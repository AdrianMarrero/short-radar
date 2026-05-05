"""Hard gates — boolean filters applied BEFORE scoring.

A ticker that fails any gate is excluded entirely. This is the cornerstone
of the v2 redesign: stop scoring overextended/illiquid setups instead of
just deducting points after the fact.

All gates are LENIENT for missing data: if a required input is unknown
(e.g. SPY history unavailable for beta), the gate passes. We do NOT
penalize the ticker for our data limitations.

Gates:
  - liquidity:       avg dollar volume >= $2M/day
  - parabolic:       not in a vertical 30d blow-off
  - extension:       1-month perf <= +40%
  - rr:              risk/reward >= 1.5
  - thesis_intact:   no fresh negative catalyst killing the long thesis
  - chase:           current price within +5% of model entry
  - earnings:        no earnings expected in next 5 days (STUB until calendar)
  - sma_200_slope:   SMA200 sloping flat-to-up (>= -0.001 over 20 bars)
  - beta:            beta vs SPY <= 3.0 (lenient if unknown)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.scoring.technicals import TechnicalSnapshot


@dataclass
class GatesResult:
    all_pass: bool
    liquidity: bool
    parabolic: bool
    extension: bool
    rr: bool
    thesis_intact: bool
    chase: bool
    earnings: bool
    sma_200_slope: bool
    beta: bool
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "all_pass": self.all_pass,
            "liquidity": self.liquidity,
            "parabolic": self.parabolic,
            "extension": self.extension,
            "rr": self.rr,
            "thesis_intact": self.thesis_intact,
            "chase": self.chase,
            "earnings": self.earnings,
            "sma_200_slope": self.sma_200_slope,
            "beta": self.beta,
            "failure_reasons": list(self.failure_reasons),
        }


# --- Individual gate functions -------------------------------------------

def passes_liquidity_gate(
    avg_dollar_vol_30d: Optional[float],
    threshold: float = 2_000_000.0,
) -> bool:
    """At least $2M/day average dollar volume over 30 sessions.

    Lenient: if the metric is unknown, we still let it through (the
    legacy liquidity score will catch it as a soft penalty downstream).
    """
    if avg_dollar_vol_30d is None:
        return True
    return float(avg_dollar_vol_30d) >= threshold


def passes_parabolic_gate(snap: Optional[TechnicalSnapshot]) -> bool:
    """Reject vertical/parabolic blow-offs."""
    if snap is None:
        return True
    return not getattr(snap, "is_parabolic_30d", False)


def passes_extension_gate(
    perf_1m_pct: Optional[float],
    max_pct: float = 40.0,
) -> bool:
    """Reject if the stock is up more than +40% in the last month."""
    if perf_1m_pct is None:
        return True
    return float(perf_1m_pct) <= max_pct


def passes_rr_gate(
    entry: Optional[float],
    stop: Optional[float],
    target: Optional[float],
    min_rr: float = 1.5,
) -> bool:
    """Risk/reward must be at least 1.5:1 to score the candidate."""
    if entry is None or stop is None or target is None:
        return False
    if entry <= 0 or stop >= entry or target <= entry:
        return False
    risk = entry - stop
    reward = target - entry
    if risk <= 0 or reward <= 0:
        return False
    return (reward / risk) >= min_rr


def passes_thesis_intact_gate(has_negative_catalyst: bool) -> bool:
    """A fresh negative catalyst kills the long thesis."""
    return not bool(has_negative_catalyst)


def passes_chase_gate(
    last_close: Optional[float],
    entry_computed: Optional[float],
    max_above_entry_pct: float = 5.0,
) -> bool:
    """Don't chase: refuse if current price is more than +5% above the
    model's ideal entry. Allows entries close to or below the entry zone.
    """
    if last_close is None or entry_computed is None or entry_computed <= 0:
        return True
    pct_above = (last_close - entry_computed) / entry_computed * 100.0
    return pct_above <= max_above_entry_pct


def passes_earnings_gate(ticker: str, days_ahead: int = 5) -> bool:
    """Reject candidates with earnings in the next `days_ahead` days.

    STUB: returns True (passes) until an earnings calendar source is wired.
    Documented limitation in CLAUDE.md.
    """
    # TODO: wire when earnings_calendar exists (yfinance earnings_dates,
    # FMP, or similar). For now, do NOT block — earnings risk is a
    # +10 to risk assessment, not a hard reject.
    return True


def passes_sma_200_slope_gate(
    snap: Optional[TechnicalSnapshot],
    min_slope: float = -0.001,
) -> bool:
    """SMA200 must be flat or rising. Lenient if data is missing."""
    if snap is None:
        return True
    slope = getattr(snap, "sma_200_slope", None)
    if slope is None:
        return True
    return float(slope) >= min_slope


def passes_beta_gate(beta: Optional[float], max_beta: float = 3.0) -> bool:
    """Reject ultra-high-beta names (3x+ market sensitivity).

    Lenient: if SPY data is unavailable, beta=None and the gate passes.
    """
    if beta is None:
        return True
    return float(beta) <= max_beta


# --- Aggregator -----------------------------------------------------------

def check_all_gates(
    *,
    snap: Optional[TechnicalSnapshot],
    avg_dollar_vol_30d: Optional[float],
    perf_1m_pct: Optional[float],
    beta: Optional[float],
    has_negative_catalyst: bool,
    entry: Optional[float],
    stop: Optional[float],
    target: Optional[float],
    last_close: Optional[float],
    ticker: str,
) -> GatesResult:
    """Run every gate. Aggregate result + reasons for any failure."""
    liq = passes_liquidity_gate(avg_dollar_vol_30d)
    para = passes_parabolic_gate(snap)
    ext = passes_extension_gate(perf_1m_pct)
    rr = passes_rr_gate(entry, stop, target)
    thesis = passes_thesis_intact_gate(has_negative_catalyst)
    chase = passes_chase_gate(last_close, entry)
    earn = passes_earnings_gate(ticker)
    sma_slope = passes_sma_200_slope_gate(snap)
    beta_ok = passes_beta_gate(beta)

    reasons: list[str] = []
    if not liq:
        reasons.append("liquidity_below_2m")
    if not para:
        reasons.append("parabolic_blowoff")
    if not ext:
        reasons.append(f"extended_1m_{perf_1m_pct:.0f}pct" if perf_1m_pct is not None else "extended")
    if not rr:
        reasons.append("rr_below_1_5")
    if not thesis:
        reasons.append("negative_catalyst")
    if not chase:
        reasons.append("chase_above_entry")
    if not earn:
        reasons.append("earnings_window")
    if not sma_slope:
        reasons.append("sma_200_falling")
    if not beta_ok:
        reasons.append(f"beta_above_3_{beta:.1f}" if beta is not None else "beta_too_high")

    all_pass = (
        liq and para and ext and rr and thesis
        and chase and earn and sma_slope and beta_ok
    )

    return GatesResult(
        all_pass=all_pass,
        liquidity=liq,
        parabolic=para,
        extension=ext,
        rr=rr,
        thesis_intact=thesis,
        chase=chase,
        earnings=earn,
        sma_200_slope=sma_slope,
        beta=beta_ok,
        failure_reasons=reasons,
    )
