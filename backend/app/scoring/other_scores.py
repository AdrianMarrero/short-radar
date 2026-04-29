"""Fundamental, macro, liquidity and squeeze-risk scores — LONG-BIAS edition.

Same shape as before, but:
  - Fundamentals: high score = healthy/growing company (good long candidate)
  - Macro: high score = sector tailwind (favorable macro for the stock)
  - Liquidity: unchanged (high = good, regardless of direction)
  - Squeeze: kept for schema compat, not used in long ranking
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable


@dataclass
class FundamentalScoreBreakdown:
    score: float
    deteriorating: bool
    growing: bool
    reasons: list[str]


@dataclass
class MacroScoreBreakdown:
    score: float
    reasons: list[str]


@dataclass
class LiquidityScoreBreakdown:
    score: float
    avg_daily_dollar_volume: Optional[float]
    reasons: list[str]


@dataclass
class SqueezeRiskBreakdown:
    score: float
    classification: str
    reasons: list[str]


# ---------------- Fundamentals (LONG bias) ----------------

def score_fundamentals_long(info) -> FundamentalScoreBreakdown:
    """Higher = healthier company = better long candidate."""
    if info is None:
        return FundamentalScoreBreakdown(50.0, False, False, ["no fundamentals data"])

    score = 50.0
    reasons: list[str] = []
    deteriorating = False
    growing = False

    rev_growth = info.revenue_growth_yoy
    op_margin = info.operating_margin
    fcf = info.free_cash_flow
    debt = info.total_debt or 0
    cash = info.total_cash or 0
    pe = info.pe
    eps = info.eps

    # Revenue growth — most important signal for longs
    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 14
            growing = True
            reasons.append(f"revenue +{rev_growth*100:.1f}% YoY (strong growth)")
        elif rev_growth > 0.08:
            score += 8
            growing = True
            reasons.append(f"revenue +{rev_growth*100:.1f}% YoY")
        elif 0 < rev_growth <= 0.05:
            score += 2
        elif rev_growth < -0.05:
            score -= 14
            deteriorating = True
            reasons.append(f"revenue down {rev_growth*100:.1f}% YoY")
        elif rev_growth < 0:
            score -= 6
            deteriorating = True

    # Operating margin
    if op_margin is not None:
        if op_margin > 0.20:
            score += 10
            reasons.append(f"operating margin {op_margin*100:.1f}% (strong)")
        elif op_margin > 0.08:
            score += 4
        elif op_margin < 0:
            score -= 12
            deteriorating = True
            reasons.append(f"operating margin {op_margin*100:.1f}% (negative)")

    # Free cash flow
    if fcf is not None:
        if fcf > 0:
            score += 6
            reasons.append("positive FCF")
        else:
            score -= 8
            deteriorating = True
            reasons.append("FCF negative")

    # Leverage
    if cash and debt:
        leverage = debt / max(1.0, cash)
        if leverage > 5:
            score -= 6
            reasons.append(f"high debt/cash ratio {leverage:.1f}")
        elif leverage < 1:
            score += 3
            reasons.append("strong balance sheet (debt < cash)")

    # EPS
    if eps is not None:
        if eps > 0:
            score += 4
        elif eps < 0:
            score -= 6
            reasons.append("EPS negative")

    # P/E sanity
    if pe is not None:
        if 0 < pe < 20 and rev_growth and rev_growth > 0.10:
            # GARP — growth at reasonable price
            score += 6
            reasons.append(f"PE {pe:.0f} with growth (GARP)")
        elif pe > 60:
            score -= 4
            reasons.append(f"PE {pe:.0f} (very expensive)")

    score = max(0.0, min(100.0, score))
    return FundamentalScoreBreakdown(score, deteriorating, growing, reasons)


# ---------------- Macro (LONG bias) ----------------

def score_macro_long(sector: str, macro_events: Iterable) -> MacroScoreBreakdown:
    """Macro for longs.

    Bullish events for the stock's sector raise the score.
    Bearish events for the sector lower it.
    """
    if not sector:
        return MacroScoreBreakdown(50.0, [])

    score = 50.0
    reasons = []
    sector_lower = sector.lower()

    # Sectors that benefit from typical macro events
    BULLISH_FOR_SECTOR = {
        "rate cut": ["technology", "real estate", "consumer cyclical", "utilities"],
        "stimulus": ["consumer", "industrial", "construction"],
        "infrastructure": ["industrials", "construction", "materials"],
        "defense": ["defense", "industrial"],
        "ai": ["technology", "semiconductors"],
        "war": ["defense", "energy"],
        "crude up": ["energy"],
        "supply chain": ["semiconductors", "industrials"],
    }

    for ev in macro_events:
        cat = (ev.category or "").lower()
        affected = (ev.affected_sectors or "").lower()
        if not affected and not cat:
            continue

        impact = float(ev.impact_score or 0.0)

        # Check bullish keyword match for this sector
        is_bullish = False
        for kw, sectors in BULLISH_FOR_SECTOR.items():
            if kw in cat or kw in (ev.title or "").lower():
                if any(s in sector_lower for s in sectors):
                    is_bullish = True
                    break

        # Match against affected_sectors (negative for the sector by default)
        is_bearish_match = any(tok in affected for tok in sector_lower.split())

        if is_bullish:
            score += min(15, impact * 25)
            reasons.append(f"+ {ev.title[:80]}")
        elif is_bearish_match:
            score -= min(15, impact * 20)
            reasons.append(f"- {ev.title[:80]}")

    score = max(0.0, min(100.0, score))
    return MacroScoreBreakdown(score, reasons[:4])


# ---------------- Liquidity (unchanged) ----------------

def score_liquidity(avg_volume: Optional[float], last_close: Optional[float]) -> LiquidityScoreBreakdown:
    if not avg_volume or not last_close:
        return LiquidityScoreBreakdown(20.0, None, ["unknown liquidity"])

    dollar_vol = float(avg_volume) * float(last_close)
    reasons = []

    if dollar_vol > 100_000_000:
        score = 95.0
        reasons.append(f"avg daily $vol ${dollar_vol/1e6:.0f}M")
    elif dollar_vol > 25_000_000:
        score = 80.0
    elif dollar_vol > 5_000_000:
        score = 60.0
    elif dollar_vol > 1_000_000:
        score = 35.0
        reasons.append("low liquidity (caution)")
    else:
        score = 15.0
        reasons.append(f"very illiquid (${dollar_vol/1e6:.1f}M/day)")

    return LiquidityScoreBreakdown(score, dollar_vol, reasons)


# ---------------- Squeeze risk (kept for schema compat) ----------------

def score_squeeze_risk(info, has_negative_catalyst: bool) -> SqueezeRiskBreakdown:
    """Not relevant for longs but preserved so existing schema/UI doesn't break."""
    if info is None:
        return SqueezeRiskBreakdown(0.0, "low", [])

    score = 0.0
    reasons = []

    pct = info.short_percent_of_float
    if pct is not None and pct > 0.20:
        score = 70.0
        reasons.append(f"short interest {pct*100:.1f}% of float")
        return SqueezeRiskBreakdown(score, "high", reasons)
    elif pct is not None and pct > 0.10:
        score = 40.0
        return SqueezeRiskBreakdown(score, "medium", reasons)

    return SqueezeRiskBreakdown(0.0, "low", [])


# Backward-compat aliases
score_fundamentals = score_fundamentals_long
score_macro = score_macro_long