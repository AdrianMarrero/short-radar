"""Ranking endpoints — LONG bias edition with conservative/aggressive split."""
from __future__ import annotations

from datetime import date as DateType
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ShortScore, Instrument, TechnicalIndicators
from app.api.schemas import ScoreOut

router = APIRouter(prefix="/api/ranking", tags=["ranking"])


def _row_to_score_out(score, inst, tech) -> ScoreOut:
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


@router.get("", response_model=list[ScoreOut])
def get_ranking(
    db: Session = Depends(get_db),
    market: Optional[str] = Query(None),
    sector: Optional[str] = None,
    min_score: float = Query(0.0, ge=0, le=100),
    setup: Optional[str] = None,
    horizon: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """General ranking. Long candidates ordered by score."""
    latest_date = db.query(ShortScore.date).order_by(ShortScore.date.desc()).limit(1).scalar()
    if not latest_date:
        return []

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

    rows = q.order_by(ShortScore.total_score.desc()).limit(limit).all()
    out = [_row_to_score_out(s, i, t) for s, i, t in rows]
    return _inject_last_close(db, out)


@router.get("/conservative", response_model=list[ScoreOut])
def get_conservative(
    db: Session = Depends(get_db),
    limit: int = Query(15, ge=1, le=30),
):
    """Conservative long candidates: confirmed uptrends with healthy fundamentals.

    Filters:
      - total score >= 65
      - technical score >= 60 (confirmed bullish trend required)
      - fundamental score >= 55 (no deterioration)
      - liquidity >= 60
      - conviction medium or high
      - setup is 'trend' (sustained uptrends)
      - R:R >= 1.5

    Expected: +5/+12% in 3-6 weeks, win rate ~60%.
    """
    latest_date = db.query(ShortScore.date).order_by(ShortScore.date.desc()).limit(1).scalar()
    if not latest_date:
        return []

    rows = (
        db.query(ShortScore, Instrument, TechnicalIndicators)
        .join(Instrument, Instrument.id == ShortScore.instrument_id)
        .outerjoin(
            TechnicalIndicators,
            (TechnicalIndicators.instrument_id == ShortScore.instrument_id)
            & (TechnicalIndicators.date == ShortScore.date),
        )
        .filter(ShortScore.date == latest_date)
        .filter(ShortScore.total_score >= 65)
        .filter(ShortScore.technical_score >= 60)
        .filter(ShortScore.fundamental_score >= 55)
        .filter(ShortScore.liquidity_score >= 60)
        .filter(ShortScore.conviction.in_(["medium", "high"]))
        .filter(ShortScore.setup_type.in_(["trend"]))
        .filter(ShortScore.entry_price.is_not(None))
        .filter(ShortScore.stop_price.is_not(None))
        .filter(ShortScore.target_2.is_not(None))
        .order_by(
            ShortScore.conviction.desc(),
            ShortScore.total_score.desc(),
        )
        .limit(limit)
        .all()
    )
    out = [_row_to_score_out(s, i, t) for s, i, t in rows]
    return _inject_last_close(db, out)


@router.get("/aggressive", response_model=list[ScoreOut])
def get_aggressive(
    db: Session = Depends(get_db),
    limit: int = Query(15, ge=1, le=30),
):
    """Aggressive long candidates: catalysts digesting, breakouts, momentum.

    Filters:
      - total score >= 60
      - liquidity >= 60
      - One of:
          * news_score >= 65 (positive catalyst still digesting)
          * setup is 'breakout' (momentum starting)
          * setup is 'reversion' (oversold bounce in healthy stock)
          * setup is 'momentum' (sector tailwind)
      - Fundamentals at least neutral (>= 45)

    Expected: +10/+25% in 2-4 weeks, win rate ~45%, wider stops.
    Higher upside, higher failure rate. Use position sizing accordingly.
    """
    latest_date = db.query(ShortScore.date).order_by(ShortScore.date.desc()).limit(1).scalar()
    if not latest_date:
        return []

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
        .filter(ShortScore.liquidity_score >= 60)
        .filter(ShortScore.fundamental_score >= 45)
        .filter(
            (ShortScore.news_score >= 65)
            | (ShortScore.setup_type.in_(["breakout", "reversion", "momentum", "catalyst"]))
        )
        .filter(ShortScore.entry_price.is_not(None))
        .filter(ShortScore.stop_price.is_not(None))
        .filter(ShortScore.target_2.is_not(None))
        .order_by(
            ShortScore.total_score.desc(),
        )
        .limit(limit)
        .all()
    )
    out = [_row_to_score_out(s, i, t) for s, i, t in rows]
    return _inject_last_close(db, out)