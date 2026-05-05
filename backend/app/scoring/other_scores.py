"""Fundamental, macro, liquidity and squeeze-risk scores — LONG-BIAS edition.

v2 redesign: this module now exposes additional 0-100 factor functions
used by the new weighted-score formula in engine.py:

  - score_quality_long / compute_quality_score: fundamentals quality factor
  - compute_mean_reversion_score: oversold-bounce setup factor
  - compute_macro_sector_score: macro-tailwind factor (re-uses score_macro_long)
  - compute_institutional_flow_score: volume/price accumulation proxy
  - compute_vol_regime_score: ATR + realized-vol regime factor

Liquidity is still scored 0-100 (kept for backward compat with
ranking.py and DB columns) but in v2 it primarily feeds the LIQUIDITY
GATE in gates.py rather than the weighted score.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Iterable

from app.scoring.technicals import TechnicalSnapshot


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


def _finite(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ---------------- Fundamentals (LONG bias) ----------------

def score_fundamentals_long(info) -> FundamentalScoreBreakdown:
    """Higher = healthier company = better long candidate."""
    if info is None:
        return FundamentalScoreBreakdown(50.0, False, False, ["no fundamentals data"])

    score = 50.0
    reasons: list[str] = []
    deteriorating = False
    growing = False

    rev_growth = _finite(getattr(info, "revenue_growth_yoy", None))
    op_margin = _finite(getattr(info, "operating_margin", None))
    fcf = _finite(getattr(info, "free_cash_flow", None))
    debt = _finite(getattr(info, "total_debt", None)) or 0.0
    cash = _finite(getattr(info, "total_cash", None)) or 0.0
    pe = _finite(getattr(info, "pe", None))
    eps = _finite(getattr(info, "eps", None))

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


def compute_quality_score(info) -> float:
    """v2 quality factor (0-100). Combines profitability, balance sheet,
    capital efficiency and (when available) margin trend.

    Robust to None / NaN fields — yfinance returns missing data for
    European tickers frequently. Each block degrades to neutral if its
    inputs are missing.

    Components:
      - FCF yield (free cash flow / market cap): up to +20
      - ROIC proxy (operating margin × asset turnover): up to +18
      - Debt/Equity (proxy via debt/cash): up to +14 (or up to -12 if levered)
      - Gross margin trend (if available): up to +8
      - Revenue growth: up to +12 (positive) or down to -10 (negative)
      - Operating margin level: up to +12
    """
    if info is None:
        return 50.0

    score = 50.0

    op_margin = _finite(getattr(info, "operating_margin", None))
    gross_margin = _finite(getattr(info, "gross_margin", None))
    rev_growth = _finite(getattr(info, "revenue_growth_yoy", None))
    fcf = _finite(getattr(info, "free_cash_flow", None))
    market_cap = _finite(getattr(info, "market_cap", None))
    revenue = _finite(getattr(info, "revenue", None))
    debt = _finite(getattr(info, "total_debt", None))
    cash = _finite(getattr(info, "total_cash", None))

    # FCF yield — top decile starts ~5%; >8% is exceptional
    if fcf is not None and market_cap is not None and market_cap > 0:
        fcf_yield = fcf / market_cap
        if math.isfinite(fcf_yield):
            if fcf_yield > 0.08:
                score += 20
            elif fcf_yield > 0.04:
                score += 12
            elif fcf_yield > 0.01:
                score += 5
            elif fcf_yield < 0:
                score -= 8

    # ROIC proxy (operating_margin × asset_turnover ~= revenue/(debt+cash))
    if op_margin is not None and revenue is not None:
        capital_proxy = (debt or 0.0) + (cash or 0.0)
        if capital_proxy > 0:
            asset_turnover = revenue / capital_proxy
            if math.isfinite(asset_turnover):
                roic = op_margin * asset_turnover
                if math.isfinite(roic):
                    if roic > 0.20:
                        score += 18
                    elif roic > 0.10:
                        score += 10
                    elif roic > 0.04:
                        score += 4

    # Debt / Equity-ish via debt/cash. Without book equity, use debt vs cash.
    if debt is not None and cash is not None:
        if cash > 0:
            de = debt / cash
            if math.isfinite(de):
                if de < 0.5:
                    score += 14
                elif de < 1.0:
                    score += 6
                elif de > 4.0:
                    score -= 12
                elif de > 2.0:
                    score -= 4

    # Operating margin level
    if op_margin is not None:
        if op_margin > 0.25:
            score += 12
        elif op_margin > 0.15:
            score += 6
        elif op_margin < 0:
            score -= 8

    # Gross margin (level — yfinance doesn't expose trend without history)
    if gross_margin is not None:
        if gross_margin > 0.45:
            score += 8
        elif gross_margin > 0.25:
            score += 3

    # Revenue growth
    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 12
        elif rev_growth > 0.08:
            score += 6
        elif rev_growth < -0.05:
            score -= 10

    score = max(0.0, min(100.0, score))
    return score


# ---------------- Mean reversion factor ----------------

def compute_mean_reversion_score(snap: Optional[TechnicalSnapshot], info) -> float:
    """0-100 factor. High = oversold bounce setup in a healthy stock.

    Components:
      +30 if RSI < 40 AND a recent +5d uptick (bounce in progress)
      +20 if price near 52w low AND fundamentals not deteriorating
      +20 if price within 2% of SMA50 from below (reclaim setup)
      +10 if price below both SMAs (deeper setup, more risk)
    """
    if snap is None:
        return 50.0

    score = 50.0
    rsi = snap.rsi_14
    last = snap.last_close
    change_5d = snap.change_5d

    if rsi is not None and rsi < 40 and change_5d is not None and change_5d > 0:
        score += 30

    if snap.low_52w and last:
        proximity = (last - snap.low_52w) / max(1e-9, snap.low_52w)
        deteriorating = bool(getattr(info, "deteriorating", False)) if info else False
        if proximity < 0.12 and not deteriorating:
            score += 20

    if snap.sma_50:
        rel = (last - snap.sma_50) / snap.sma_50
        if -0.03 <= rel <= 0.0:
            score += 20

    if snap.sma_50 and snap.sma_200 and last < snap.sma_50 and last < snap.sma_200:
        score += 10

    return max(0.0, min(100.0, score))


# ---------------- Macro (LONG bias) ----------------

def score_macro_long(sector: str, macro_events: Iterable) -> MacroScoreBreakdown:
    """Macro for longs.

    Bullish events for the stock's sector raise the score.
    Bearish events for the sector lower it.
    """
    if not sector:
        return MacroScoreBreakdown(50.0, [])

    score = 50.0
    reasons: list[str] = []
    sector_lower = sector.lower()

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

        is_bullish = False
        for kw, sectors in BULLISH_FOR_SECTOR.items():
            if kw in cat or kw in (ev.title or "").lower():
                if any(s in sector_lower for s in sectors):
                    is_bullish = True
                    break

        is_bearish_match = any(tok in affected for tok in sector_lower.split())

        if is_bullish:
            score += min(15, impact * 25)
            reasons.append(f"+ {ev.title[:80]}")
        elif is_bearish_match:
            score -= min(15, impact * 20)
            reasons.append(f"- {ev.title[:80]}")

    score = max(0.0, min(100.0, score))
    return MacroScoreBreakdown(score, reasons[:4])


def compute_macro_sector_score(sector: str, macro_events: Iterable) -> float:
    """0-100 macro factor. Wraps score_macro_long for the v2 engine."""
    return score_macro_long(sector, macro_events).score


def detect_sector_momentum(sector: str, macro_events: Iterable) -> bool:
    """True if the sector has at least one bullish macro tailwind."""
    breakdown = score_macro_long(sector, macro_events)
    return breakdown.score >= 60.0


# ---------------- Institutional flow factor ----------------

def compute_institutional_flow_score(snap: Optional[TechnicalSnapshot]) -> float:
    """0-100 factor based on volume/price patterns suggestive of
    institutional accumulation.

    Components:
      Relative volume: above 1.3x = accumulation evidence
      Price uptick on rising volume: bullish confirmation
      Volume below 0.7x: distribution or apathy (negative)
    """
    if snap is None:
        return 50.0

    score = 50.0
    rv = snap.relative_volume
    c1d = snap.change_1d
    c5d = snap.change_5d

    if rv is not None:
        if rv >= 1.8:
            score += 20
        elif rv >= 1.3:
            score += 12
        elif rv < 0.7:
            score -= 6

    # Up-day on volume
    if rv is not None and rv > 1.2 and c1d is not None and c1d > 0:
        score += 10
    # Sustained 5d move with elevated volume
    if rv is not None and rv > 1.1 and c5d is not None and c5d > 2.5:
        score += 8

    # Healthy MA proximity (institutions defending the level)
    if snap.sma_50 and snap.last_close:
        rel = (snap.last_close - snap.sma_50) / snap.sma_50
        if 0.0 <= rel <= 0.04:
            score += 6

    return max(0.0, min(100.0, score))


# ---------------- Vol regime factor ----------------

def compute_vol_regime_score(snap: Optional[TechnicalSnapshot]) -> float:
    """0-100 factor. High = manageable volatility regime for retail.

    Penalizes:
      - High realized vol (>0.55 annualized)
      - High ATR % (>5%)
      - Parabolic shape
    Rewards low/normal vol regimes.
    """
    if snap is None:
        return 50.0

    score = 70.0
    rv = snap.realized_vol_30d
    atr_pct = snap.atr_pct

    if rv is not None:
        if rv <= 0.20:
            score += 15
        elif rv <= 0.35:
            score += 5
        elif rv <= 0.55:
            score -= 5
        else:
            score -= 18

    if atr_pct is not None:
        a = atr_pct * 100.0
        if a <= 2.5:
            score += 8
        elif a <= 4.5:
            score += 0
        elif a <= 7.0:
            score -= 8
        else:
            score -= 18

    if getattr(snap, "is_parabolic_30d", False):
        score -= 15

    return max(0.0, min(100.0, score))


# ---------------- RR factor ----------------

def compute_rr_factor_score(rr: Optional[float]) -> float:
    """0-100 factor mapped from the trade-plan risk/reward ratio.

    Schedule:
      rr unknown:  40
      rr <= 1.0:   20
      rr 1.5:      55
      rr 2.0:      75
      rr 3.0:      90
      rr >= 4.0:  100
    """
    if rr is None:
        return 40.0
    r = float(rr)
    if not math.isfinite(r):
        return 40.0
    if r <= 1.0:
        return 20.0
    if r <= 1.5:
        return 20.0 + (r - 1.0) / 0.5 * 35.0  # 20 -> 55
    if r <= 2.0:
        return 55.0 + (r - 1.5) / 0.5 * 20.0  # 55 -> 75
    if r <= 3.0:
        return 75.0 + (r - 2.0) / 1.0 * 15.0  # 75 -> 90
    if r <= 4.0:
        return 90.0 + (r - 3.0) / 1.0 * 10.0  # 90 -> 100
    return 100.0


# ---------------- Liquidity (kept for gate + score column) ----------------

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


def compute_liquidity_score(avg_volume: Optional[float], last_close: Optional[float]) -> float:
    """Numeric helper for the gate / engine — score component only."""
    return score_liquidity(avg_volume, last_close).score


# ---------------- Squeeze risk (kept for schema compat) ----------------

def score_squeeze_risk(info, has_negative_catalyst: bool) -> SqueezeRiskBreakdown:
    """Not relevant for longs but preserved so existing schema/UI doesn't break."""
    if info is None:
        return SqueezeRiskBreakdown(0.0, "low", [])

    score = 0.0
    reasons = []

    pct = _finite(getattr(info, "short_percent_of_float", None))
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
score_quality_long = compute_quality_score
