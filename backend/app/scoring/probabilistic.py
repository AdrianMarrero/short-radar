"""Probabilistic display layer — Monte Carlo path simulation for signal odds.

Given entry/stop/target and historical realized volatility, simulate
10_000 price paths under Geometric Brownian Motion and count barrier
hits. Output is INFORMATION not prediction: 'given the volatility this
stock currently has, what's the chance of touching target_1 before
hitting stop'.

Drift is zero by default (neutral). For signals with strong
earnings_momentum (>70), inject a small positive PEAD drift documented
in academic literature (Bernard & Thomas 1989). No other factor enters
the drift — keeps the model honest.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np


# Trading-day annualization factor.
TRADING_DAYS_YEAR = 252

# PEAD (post-earnings-announcement drift) — small positive drift only applied
# when the earnings_momentum factor score is strong. ~0.05%/day for ~60 days
# of drift is roughly consistent with the academic literature (Bernard &
# Thomas 1989). Threshold of 70 corresponds to top-quartile momentum.
PEAD_DRIFT_THRESHOLD = 70.0
PEAD_DRIFT_DAILY = 0.0005

# Number of paths to simulate. 10k is a reasonable trade-off between
# variance (~1% stderr on probabilities) and compute time.
DEFAULT_N_SIMS = 10_000


@dataclass
class MonteCarloResult:
    p_hit_target_1: float          # 0..1
    p_hit_target_2: Optional[float]   # None if target_2 missing
    p_hit_stop: float
    p_expire: float
    expected_r: float              # in R units
    edge_class: str                # "high_edge" | "positive_edge" | "neutral" | "negative_edge"
    n_sims: int
    drift_daily_used: float

    def to_dict(self) -> dict:
        return asdict(self)


def compute_pead_drift(earnings_momentum_score: Optional[float]) -> float:
    """Return +PEAD_DRIFT_DAILY if earnings_momentum score > threshold, else 0.

    Pure function; no side effects. Used by the engine to inject a small
    positive drift only when the earnings momentum signal is strong.
    """
    if earnings_momentum_score is None:
        return 0.0
    try:
        v = float(earnings_momentum_score)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(v):
        return 0.0
    return PEAD_DRIFT_DAILY if v > PEAD_DRIFT_THRESHOLD else 0.0


def _classify_edge(expected_r: float) -> str:
    if expected_r > 1.2:
        return "high_edge"
    if expected_r > 0.4:
        return "positive_edge"
    if expected_r > -0.4:
        return "neutral"
    return "negative_edge"


def simulate_signal_probabilities(
    entry: Optional[float],
    stop: Optional[float],
    target_1: Optional[float],
    target_2: Optional[float],
    horizon_days: int,
    realized_vol_annual: Optional[float],
    drift_daily: float = 0.0,
    n_sims: int = DEFAULT_N_SIMS,
    rng_seed: Optional[int] = None,
) -> Optional[MonteCarloResult]:
    """Run Geometric Brownian Motion sim, count barrier hits.

    Returns None if any input is invalid (entry<=0, stop>=entry,
    target_1<=entry, realized_vol_annual<=0, horizon_days<1).

    Walks day-by-day applying log-return shocks. At each step checks
    barriers in order: stop first, then target_2 if set, then target_1.
    First barrier hit wins for that path. If neither hit by horizon end,
    counts as expire and records terminal price for expected_r.
    """
    # ---- Input validation ----
    if entry is None or stop is None or target_1 is None or realized_vol_annual is None:
        return None
    try:
        entry_f = float(entry)
        stop_f = float(stop)
        t1_f = float(target_1)
        vol_f = float(realized_vol_annual)
        h_days = int(horizon_days)
    except (TypeError, ValueError):
        return None
    t2_f: Optional[float]
    if target_2 is None:
        t2_f = None
    else:
        try:
            t2_f = float(target_2)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(t2_f) or t2_f <= t1_f:
            t2_f = None  # ignore nonsensical target_2; keep simulation valid

    if not (math.isfinite(entry_f) and math.isfinite(stop_f) and math.isfinite(t1_f) and math.isfinite(vol_f)):
        return None
    if entry_f <= 0 or stop_f >= entry_f or t1_f <= entry_f:
        return None
    if vol_f <= 0 or h_days < 1:
        return None
    if n_sims < 100:
        n_sims = 100

    sigma_daily = vol_f / math.sqrt(TRADING_DAYS_YEAR)
    drift_term = drift_daily - 0.5 * sigma_daily * sigma_daily

    rng = np.random.default_rng(rng_seed)

    # Vectorized GBM: draw all shocks at once, walk day-by-day with cumulative
    # log-return. For each path, find the first day a barrier is breached.
    shocks = rng.standard_normal(size=(n_sims, h_days))
    # log-return per step = drift_term + sigma_daily * shock
    log_steps = drift_term + sigma_daily * shocks
    cum_log = np.cumsum(log_steps, axis=1)
    # price[t] = entry * exp(cum_log[t])
    prices = entry_f * np.exp(cum_log)

    stop_mask = prices <= stop_f
    t1_mask = prices >= t1_f
    if t2_f is not None:
        t2_mask = prices >= t2_f
    else:
        t2_mask = None

    # For each row, find the first day each barrier is hit (h_days if never).
    def first_hit(mask: np.ndarray) -> np.ndarray:
        # argmax on a boolean returns the first True index; rows with no True
        # are detected via mask.any.
        any_hit = mask.any(axis=1)
        idx = mask.argmax(axis=1)
        idx = np.where(any_hit, idx, h_days)  # sentinel = h_days (never)
        return idx

    stop_idx = first_hit(stop_mask)
    t1_idx = first_hit(t1_mask)
    t2_idx = first_hit(t2_mask) if t2_mask is not None else np.full(n_sims, h_days, dtype=np.int64)

    # Internal bucketing (disjoint, for expected_r):
    #   stop_only      — stop hit before any upside barrier
    #   t2_reached     — path reaches t2 within horizon (t1 was reached
    #                    en route since t2 > t1; bucketed as t2 outcome)
    #   t1_only        — t1 reached but never t2, within horizon
    #   expire_only    — neither barrier reached within horizon
    # If stop and a target hit on the SAME bar, conservatively assume the
    # stop went first (worst-case — keeps the display honest).
    upside_idx = np.minimum(t1_idx, t2_idx)  # earliest of any upside hit
    stop_only = (stop_idx < h_days) & (stop_idx <= upside_idx)

    remaining = ~stop_only
    if t2_mask is not None:
        t2_reached = remaining & (t2_idx < h_days)
    else:
        t2_reached = np.zeros(n_sims, dtype=bool)
    t1_only = remaining & ~t2_reached & (t1_idx < h_days)
    expire = ~(stop_only | t1_only | t2_reached)

    # Bucket probabilities (disjoint).
    p_stop_only = float(stop_only.mean())
    p_t1_only = float(t1_only.mean())
    p_t2_reached = float(t2_reached.mean()) if t2_mask is not None else 0.0
    p_expire = float(expire.mean())

    # User-facing probabilities: P(t1) is inclusive of any t2 hits since
    # a path that reaches t2 also passed through t1.
    p_t1_user = p_t1_only + p_t2_reached
    p_t2_user: Optional[float] = p_t2_reached if t2_mask is not None else None

    # ---- Expected R (uses disjoint buckets) ----
    risk = entry_f - stop_f  # > 0 by validation
    r_t1 = (t1_f - entry_f) / risk
    r_t2 = ((t2_f - entry_f) / risk) if t2_f is not None else 0.0
    r_stop = -1.0

    if expire.any():
        # Terminal price for paths that never hit either barrier.
        terminal = prices[:, -1]
        terminal_expiring = terminal[expire]
        r_expire_each = (terminal_expiring - entry_f) / risk
        mean_r_expire = float(r_expire_each.mean())
    else:
        mean_r_expire = 0.0

    expected_r = (
        p_t1_only * r_t1
        + p_t2_reached * r_t2
        + p_stop_only * r_stop
        + p_expire * mean_r_expire
    )

    if not math.isfinite(expected_r):
        return None

    edge_class = _classify_edge(expected_r)

    return MonteCarloResult(
        p_hit_target_1=round(p_t1_user, 4),
        p_hit_target_2=round(p_t2_user, 4) if p_t2_user is not None else None,
        p_hit_stop=round(p_stop_only, 4),
        p_expire=round(p_expire, 4),
        expected_r=round(expected_r, 3),
        edge_class=edge_class,
        n_sims=int(n_sims),
        drift_daily_used=round(float(drift_daily), 6),
    )
