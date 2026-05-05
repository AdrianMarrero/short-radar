"""Signal stats endpoint — paper-backtest visibility for the user.

Returns per-tier / per-category / per-setup_type breakdowns of the
signals tracker so we can answer the question: "is the system actually
giving edge, or are A+ signals just noise?".
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.ranking import _sanitize_floats
from app.api.schemas import SignalStatsBucket, SignalStatsOut
from app.core.database import get_db
from app.models import Signal


router = APIRouter(prefix="/api/signals", tags=["signals"])


CLOSED_STATUSES = {"hit_stop", "hit_target_1", "hit_target_2", "expired"}


def _bucket(group: list[Signal]) -> SignalStatsBucket:
    """Compute n / n_closed / win_rate / avg_return / expectancy for a group.

    Win = pnl_pct > 0. Expectancy = win_rate * avg_win - loss_rate * avg_loss
    (with avg_loss as an absolute value). Returns 0s on empty/closed groups.
    """
    n = len(group)
    closed = [s for s in group if s.status in CLOSED_STATUSES and s.pnl_pct is not None]
    n_closed = len(closed)
    if n_closed == 0:
        return SignalStatsBucket(
            n=n, n_closed=0, win_rate_pct=0.0,
            avg_return_pct=0.0, expectancy=0.0,
        )

    wins = [float(s.pnl_pct) for s in closed if (s.pnl_pct or 0.0) > 0]
    losses = [float(s.pnl_pct) for s in closed if (s.pnl_pct or 0.0) <= 0]
    win_rate = len(wins) / n_closed
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0  # already negative
    avg_return = sum(float(s.pnl_pct) for s in closed) / n_closed
    expectancy = win_rate * avg_win + (1.0 - win_rate) * avg_loss

    return SignalStatsBucket(
        n=n,
        n_closed=n_closed,
        win_rate_pct=round(win_rate * 100.0, 2),
        avg_return_pct=round(avg_return, 2),
        expectancy=round(expectancy, 2),
    )


def _group_by(signals: Iterable[Signal], key: str) -> dict[str, list[Signal]]:
    out: dict[str, list[Signal]] = defaultdict(list)
    for s in signals:
        v = getattr(s, key, None) or "unknown"
        out[str(v)].append(s)
    return dict(out)


@router.get("/stats", response_model=SignalStatsOut)
def signal_stats(db: Session = Depends(get_db)):
    signals = db.query(Signal).all()
    total = len(signals)
    open_n = sum(1 for s in signals if s.status == "open")
    closed_n = sum(1 for s in signals if s.status in CLOSED_STATUSES)

    overall = _bucket(signals)

    by_tier_groups = _group_by(signals, "tier")
    by_category_groups = _group_by(signals, "category")
    by_setup_groups = _group_by(signals, "setup_type")

    payload = SignalStatsOut(
        total=total,
        open=open_n,
        closed=closed_n,
        win_rate_pct=overall.win_rate_pct,
        avg_return_pct=overall.avg_return_pct,
        expectancy=overall.expectancy,
        by_tier={k: _bucket(v) for k, v in by_tier_groups.items()},
        by_category={k: _bucket(v) for k, v in by_category_groups.items()},
        by_setup_type={k: _bucket(v) for k, v in by_setup_groups.items()},
    )
    # Final-step sanitize so any edge-case NaNs from corrupted historical
    # rows don't break JSON serialization.
    return JSONResponse(content=_sanitize_floats(payload.model_dump(mode="json")))
