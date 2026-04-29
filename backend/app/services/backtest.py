"""Basic backtesting service.

For each historical ranking entry, simulate a short trade entered at the
close on the signal day. Exit when stop is hit, target_2 is hit, or after
N days. Track P&L %, hit rate, and average return per setup type.

This is intentionally simple: it does not model slippage, borrow fees, or
intraday fills. Use it as a sanity check, not a precise simulator.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as DateType, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ShortScore, PriceDaily


@dataclass
class BacktestResult:
    n_trades: int
    win_rate_pct: float
    avg_return_pct: float
    avg_hold_days: float
    by_setup: dict[str, dict]


def _future_prices(db: Session, instrument_id: int, start: DateType, days: int) -> list[tuple[DateType, float, float, float]]:
    end = start + timedelta(days=days * 2)  # buffer for weekends
    rows = (
        db.query(PriceDaily)
        .filter(PriceDaily.instrument_id == instrument_id)
        .filter(PriceDaily.date > start)
        .filter(PriceDaily.date <= end)
        .order_by(PriceDaily.date)
        .limit(days)
        .all()
    )
    return [(r.date, r.high, r.low, r.close) for r in rows]


def backtest(db: Session, min_score: float = 65, hold_days: int = 10) -> BacktestResult:
    scores = (
        db.query(ShortScore)
        .filter(ShortScore.total_score >= min_score)
        .filter(ShortScore.entry_price.is_not(None))
        .filter(ShortScore.stop_price.is_not(None))
        .filter(ShortScore.target_2.is_not(None))
        .filter(ShortScore.setup_type != "avoid_squeeze")
        .all()
    )

    by_setup: dict[str, list[float]] = {}
    rets, holds, wins = [], [], 0

    for s in scores:
        future = _future_prices(db, s.instrument_id, s.date, hold_days)
        if not future:
            continue

        entry, stop, t2 = s.entry_price, s.stop_price, s.target_2
        outcome_pct: Optional[float] = None
        held: int = 0

        for i, (_, hi, lo, _) in enumerate(future, 1):
            held = i
            # For a SHORT: stop is HIGHER, target is LOWER
            if hi >= stop:
                outcome_pct = (entry - stop) / entry * 100.0
                break
            if lo <= t2:
                outcome_pct = (entry - t2) / entry * 100.0
                break

        if outcome_pct is None and future:
            last_close = future[-1][3]
            outcome_pct = (entry - last_close) / entry * 100.0

        if outcome_pct is None:
            continue

        rets.append(outcome_pct)
        holds.append(held)
        if outcome_pct > 0:
            wins += 1
        by_setup.setdefault(s.setup_type, []).append(outcome_pct)

    n = len(rets)
    if n == 0:
        return BacktestResult(0, 0.0, 0.0, 0.0, {})

    return BacktestResult(
        n_trades=n,
        win_rate_pct=round(100.0 * wins / n, 2),
        avg_return_pct=round(sum(rets) / n, 2),
        avg_hold_days=round(sum(holds) / n, 1),
        by_setup={
            k: {"n": len(v), "avg_pct": round(sum(v) / len(v), 2)}
            for k, v in by_setup.items()
        },
    )
