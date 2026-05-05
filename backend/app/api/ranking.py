"""Ranking endpoints — LONG bias edition with conservative/aggressive split.

v2 redesign:
  - Hydrate v2 fields (tier/category/factor_scores/multipliers/warnings/
    explanation/...) from ShortScore.raw_score_data JSON.
  - /api/ranking takes an optional ``category`` query param.
  - /conservative filters category in {investment, swing_trade}.
  - /aggressive filters category in {swing_trade, speculative, cyclical}.
  - After category filtering, daily TIER CAPS are applied
    (A+ <= 3, A <= 7, B <= 15, C <= 30) via tiers.assign_tiers, with the
    dynamic A+ floor logic.
"""
from __future__ import annotations

import json
import math
from datetime import date as DateType
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ShortScore, Instrument, TechnicalIndicators
from app.api.schemas import ScoreOut
from app.scoring.tiers import assign_tiers, TIER_DAILY_CAP, TIER_ORDER

router = APIRouter(prefix="/api/ranking", tags=["ranking"])


CONSERVATIVE_CATEGORIES = {"investment", "swing_trade"}
AGGRESSIVE_CATEGORIES = {"swing_trade", "speculative", "cyclical"}


def _sanitize_floats(obj: Any) -> Any:
    """Recursively replace non-finite floats (NaN, +Inf, -Inf) with None.

    Python's stdlib json.dumps (used by Starlette's JSONResponse) rejects
    these values with `ValueError: Out of range float values are not JSON
    compliant`. yfinance frequently returns NaN for European tickers'
    fundamentals (forward_pe, peg_ratio, margins) and a divide-by-zero
    in derived metrics can produce Inf — sanitize at the response boundary.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_sanitize_floats(v) for v in obj)
    return obj


def _safe_response(out: list[ScoreOut]) -> JSONResponse:
    payload = [_sanitize_floats(s.model_dump(mode="json")) for s in out]
    return JSONResponse(content=payload)


def _coerce_raw(score: ShortScore) -> dict:
    """Normalize raw_score_data: PG returns dict directly; SQLite stores TEXT."""
    raw = score.raw_score_data
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw:
            return {}
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _row_to_score_out(score: ShortScore, inst: Instrument, tech) -> ScoreOut:
    raw = _coerce_raw(score)
    return ScoreOut(
        instrument_id=inst.id,
        ticker=inst.ticker,
        name=inst.name or inst.ticker,
        exchange=inst.exchange,
        sector=inst.sector or "",
        last_close=None,
        change_1d=tech.change_1d if tech else None,
        change_5d=tech.change_5d if tech else None,
        change_1m=tech.change_1m if tech else None,
        total_score=score.total_score,
        technical_score=score.technical_score,
        news_score=score.news_score,
        fundamental_score=score.fundamental_score,
        macro_score=score.macro_score,
        squeeze_risk_score=score.squeeze_risk_score,
        liquidity_score=score.liquidity_score,
        setup_type=score.setup_type,
        conviction=score.conviction,
        horizon=score.horizon,
        entry_price=score.entry_price,
        stop_price=score.stop_price,
        target_1=score.target_1,
        target_2=score.target_2,
        invalidation_reason=score.invalidation_reason or "",
        tier=raw.get("tier"),
        category=raw.get("category"),
        factor_scores=raw.get("factor_scores"),
        multipliers=raw.get("multipliers"),
        warnings=list(raw.get("warnings") or []),
        explanation=list(raw.get("explanation") or []),
        entry_zone_status=raw.get("entry_zone_status"),
        extension_status=raw.get("extension_status"),
        perf_1m_pct=raw.get("perf_1m_pct"),
    )


def _inject_last_close(db: Session, out: list[ScoreOut]) -> list[ScoreOut]:
    if not out:
        return out
    from app.models import PriceDaily
    ids = [s.instrument_id for s in out]
    last_prices = (
        db.query(PriceDaily.instrument_id, PriceDaily.close, PriceDaily.date)
        .filter(PriceDaily.instrument_id.in_(ids))
        .order_by(PriceDaily.instrument_id, PriceDaily.date.desc())
        .all()
    )
    seen: dict[int, float] = {}
    for inst_id, close, _ in last_prices:
        if inst_id not in seen and close is not None:
            seen[inst_id] = float(close)
    for s in out:
        s.last_close = seen.get(s.instrument_id)
    return out


def _apply_daily_caps(rows: list[ScoreOut]) -> list[ScoreOut]:
    """Re-tier the rows respecting daily caps + the dynamic A+ floor.

    The per-row ``tier`` stored in raw_score_data is computed without
    knowledge of the rest of the day's universe. Here we have the full
    set of survivors — re-assign and trim.

    Caps come from tiers.TIER_DAILY_CAP. Anything that gets pushed below
    ``D`` (impossible right now since D is unlimited) would be dropped.
    """
    if not rows:
        return rows
    pairs = [(s.instrument_id, float(s.total_score or 0.0)) for s in rows]
    tier_map = assign_tiers(pairs)

    out: list[ScoreOut] = []
    counts = {t: 0 for t in TIER_ORDER}
    # Sort by total_score desc so the cap consumes the strongest first
    rows_sorted = sorted(rows, key=lambda r: float(r.total_score or 0.0), reverse=True)
    for r in rows_sorted:
        new_tier = tier_map.get(r.instrument_id, r.tier)
        if new_tier and counts.get(new_tier, 0) >= TIER_DAILY_CAP.get(new_tier, 10**9):
            continue  # cap already filled — should not happen given assign_tiers logic
        r.tier = new_tier
        counts[new_tier] = counts.get(new_tier, 0) + 1
        out.append(r)
    return out


@router.get("", response_model=list[ScoreOut])
def get_ranking(
    db: Session = Depends(get_db),
    market: Optional[str] = Query(None),
    sector: Optional[str] = None,
    min_score: float = Query(0.0, ge=0, le=100),
    setup: Optional[str] = None,
    horizon: Optional[str] = None,
    category: Optional[str] = Query(None, description="investment | swing_trade | speculative | cyclical"),
    limit: int = Query(50, ge=1, le=500),
):
    """General ranking. Long candidates ordered by score."""
    latest_date = db.query(ShortScore.date).order_by(ShortScore.date.desc()).limit(1).scalar()
    if not latest_date:
        return _safe_response([])

    q = (
        db.query(ShortScore, Instrument, TechnicalIndicators)
        .join(Instrument, Instrument.id == ShortScore.instrument_id)
        .outerjoin(
            TechnicalIndicators,
            (TechnicalIndicators.instrument_id == ShortScore.instrument_id)
            & (TechnicalIndicators.date == ShortScore.date),
        )
        .filter(ShortScore.date == latest_date)
        .filter(ShortScore.total_score >= min_score)
    )

    if market:
        q = q.filter(Instrument.exchange == market.upper())
    if sector:
        q = q.filter(Instrument.sector.ilike(f"%{sector}%"))
    if setup:
        q = q.filter(ShortScore.setup_type == setup)
    if horizon:
        q = q.filter(ShortScore.horizon == horizon)

    # Pull more than `limit` so we can apply category + tier filters in Python
    # without losing legitimate candidates to a too-tight pre-limit.
    rows = (
        q.order_by(ShortScore.total_score.desc())
        .limit(max(limit * 4, 100))
        .all()
    )
    out = [_row_to_score_out(s, i, t) for s, i, t in rows]
    if category:
        cat = category.lower().strip()
        out = [s for s in out if (s.category or "") == cat]
    out = _apply_daily_caps(out)[:limit]
    return _safe_response(_inject_last_close(db, out))


@router.get("/conservative", response_model=list[ScoreOut])
def get_conservative(
    db: Session = Depends(get_db),
    limit: int = Query(15, ge=1, le=30),
):
    """Conservative long candidates: confirmed uptrends with healthy fundamentals."""
    latest_date = db.query(ShortScore.date).order_by(ShortScore.date.desc()).limit(1).scalar()
    if not latest_date:
        return _safe_response([])

    rows = (
        db.query(ShortScore, Instrument, TechnicalIndicators)
        .join(Instrument, Instrument.id == ShortScore.instrument_id)
        .outerjoin(
            TechnicalIndicators,
            (TechnicalIndicators.instrument_id == ShortScore.instrument_id)
            & (TechnicalIndicators.date == ShortScore.date),
        )
        .filter(ShortScore.date == latest_date)
        .filter(ShortScore.total_score >= 60)
        .filter(ShortScore.entry_price.is_not(None))
        .filter(ShortScore.stop_price.is_not(None))
        .filter(ShortScore.target_2.is_not(None))
        .order_by(ShortScore.total_score.desc())
        .limit(200)
        .all()
    )

    out = [_row_to_score_out(s, i, t) for s, i, t in rows]
    out = [s for s in out if (s.category or "") in CONSERVATIVE_CATEGORIES]
    out = _apply_daily_caps(out)[:limit]
    return _safe_response(_inject_last_close(db, out))


@router.get("/aggressive", response_model=list[ScoreOut])
def get_aggressive(
    db: Session = Depends(get_db),
    limit: int = Query(15, ge=1, le=30),
):
    """Aggressive long candidates: catalysts digesting, breakouts, momentum."""
    latest_date = db.query(ShortScore.date).order_by(ShortScore.date.desc()).limit(1).scalar()
    if not latest_date:
        return _safe_response([])

    rows = (
        db.query(ShortScore, Instrument, TechnicalIndicators)
        .join(Instrument, Instrument.id == ShortScore.instrument_id)
        .outerjoin(
            TechnicalIndicators,
            (TechnicalIndicators.instrument_id == ShortScore.instrument_id)
            & (TechnicalIndicators.date == ShortScore.date),
        )
        .filter(ShortScore.date == latest_date)
        .filter(ShortScore.total_score >= 55)
        .filter(ShortScore.entry_price.is_not(None))
        .filter(ShortScore.stop_price.is_not(None))
        .filter(ShortScore.target_2.is_not(None))
        .order_by(ShortScore.total_score.desc())
        .limit(200)
        .all()
    )

    out = [_row_to_score_out(s, i, t) for s, i, t in rows]
    out = [s for s in out if (s.category or "") in AGGRESSIVE_CATEGORIES]
    out = _apply_daily_caps(out)[:limit]
    return _safe_response(_inject_last_close(db, out))
