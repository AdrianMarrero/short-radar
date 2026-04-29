"""Position sizing helper (spec §16)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PositionSize:
    shares: int
    risk_per_share: Optional[float]
    max_loss: Optional[float]
    max_gain: Optional[float]
    risk_reward: Optional[float]
    warning: Optional[str]


def size_position(
    capital: float,
    risk_pct: float,
    entry: Optional[float],
    stop: Optional[float],
    target: Optional[float],
) -> PositionSize:
    if not entry or not stop or stop <= entry:
        return PositionSize(0, None, None, None, None, "invalid entry/stop")

    risk_per_share = stop - entry
    risk_amount = capital * (risk_pct / 100.0)
    shares = int(risk_amount // risk_per_share)

    max_loss = round(shares * risk_per_share, 2)
    max_gain = round(shares * (entry - target), 2) if target and target < entry else None
    rr = round((entry - target) / risk_per_share, 2) if target and target < entry else None

    warning = None
    if rr is not None and rr < 1.5:
        warning = "Ratio R:R por debajo de 1.5 — considera buscar mejor entrada."

    return PositionSize(
        shares=shares,
        risk_per_share=round(risk_per_share, 4),
        max_loss=max_loss,
        max_gain=max_gain,
        risk_reward=rr,
        warning=warning,
    )
