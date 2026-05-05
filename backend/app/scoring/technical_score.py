"""Technical scoring for LONG bias.

v2 redesign: this module now exposes TWO entry points.

  - `score_technicals_long(snap)` — legacy 0-100 momentum/trend score.
    Kept for backward compatibility. Used as a fallback by services that
    import the dataclass shape (LLM templates, backtest).

  - `compute_setup_integrity(snap)` — STRUCTURE-based 0-100 score.
    No momentum compensation here: extension/timing penalties are
    applied as multipliers in engine.py. This score answers the
    question "does the price action have a clean structural setup?"
    and nothing else.

The integrity score is capped at 65 if no confirmed trend / breakout /
oversold-bounce structure exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.scoring.technicals import TechnicalSnapshot


@dataclass
class TechnicalScoreBreakdown:
    score: float
    confirmed_uptrend: bool
    confirmed_downtrend: bool
    has_breakout: bool
    has_oversold_bounce: bool
    has_insider_signal: bool
    has_sector_momentum: bool
    is_at_extreme_high: bool
    is_overextended: bool          # kept for schema compat with old code
    momentum_strongly_bullish: bool  # kept for schema compat
    has_breakdown: bool             # kept for schema compat
    has_failed_bounce: bool         # kept for schema compat
    reasons: list[str]


@dataclass
class SetupIntegrityBreakdown:
    score: float
    confirmed_uptrend: bool
    has_breakout: bool
    has_oversold_bounce: bool
    has_insider_signal: bool
    is_at_extreme_high: bool
    reasons: list[str]


def compute_setup_integrity(snap: Optional[TechnicalSnapshot]) -> SetupIntegrityBreakdown:
    """Score 0-100 based on PRICE ACTION STRUCTURE only.

    Excluded from this score (handled elsewhere):
      - 1-month performance / parabolic shape -> extension multiplier
      - Volume vs avg -> institutional_flow factor
      - 52w-high distance -> warnings + extension multiplier
    """
    if snap is None:
        return SetupIntegrityBreakdown(
            score=0.0,
            confirmed_uptrend=False,
            has_breakout=False,
            has_oversold_bounce=False,
            has_insider_signal=False,
            is_at_extreme_high=False,
            reasons=["no technical data"],
        )

    score = 50.0
    reasons: list[str] = []
    confirmed_uptrend = False
    has_breakout = False
    has_oversold_bounce = False
    has_insider_signal = False
    is_at_extreme_high = False

    last = snap.last_close

    # --- Trend confirmation (the core structural signal) ---
    above_sma50 = bool(snap.sma_50 and last > snap.sma_50)
    above_sma200 = bool(snap.sma_200 and last > snap.sma_200)
    bullish_ma_stack = bool(snap.sma_50 and snap.sma_200 and snap.sma_50 > snap.sma_200)

    if above_sma50 and above_sma200 and bullish_ma_stack:
        score += 22
        confirmed_uptrend = True
        reasons.append("price above SMA50 and SMA200 with bullish stacking")
    elif above_sma50 and above_sma200:
        score += 12
        reasons.append("price above both SMAs (early stacking)")
    elif above_sma50:
        score += 4
        reasons.append("above SMA50 only")

    # --- MACD bullish state ---
    if snap.macd is not None and snap.macd_signal is not None:
        if snap.macd > snap.macd_signal and snap.macd > 0:
            score += 8
            reasons.append("MACD bullish (above signal and above zero)")
        elif snap.macd > snap.macd_signal:
            score += 4
            reasons.append("MACD bullish cross (still under zero)")

    # --- RSI in healthy bullish zone ---
    if snap.rsi_14 is not None:
        rsi = snap.rsi_14
        if 55 <= rsi <= 70:
            score += 10
            reasons.append(f"RSI {rsi:.0f} in healthy bullish zone")
        elif 45 <= rsi < 55:
            score += 3
        elif 30 <= rsi < 45:
            # Possible oversold-bounce candidate
            if snap.change_5d is not None and snap.change_5d > 0:
                has_oversold_bounce = True
                score += 8
                reasons.append(f"oversold bounce in progress (RSI {rsi:.0f}, +{snap.change_5d:.1f}% 5d)")
            else:
                score += 3
        elif rsi > 75:
            is_at_extreme_high = True
            # Light penalty here; the heavy lift is in extension multiplier
            score -= 4
            reasons.append(f"RSI {rsi:.0f} extreme overbought")
        elif rsi < 30:
            score += 2

    # --- Breakout structure ---
    if snap.resistance_level and snap.relative_volume is not None:
        if last > snap.resistance_level * 1.01 and snap.relative_volume > 1.3:
            has_breakout = True
            score += 14
            reasons.append("breakout above resistance with volume")
        elif 0.99 <= (last / snap.resistance_level) <= 1.01 and snap.relative_volume > 1.2:
            has_breakout = True
            score += 8
            reasons.append("at resistance with rising volume (imminent breakout)")

    # --- Insider-buying-pattern proxy ---
    if (
        snap.change_5d is not None and snap.change_5d > 3
        and snap.relative_volume is not None and snap.relative_volume > 1.3
        and snap.rsi_14 is not None and 40 < snap.rsi_14 < 65
    ):
        has_insider_signal = True
        score += 6
        reasons.append("price/volume pattern consistent with accumulation")

    # --- 52w-high context (light penalty only) ---
    if snap.high_52w and last >= snap.high_52w * 0.98:
        is_at_extreme_high = True

    # Cap at 65 if no confirmed structural setup exists
    if not (confirmed_uptrend or has_breakout or has_oversold_bounce):
        score = min(score, 65.0)

    score = max(0.0, min(100.0, score))

    return SetupIntegrityBreakdown(
        score=score,
        confirmed_uptrend=confirmed_uptrend,
        has_breakout=has_breakout,
        has_oversold_bounce=has_oversold_bounce,
        has_insider_signal=has_insider_signal,
        is_at_extreme_high=is_at_extreme_high,
        reasons=reasons,
    )


def score_technicals_long(snap: Optional[TechnicalSnapshot]) -> TechnicalScoreBreakdown:
    """Legacy momentum-aware score. Kept for backward compatibility.

    The v2 engine uses `compute_setup_integrity` directly and applies
    extension penalties via multipliers. This function continues to
    return the older breakdown for callers that haven't migrated yet
    (services/llm.py template, tests).
    """
    if snap is None:
        return TechnicalScoreBreakdown(
            score=0.0,
            confirmed_uptrend=False, confirmed_downtrend=False,
            has_breakout=False, has_oversold_bounce=False,
            has_insider_signal=False, has_sector_momentum=False,
            is_at_extreme_high=False, is_overextended=False,
            momentum_strongly_bullish=False,
            has_breakdown=False, has_failed_bounce=False,
            reasons=["no technical data"],
        )

    integrity = compute_setup_integrity(snap)
    score = integrity.score

    # Detect a downtrend signal for legacy callers
    confirmed_downtrend = bool(
        snap.sma_50 and snap.sma_200
        and snap.last_close < snap.sma_50 * 0.98
        and snap.last_close < snap.sma_200 * 0.95
    )
    if confirmed_downtrend:
        score = max(0.0, score - 20)

    # Add a small momentum-aware adjustment for the legacy score
    if snap.change_1m is not None:
        if 5 < snap.change_1m < 20:
            score = min(100.0, score + 4)
        elif snap.change_1m > 30:
            score = max(0.0, score - 6)
        elif snap.change_1m < -10:
            score = max(0.0, score - 4)

    return TechnicalScoreBreakdown(
        score=score,
        confirmed_uptrend=integrity.confirmed_uptrend,
        confirmed_downtrend=confirmed_downtrend,
        has_breakout=integrity.has_breakout,
        has_oversold_bounce=integrity.has_oversold_bounce,
        has_insider_signal=integrity.has_insider_signal,
        has_sector_momentum=False,  # set by macro module / caller
        is_at_extreme_high=integrity.is_at_extreme_high,
        is_overextended=integrity.is_at_extreme_high,
        momentum_strongly_bullish=integrity.confirmed_uptrend,
        has_breakdown=False,
        has_failed_bounce=False,
        reasons=integrity.reasons,
    )


# Backward-compat alias
score_technicals = score_technicals_long
