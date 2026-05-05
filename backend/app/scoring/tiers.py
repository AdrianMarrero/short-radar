"""Tier assignment — A+/A/B/C/D with dynamic threshold + daily caps.

Why tiers? Without a hard cap, on a strong-trend day the engine can return
30 candidates all looking equally great. Adrián has 2.000€ — he can
realistically open 1-3 positions per week. A tier system enforces
discipline: at most 3 A+ ideas/day, 7 A, 15 B, 30 C; D is unlimited but
not surfaced in the conservative view.

Algorithm:
  1. Sort candidates by total_score descending.
  2. For each candidate, compute base_tier from score thresholds.
  3. Daily cap: if base_tier is full, downgrade one tier and re-check.
  4. Dynamic A+ threshold: if more than 3 candidates qualify for A+
     by score alone, raise the score floor until <= 3 remain at A+.

This module is pure: it accepts a list of (id, score) tuples, returns a
dict id -> tier. Persistence is the caller's job.
"""
from __future__ import annotations

from typing import Iterable

# Static base thresholds (before dynamic A+ tightening)
TIER_FLOOR = {
    "A+": 85.0,
    "A": 75.0,
    "B": 65.0,
    "C": 50.0,
    "D": 0.0,
}

# Daily caps (how many we'll publish per tier per day)
TIER_DAILY_CAP = {
    "A+": 3,
    "A": 7,
    "B": 15,
    "C": 30,
    "D": 10**9,  # effectively unlimited
}


TIER_ORDER = ["A+", "A", "B", "C", "D"]


def _base_tier(score: float, a_plus_floor: float) -> str:
    if score >= a_plus_floor:
        return "A+"
    if score >= TIER_FLOOR["A"]:
        return "A"
    if score >= TIER_FLOOR["B"]:
        return "B"
    if score >= TIER_FLOOR["C"]:
        return "C"
    return "D"


def _dynamic_a_plus_floor(scores_desc: list[float], cap: int = 3) -> float:
    """Raise the A+ floor until at most `cap` candidates qualify.

    Walks the scores in descending order; returns the (cap+1)-th score
    plus a tiny epsilon so exactly `cap` rows are above. If fewer than
    cap+1 candidates exist, returns the static floor.
    """
    static = TIER_FLOOR["A+"]
    above = [s for s in scores_desc if s >= static]
    if len(above) <= cap:
        return static
    # The (cap)th score (0-indexed cap) is the floor — anything strictly
    # above qualifies. Use the next score down + epsilon for safety.
    idx = cap  # the (cap+1)-th element index
    if idx >= len(scores_desc):
        return static
    return float(scores_desc[idx]) + 1e-6


def assign_tiers(candidates: Iterable[tuple]) -> dict:
    """Assign tiers respecting daily caps and dynamic A+ threshold.

    Args:
        candidates: iterable of (key, score) tuples. `key` can be any
            hashable identifier (instrument_id, ticker, dataclass...).

    Returns:
        dict mapping each key -> tier string (one of A+/A/B/C/D).
    """
    sorted_pairs = sorted(candidates, key=lambda kv: float(kv[1] or 0.0), reverse=True)
    if not sorted_pairs:
        return {}

    scores_desc = [float(s or 0.0) for _, s in sorted_pairs]
    a_plus_floor = _dynamic_a_plus_floor(scores_desc, cap=TIER_DAILY_CAP["A+"])

    counts = {t: 0 for t in TIER_ORDER}
    out: dict = {}
    for key, score in sorted_pairs:
        s = float(score or 0.0)
        base = _base_tier(s, a_plus_floor)
        # Walk down the tier ladder if the base tier's daily cap is full
        idx = TIER_ORDER.index(base)
        while idx < len(TIER_ORDER) - 1 and counts[TIER_ORDER[idx]] >= TIER_DAILY_CAP[TIER_ORDER[idx]]:
            idx += 1
        tier = TIER_ORDER[idx]
        counts[tier] += 1
        out[key] = tier
    return out


def assign_tier_single(score: float) -> str:
    """Single-shot tier assignment without daily caps. Used as a fallback
    or when caller doesn't have the full daily candidate set."""
    return _base_tier(float(score or 0.0), TIER_FLOOR["A+"])
