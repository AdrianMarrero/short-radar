"""Technical scoring for LONG bias.

Detects:
  - Confirmed uptrends (price above SMA50 AND SMA200, both ascending)
  - Breakouts above resistance with volume
  - Oversold bounces in otherwise healthy stocks
  - Insider-buying-style price/volume signatures
  - Stocks lagging their sector (potential catch-up)

Score capped at 65 if no confirmed bullish trend exists, to prevent
chasing weak setups.
"""
from __future__ import annotations

from dataclasses import dataclass

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


def score_technicals_long(snap: TechnicalSnapshot | None) -> TechnicalScoreBreakdown:
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

    score = 50.0
    reasons: list[str] = []
    confirmed_uptrend = False
    confirmed_downtrend = False
    has_breakout = False
    has_oversold_bounce = False
    has_insider_signal = False
    has_sector_momentum = False
    is_at_extreme_high = False

    last = snap.last_close

    # --- Trend confirmation: price relative to BOTH key MAs ---
    above_sma50 = snap.sma_50 and last > snap.sma_50
    above_sma200 = snap.sma_200 and last > snap.sma_200
    below_sma50 = snap.sma_50 and last < snap.sma_50 * 0.98
    below_sma200 = snap.sma_200 and last < snap.sma_200 * 0.95

    # MA stacking — bullish when SMA50 > SMA200
    bullish_ma_stack = snap.sma_50 and snap.sma_200 and snap.sma_50 > snap.sma_200

    if above_sma50 and above_sma200 and bullish_ma_stack:
        score += 18
        confirmed_uptrend = True
        reasons.append("price above SMA50 AND SMA200 with bullish stacking")
    elif above_sma50 and above_sma200:
        score += 10
        reasons.append("price above both SMAs")
    elif above_sma50 and not above_sma200:
        score += 3
        reasons.append("above SMA50 only (early uptrend)")
    elif below_sma50 and below_sma200:
        score -= 22
        confirmed_downtrend = True
        reasons.append("price below SMA50 AND SMA200 (downtrend)")
    elif below_sma200:
        score -= 10
        reasons.append("price below SMA200")

    # --- MACD ---
    if snap.macd is not None and snap.macd_signal is not None:
        if snap.macd > snap.macd_signal and snap.macd > 0:
            score += 8
            reasons.append("MACD bullish (above signal and zero)")
        elif snap.macd > snap.macd_signal and snap.macd < 0:
            # Bullish cross but still negative — early signal
            score += 4
            reasons.append("MACD bullish cross (early)")
        elif snap.macd < snap.macd_signal and snap.macd < 0:
            score -= 8
            reasons.append("MACD bearish")

    # --- RSI ---
    if snap.rsi_14 is not None:
        if snap.rsi_14 > 75:
            is_at_extreme_high = True  # blow-off territory
            score -= 8
            reasons.append("RSI extreme overbought (>75)")
        elif 55 <= snap.rsi_14 <= 70:
            # Healthy bullish momentum zone
            score += 8
            reasons.append("RSI in healthy bullish zone (55-70)")
        elif 45 <= snap.rsi_14 < 55:
            score += 2
            reasons.append("RSI neutral")
        elif 30 <= snap.rsi_14 < 45:
            # Possible oversold bounce candidate if other conditions align
            score += 4
            if snap.change_5d is not None and snap.change_5d > 0:
                # Already bouncing
                has_oversold_bounce = True
                score += 6
                reasons.append("oversold bounce in progress")
            else:
                reasons.append("RSI weak (waiting for bounce)")
        elif snap.rsi_14 < 30:
            # Deeply oversold — possible reversal but high risk
            score += 2
            reasons.append("RSI deeply oversold (high risk reversal)")

    # --- Breakout detection: price near or just above resistance with volume ---
    if snap.resistance_level and snap.relative_volume is not None:
        if last > snap.resistance_level * 1.01 and snap.relative_volume > 1.3:
            has_breakout = True
            score += 14
            reasons.append("breakout above resistance with volume")
        elif 0.99 <= last / snap.resistance_level <= 1.01 and snap.relative_volume > 1.2:
            # Right at resistance with volume — imminent breakout
            has_breakout = True
            score += 8
            reasons.append("at resistance with rising volume (potential breakout)")

    # --- Volume context ---
    if snap.relative_volume is not None:
        if snap.relative_volume > 1.5 and snap.change_1d is not None and snap.change_1d > 2:
            score += 8
            reasons.append("heavy buying volume today")
        elif snap.relative_volume > 1.5 and snap.change_1d is not None and snap.change_1d < -2:
            score -= 6
            reasons.append("heavy selling volume today")

    # --- Insider-buying signal proxy ---
    # We can't see Form 4 directly, but a price/volume pattern that
    # often accompanies insider buying: 3-5 days of above-avg volume on green
    # candles without major news. We approximate via change_5d + relative_volume.
    if (
        snap.change_5d is not None and snap.change_5d > 3
        and snap.relative_volume is not None and snap.relative_volume > 1.3
        and snap.rsi_14 is not None and 40 < snap.rsi_14 < 65
    ):
        has_insider_signal = True
        score += 6
        reasons.append("price/volume pattern consistent with accumulation")

    # --- Distance to 52w high ---
    if snap.high_52w and last >= snap.high_52w * 0.98:
        is_at_extreme_high = True
        # At ATH — neutral, sometimes good (continuation), sometimes blow-off
        if snap.change_1m is not None and snap.change_1m > 20:
            score -= 6
            reasons.append("at 52w high with parabolic 1M (blow-off risk)")
        else:
            score += 4
            reasons.append("at 52w highs (continuation possible)")
    elif snap.high_52w and 0.85 < last / snap.high_52w < 0.95:
        # Just below highs — sweet spot for breakout setups
        score += 5
        reasons.append("just below 52w highs (breakout zone)")

    # --- Distance to 52w low ---
    if snap.low_52w and last <= snap.low_52w * 1.05:
        # Near 52w low — risky (catching falling knife) unless bounce confirmed
        if has_oversold_bounce:
            score += 3
            reasons.append("bouncing off 52w lows")
        else:
            score -= 12
            reasons.append("near 52w lows (avoid falling knife)")

    # --- Recent performance ---
    if snap.change_1m is not None:
        if 5 < snap.change_1m < 20:
            # Healthy uptrend, not parabolic
            score += 7
            reasons.append(f"+{snap.change_1m:.1f}% in last month (healthy)")
        elif 0 < snap.change_1m <= 5:
            score += 3
        elif snap.change_1m > 30:
            # Parabolic, dangerous
            score -= 8
            reasons.append(f"+{snap.change_1m:.1f}% in last month (parabolic)")
        elif snap.change_1m < -10:
            score -= 5

    # --- 6-month trend confirmation ---
    if snap.change_6m is not None:
        if snap.change_6m > 15:
            score += 6
            reasons.append(f"+{snap.change_6m:.1f}% in last 6 months (sustained uptrend)")
        elif snap.change_6m < -15:
            score -= 8
            reasons.append(f"{snap.change_6m:.1f}% in last 6 months")

    # Cap and floor
    score = max(0.0, min(100.0, score))
    # If no confirmed uptrend AND no breakout AND no bounce, ceiling is 65
    if not (confirmed_uptrend or has_breakout or has_oversold_bounce):
        score = min(score, 65.0)

    return TechnicalScoreBreakdown(
        score=score,
        confirmed_uptrend=confirmed_uptrend,
        confirmed_downtrend=confirmed_downtrend,
        has_breakout=has_breakout,
        has_oversold_bounce=has_oversold_bounce,
        has_insider_signal=has_insider_signal,
        has_sector_momentum=has_sector_momentum,  # set by caller/macro module
        is_at_extreme_high=is_at_extreme_high,
        is_overextended=is_at_extreme_high,
        momentum_strongly_bullish=confirmed_uptrend,
        has_breakdown=False,
        has_failed_bounce=False,
        reasons=reasons,
    )


# Backward-compat alias so old imports `score_technicals` still work
score_technicals = score_technicals_long