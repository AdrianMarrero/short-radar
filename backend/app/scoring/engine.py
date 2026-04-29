"""Master scoring engine — LONG-BIAS edition.

Score 0-100, where higher = better LONG candidate (price likely to rise).
The engine produces two parallel evaluations:

  - Conservative profile: confirmed uptrend, healthy fundamentals,
    no near-term binary risk. Goal: +5/+12% in 3-6 weeks, win rate ~60%.

  - Aggressive profile: emerging breakouts, recent positive catalysts
    still digesting, sector momentum, insider buying signals.
    Goal: +10/+25% in 2-4 weeks, win rate ~45%, wider stops.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from app.core.config import get_settings
from app.scoring.technicals import TechnicalSnapshot
from app.scoring.technical_score import TechnicalScoreBreakdown, score_technicals_long
from app.scoring.news_score import NewsScoreBreakdown, score_news_long
from app.scoring.other_scores import (
    FundamentalScoreBreakdown, score_fundamentals_long,
    MacroScoreBreakdown, score_macro_long,
    LiquidityScoreBreakdown, score_liquidity,
    SqueezeRiskBreakdown, score_squeeze_risk,
)

settings = get_settings()


# Risk parameters for long trades (retail with limited capital)
MAX_STOP_PCT = 0.07      # max 7% below entry
MIN_STOP_PCT = 0.03      # min 3% below entry (under this, noise stops you out)
MAX_TARGET_PCT = 0.25    # max 25% target on aggressive setups
MIN_RISK_REWARD = 1.5    # below this we mark the setup as low quality


@dataclass
class TradePlan:
    entry: Optional[float]
    stop: Optional[float]
    target_1: Optional[float]
    target_2: Optional[float]
    risk_reward: Optional[float]
    invalidation: str


@dataclass
class FinalScore:
    total: float
    technical: TechnicalScoreBreakdown
    news: NewsScoreBreakdown
    fundamental: FundamentalScoreBreakdown
    macro: MacroScoreBreakdown
    liquidity: LiquidityScoreBreakdown
    squeeze: SqueezeRiskBreakdown   # not used in longs but kept for schema compat
    setup_type: str
    conviction: str
    horizon: str
    profile: str                    # "conservative" / "aggressive" / "none"
    trade_plan: TradePlan

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "technical": asdict(self.technical),
            "news": asdict(self.news),
            "fundamental": asdict(self.fundamental),
            "macro": asdict(self.macro),
            "liquidity": asdict(self.liquidity),
            "squeeze": asdict(self.squeeze),
            "setup_type": self.setup_type,
            "conviction": self.conviction,
            "horizon": self.horizon,
            "profile": self.profile,
            "trade_plan": asdict(self.trade_plan),
        }


def _build_long_plan(snap: TechnicalSnapshot, tech: TechnicalScoreBreakdown, profile: str) -> TradePlan:
    """Long trade plan with bounded stops and targets.

    Conservative: tight stop (3-5%), modest targets (5-12%).
    Aggressive: wider stop (5-7%), higher targets (10-25%).
    """
    if snap is None:
        return TradePlan(None, None, None, None, None, "no technical data")

    last = snap.last_close
    atr = snap.atr_14 or (last * 0.02)

    # Entry: at current price for trend-following, slight pullback for breakouts
    entry = last
    invalidation = ""

    if tech.has_breakout and snap.resistance_level:
        # Just broke through resistance, ideal entry is at retest
        entry = max(last, snap.resistance_level * 1.005)
        invalidation = "daily close back below broken resistance"
    elif tech.confirmed_uptrend:
        invalidation = "daily close below SMA50 with volume"
    else:
        invalidation = "trend reversal with volume"

    # --- Stop: below support level OR ATR-based, capped ---
    stop_atr = entry - atr * (1.5 if profile == "conservative" else 2.0)
    stop_support = None
    if snap.support_level and snap.support_level < entry * 0.99:
        # Use support if within MAX_STOP_PCT of entry
        if snap.support_level >= entry * (1 - MAX_STOP_PCT):
            stop_support = snap.support_level * 0.99

    # Pick the tighter stop (higher = less risk)
    candidates = [stop_atr]
    if stop_support:
        candidates.append(stop_support)
    stop = max(candidates)

    # Apply hard bounds
    min_stop = entry * (1 - MAX_STOP_PCT)
    max_stop = entry * (1 - MIN_STOP_PCT)
    stop = min(max(stop, min_stop), max_stop)

    risk = entry - stop
    if risk <= 0:
        return TradePlan(round(entry, 2), None, None, None, None, invalidation)

    # --- Targets ---
    if profile == "conservative":
        # Modest targets: 1.5R and 2.5R, capped at 8% / 14%
        t1_pct = min(1.5 * risk / entry, 0.08)
        t2_pct = min(2.5 * risk / entry, 0.14)
    else:  # aggressive
        # Bigger targets: 2R and 4R, capped at 12% / 25%
        t1_pct = min(2.0 * risk / entry, 0.12)
        t2_pct = min(4.0 * risk / entry, 0.25)

    t1 = entry * (1 + t1_pct)
    t2 = entry * (1 + t2_pct)

    # If 52w high is between t1 and t2, use it as a meaningful waypoint
    if snap.high_52w and t1 < snap.high_52w < t2:
        t1 = snap.high_52w

    rr = round((t2 - entry) / risk, 2)

    return TradePlan(
        entry=round(entry, 2),
        stop=round(stop, 2),
        target_1=round(t1, 2),
        target_2=round(t2, 2),
        risk_reward=rr,
        invalidation=invalidation,
    )


def _classify_profile(
    tech: TechnicalScoreBreakdown,
    news: NewsScoreBreakdown,
    fund: FundamentalScoreBreakdown,
    total: float,
) -> str:
    """Decide whether this candidate is conservative, aggressive, or none.

    Conservative requires:
      - Confirmed uptrend (price above SMA50 AND SMA200)
      - Healthy fundamentals (no deterioration flags)
      - No major negative catalyst recent
      - Total score >= 65
      - NO upcoming earnings risk (handled in setup_type)

    Aggressive requires:
      - Either: emerging breakout with volume
      - Or: positive catalyst still digesting (3-10 days old)
      - Or: insider buying detected
      - Or: strong sector momentum with the stock lagging
      - Total score >= 60 (we accept lower confirmation in exchange for upside)
    """
    # Conservative path: trend-following with full confirmation
    if (
        tech.confirmed_uptrend
        and not fund.deteriorating
        and not news.has_negative_catalyst
        and total >= 65
        and not tech.is_at_extreme_high  # don't chase blow-off tops
    ):
        return "conservative"

    # Aggressive path: catalyst-driven or momentum-emerging
    if (
        total >= 60
        and (news.has_positive_catalyst or tech.has_breakout or tech.has_insider_signal or tech.has_sector_momentum)
        and not fund.deteriorating
    ):
        return "aggressive"

    return "none"


def _classify_setup_long(tech: TechnicalScoreBreakdown, news: NewsScoreBreakdown, fund: FundamentalScoreBreakdown) -> str:
    """Setup type for long bias.

    Returns: trend / breakout / catalyst / reversion / momentum / none
    """
    if news.has_positive_catalyst:
        return "catalyst"
    if tech.has_breakout:
        return "breakout"
    if tech.confirmed_uptrend and not fund.deteriorating:
        return "trend"
    if tech.has_oversold_bounce:
        return "reversion"
    if tech.has_sector_momentum:
        return "momentum"
    return "none"


def _conviction(total: float, plan: TradePlan, tech: TechnicalScoreBreakdown, profile: str) -> str:
    if profile == "none":
        return "low"

    rr = plan.risk_reward or 0

    if profile == "conservative":
        if total >= 75 and rr >= 2.0 and tech.confirmed_uptrend:
            return "high"
        if total >= 65 and rr >= MIN_RISK_REWARD:
            return "medium"
        return "low"
    else:  # aggressive
        if total >= 75 and rr >= 2.5:
            return "high"
        if total >= 65 and rr >= 1.8:
            return "medium"
        return "low"


def _horizon(profile: str, setup: str) -> str:
    if profile == "aggressive":
        if setup in ("catalyst", "breakout"):
            return "swing"        # 1-3 weeks
        return "swing"
    # Conservative
    if setup == "trend":
        return "positional"       # 4-8 weeks
    return "swing"


def compute_final_score(
    snap: TechnicalSnapshot | None,
    news_items,
    info,
    macro_events,
    avg_volume: Optional[float],
) -> FinalScore:
    tech = score_technicals_long(snap)
    news = score_news_long(news_items or [])
    fund = score_fundamentals_long(info)
    sector = info.sector if info else ""
    macro = score_macro_long(sector, macro_events or [])
    liq = score_liquidity(avg_volume, snap.last_close if snap else None)
    squeeze = score_squeeze_risk(info, news.has_negative_catalyst)  # informational

    raw = (
        tech.score      * settings.weight_technical
        + news.score    * settings.weight_news
        + fund.score    * settings.weight_fundamental
        + macro.score   * settings.weight_macro
        + liq.score     * settings.weight_liquidity
    )

    # --- Penalties ---
    # Negative catalyst kills the long thesis
    if news.has_negative_catalyst:
        raw -= 25

    # Strong bearish momentum (price below both MAs in falling MA structure)
    if tech.confirmed_downtrend:
        raw -= 30

    # Very low liquidity -> avoid (US blue chips should never hit this)
    if liq.score < 40:
        raw -= 30

    # Already extended at 52w high without earnings/catalyst behind it
    if tech.is_at_extreme_high and not news.has_positive_catalyst:
        raw -= 10

    # Deteriorating fundamentals -> reduce, even if technical is positive
    if fund.deteriorating:
        raw -= 12

    raw = max(0.0, min(100.0, raw))

    profile = _classify_profile(tech, news, fund, raw)
    setup = _classify_setup_long(tech, news, fund)
    plan = _build_long_plan(snap, tech, profile if profile != "none" else "conservative") if snap else TradePlan(None, None, None, None, None, "no data")
    conv = _conviction(raw, plan, tech, profile)
    hor = _horizon(profile, setup)

    return FinalScore(
        total=round(raw, 1),
        technical=tech,
        news=news,
        fundamental=fund,
        macro=macro,
        liquidity=liq,
        squeeze=squeeze,
        setup_type=setup,
        conviction=conv,
        horizon=hor,
        profile=profile,
        trade_plan=plan,
    )