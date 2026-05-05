"""Multiplicative penalties — applied AFTER the raw weighted score.

Cornerstone insight of the v2 redesign: bad signals MULTIPLY the score
down, not subtract from it. A perfect-quality stock that's already
overextended should NOT be saved by its quality — the entry is bad,
period. Multiplicative collapse > additive deduction.

All multipliers are clamped to [0.3, 1.0]:
  - 1.0 means no penalty (ideal conditions)
  - 0.3 is the floor (severe penalty, almost zeroes the score)

Three multipliers compound:
  final = raw_score * extension_mult * timing_mult * vol_anchor_mult
"""
from __future__ import annotations

import math
from typing import Optional


def _finite_or(default: float, value: Optional[float]) -> float:
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def compute_extension_multiplier(perf_1m_pct: Optional[float]) -> float:
    """Penalize stocks that already ran in the last month.

    The gate already rejects > +40%. This multiplier ramps down BEFORE
    the gate kicks in so a 25-30% mover is still scored, but heavily
    discounted.

    Schedule:
      perf <= +5%:           1.00 (no penalty — fresh)
      +5% < perf <= +15%:    1.00 -> 0.85 linear
      +15% < perf <= +25%:   0.85 -> 0.65 linear
      +25% < perf <= +40%:   0.65 -> 0.40 linear
      perf > +40%:           0.40 (gate would normally reject)
      perf < 0%:             1.00 (no penalty — pullback ok)
    """
    p = _finite_or(0.0, perf_1m_pct)
    if p <= 5.0:
        return 1.0
    if p <= 15.0:
        return _lerp(p, 5.0, 15.0, 1.0, 0.85)
    if p <= 25.0:
        return _lerp(p, 15.0, 25.0, 0.85, 0.65)
    if p <= 40.0:
        return _lerp(p, 25.0, 40.0, 0.65, 0.40)
    return 0.40


def compute_timing_multiplier(
    catalyst_age_days: Optional[float],
    catalyst_is_digesting: bool,
) -> float:
    """Reward catalysts that have been digesting 3-10 days; penalize
    fresh-news chasing (<1d) or stale catalysts (>14d).

    Rationale (from CLAUDE.md): retail edge sits in the digestion window.
    A same-day headline has already been front-run by institutions.

    Schedule:
      no catalyst:                  1.00 (neutral — not a timing case)
      < 1 day old:                  0.65 (chase risk)
      1 -> 3 days:                  0.65 -> 0.85 ramp
      3 -> 10 days (digesting):     1.00 (sweet spot, full credit)
      10 -> 14 days:                1.00 -> 0.85 fade
      > 14 days:                    0.85 (stale but still ok)
    """
    if catalyst_age_days is None:
        return 1.0
    age = _finite_or(0.0, catalyst_age_days)
    if catalyst_is_digesting and 3.0 <= age <= 10.0:
        return 1.0
    if age < 1.0:
        return 0.65
    if age < 3.0:
        return _lerp(age, 1.0, 3.0, 0.65, 0.85)
    if age <= 10.0:
        return 1.0
    if age <= 14.0:
        return _lerp(age, 10.0, 14.0, 1.00, 0.85)
    return 0.85


def compute_vol_anchor_multiplier(
    atr_pct: Optional[float],
    capital_available: float = 2000.0,
) -> float:
    """Penalize stocks where ATR is too large for the user's capital.

    With ~2000€ to allocate, an ATR > 8% means a single ATR move risks
    160€ on a full-allocation position — too much for a beginner.

    Schedule:
      atr_pct unknown:    1.00 (lenient)
      atr_pct <= 3%:      1.00 (manageable)
      3% < atr <= 5%:     1.00 -> 0.90 ramp
      5% < atr <= 8%:     0.90 -> 0.70 ramp
      atr > 8%:           0.60 (too volatile for retail)
    """
    if atr_pct is None:
        return 1.0
    a = _finite_or(0.0, atr_pct) * 100.0  # convert from fraction (0.05) to %
    if a <= 3.0:
        return 1.0
    if a <= 5.0:
        return _lerp(a, 3.0, 5.0, 1.00, 0.90)
    if a <= 8.0:
        return _lerp(a, 5.0, 8.0, 0.90, 0.70)
    return 0.60


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """Linear interpolation, clamped to [min(y0,y1), max(y0,y1)]."""
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    t = max(0.0, min(1.0, t))
    return y0 + t * (y1 - y0)


def compose_multipliers(*multipliers: float) -> float:
    """Compose any number of multipliers, clamped to [0.30, 1.00]."""
    out = 1.0
    for m in multipliers:
        out *= float(m)
    return max(0.30, min(1.0, out))
