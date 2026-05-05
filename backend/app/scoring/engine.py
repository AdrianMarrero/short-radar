"""Master scoring engine — LONG-BIAS edition, v2 redesign.

Three-layer model:

  1. Hard gates (gates.py). If any gate fails -> RejectedScore.
  2. Weighted raw score over 8 factors (no momentum compensation in
     the factor scores; extension is handled as a multiplier).
  3. Multiplicative penalties (multipliers.py): final = raw × ext × tim × vol.

Backwards-compatible: returns the legacy ``FinalScore`` dataclass so that
``services/llm.py`` and ``jobs/daily.py`` keep working — but the score
now reflects the v2 logic and ``raw_score_data`` (a flat dict) carries
factor scores, multipliers, tier, category, warnings, explanation.

Conviction is derived from tier (A+/A -> high, B -> medium, C/D -> low).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from app.core.config import get_settings
from app.scoring.technicals import TechnicalSnapshot
from app.scoring.technical_score import (
    TechnicalScoreBreakdown,
    score_technicals_long,
    compute_setup_integrity,
)
from app.scoring.news_score import (
    NewsScoreBreakdown,
    score_news_long,
    compute_catalyst_score,
)
from app.scoring.other_scores import (
    FundamentalScoreBreakdown,
    score_fundamentals_long,
    MacroScoreBreakdown,
    score_macro_long,
    LiquidityScoreBreakdown,
    score_liquidity,
    SqueezeRiskBreakdown,
    score_squeeze_risk,
    compute_quality_score,
    compute_mean_reversion_score,
    compute_macro_sector_score,
    compute_institutional_flow_score,
    compute_vol_regime_score,
    compute_rr_factor_score,
    detect_sector_momentum,
)
from app.scoring.gates import check_all_gates, GatesResult
from app.scoring.multipliers import (
    compute_extension_multiplier,
    compute_timing_multiplier,
    compute_vol_anchor_multiplier,
)
from app.scoring.categories import classify_category_long
from app.scoring.tiers import assign_tier_single
from app.scoring.explanations import (
    generate_warnings,
    generate_explanation_bullets,
)
from app.scoring.edge_factors import (
    compute_target_premium,
    compute_earnings_momentum,
    compute_insider_flow,
    compute_short_int_delta,
    regime_multiplier,
)

settings = get_settings()


# Risk parameters for long trades (retail with limited capital)
MAX_STOP_PCT = 0.07
MIN_STOP_PCT = 0.03
MAX_TARGET_PCT = 0.25
MIN_RISK_REWARD = 1.5


# v3 factor weights (sum = 1.00). New ``earnings_momentum`` factor gets
# 8 percentage points; the budget is taken from ``catalyst`` (12 -> 8) and
# ``mean_reversion`` (10 -> 6).
FACTOR_WEIGHTS = {
    "quality": 0.22,
    "setup_integrity": 0.18,
    "rr": 0.15,
    "catalyst": 0.08,
    "mean_reversion": 0.06,
    "macro_sector": 0.08,
    "institutional_flow": 0.08,
    "vol_regime": 0.07,
    "earnings_momentum": 0.08,
}


def _safe_dict(d) -> dict:
    """Coerce a dict's values into JSON-safe types (no NaN/Inf).

    Used to scrub the edge-factor sub-dicts that get stored in
    ``raw_score_data``. Booleans, ints, strings, lists are passed
    through as-is; floats are clamped to None when not finite.
    """
    import math as _math
    if d is None:
        return {}
    out = {}
    for k, v in d.items():
        if isinstance(v, float):
            out[k] = v if _math.isfinite(v) else None
        elif isinstance(v, dict):
            out[k] = _safe_dict(v)
        else:
            out[k] = v
    return out


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
    """v2 result — backward-compatible shape (legacy callers consume
    ``technical``/``news``/``fundamental``/etc.) plus v2 fields under
    ``raw_score_data``.
    """
    total: float
    technical: TechnicalScoreBreakdown
    news: NewsScoreBreakdown
    fundamental: FundamentalScoreBreakdown
    macro: MacroScoreBreakdown
    liquidity: LiquidityScoreBreakdown
    squeeze: SqueezeRiskBreakdown
    setup_type: str
    conviction: str
    horizon: str
    profile: str                          # legacy "conservative"/"aggressive"/"none"
    trade_plan: TradePlan
    # v2 additions
    rejected: bool = False
    rejection_reasons: list[str] = field(default_factory=list)
    factor_scores: dict = field(default_factory=dict)
    multipliers: dict = field(default_factory=dict)
    category: Optional[str] = None
    tier: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    extension_status: Optional[str] = None
    entry_zone_status: Optional[str] = None
    perf_1m_pct: Optional[float] = None
    raw_score_data: dict = field(default_factory=dict)

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
            "rejected": self.rejected,
            "rejection_reasons": list(self.rejection_reasons),
            "factor_scores": dict(self.factor_scores),
            "multipliers": dict(self.multipliers),
            "category": self.category,
            "tier": self.tier,
            "warnings": list(self.warnings),
            "explanation": list(self.explanation),
            "extension_status": self.extension_status,
            "entry_zone_status": self.entry_zone_status,
            "perf_1m_pct": self.perf_1m_pct,
        }


# ---------- Trade plan ----------

def _build_long_plan(
    snap: TechnicalSnapshot,
    tech: TechnicalScoreBreakdown,
    profile: str,
) -> TradePlan:
    """Long trade plan with bounded stops and targets. Same logic as v1."""
    if snap is None:
        return TradePlan(None, None, None, None, None, "no technical data")

    last = snap.last_close
    atr = snap.atr_14 or (last * 0.02)

    entry = last
    invalidation = ""

    if tech.has_breakout and snap.resistance_level:
        entry = max(last, snap.resistance_level * 1.005)
        invalidation = "daily close back below broken resistance"
    elif tech.confirmed_uptrend:
        invalidation = "daily close below SMA50 with volume"
    else:
        invalidation = "trend reversal with volume"

    stop_atr = entry - atr * (1.5 if profile == "conservative" else 2.0)
    stop_support = None
    if snap.support_level and snap.support_level < entry * 0.99:
        if snap.support_level >= entry * (1 - MAX_STOP_PCT):
            stop_support = snap.support_level * 0.99

    candidates = [stop_atr]
    if stop_support:
        candidates.append(stop_support)
    stop = max(candidates)

    min_stop = entry * (1 - MAX_STOP_PCT)
    max_stop = entry * (1 - MIN_STOP_PCT)
    stop = min(max(stop, min_stop), max_stop)

    risk = entry - stop
    if risk <= 0:
        return TradePlan(round(entry, 2), None, None, None, None, invalidation)

    if profile == "conservative":
        t1_pct = min(1.5 * risk / entry, 0.08)
        t2_pct = min(2.5 * risk / entry, 0.14)
    else:
        t1_pct = min(2.0 * risk / entry, 0.12)
        t2_pct = min(4.0 * risk / entry, 0.25)

    t1 = entry * (1 + t1_pct)
    t2 = entry * (1 + t2_pct)

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


def _classify_setup_long(
    tech: TechnicalScoreBreakdown,
    news: NewsScoreBreakdown,
    fund: FundamentalScoreBreakdown,
) -> str:
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


def _profile_from_category(category: Optional[str]) -> str:
    """Map v2 category to the legacy ``profile`` field for backward compat
    with code paths that still read ``fs.profile``.
    """
    if category in ("investment",):
        return "conservative"
    if category in ("speculative", "cyclical"):
        return "aggressive"
    if category in ("swing_trade",):
        return "conservative"
    return "none"


def _conviction_from_tier(tier: Optional[str]) -> str:
    if tier in ("A+", "A"):
        return "high"
    if tier == "B":
        return "medium"
    return "low"


def _horizon(profile: str, setup: str) -> str:
    if profile == "aggressive":
        return "swing"
    if setup == "trend":
        return "positional"
    return "swing"


def _extension_status(perf_1m: Optional[float]) -> str:
    if perf_1m is None:
        return "ok"
    if perf_1m <= 5.0:
        return "ok"
    if perf_1m <= 15.0:
        return "warming"
    if perf_1m <= 25.0:
        return "extended"
    return "very_late"


def _entry_zone_status(
    last_close: Optional[float],
    entry: Optional[float],
) -> str:
    if last_close is None or entry is None or entry <= 0:
        return "green"
    pct = (last_close - entry) / entry * 100.0
    if pct <= 0.5:
        return "green"
    if pct <= 2.0:
        return "yellow"
    if pct <= 5.0:
        return "orange"
    return "red"


# ---------- Main entry point ----------

def compute_final_score(
    snap: TechnicalSnapshot | None,
    news_items,
    info,
    macro_events,
    avg_volume: Optional[float],
    *,
    beta: Optional[float] = None,
    insider_df=None,
    short_rows: Optional[list] = None,
    macro_regime: Optional[dict] = None,
) -> FinalScore:
    """v2/v3 compute. Returns FinalScore (rejected when gates fail).

    v3 additions (all optional, all degrade safely to v2 behavior when
    not provided):
      - ``insider_df``: yfinance insider_transactions DataFrame for the
        ticker. Fed into the institutional_flow factor.
      - ``short_rows``: list of ShortData rows for the ticker (~30d).
        Fed into the institutional_flow factor.
      - ``macro_regime``: result of edge_factors.detect_macro_regime()
        (computed ONCE per daily run, passed to every ticker). When
        provided, applied as a 4th multiplier alongside extension,
        timing, vol_anchor.
    """
    # Always run breakdowns we need for legacy compat fields
    tech_legacy = score_technicals_long(snap)
    news_breakdown = score_news_long(news_items or [])
    fund = score_fundamentals_long(info)
    sector = info.sector if info else ""
    macro = score_macro_long(sector, macro_events or [])
    liq = score_liquidity(avg_volume, snap.last_close if snap else None)
    squeeze = score_squeeze_risk(info, news_breakdown.has_negative_catalyst)

    setup = _classify_setup_long(tech_legacy, news_breakdown, fund)
    has_sector_mom = detect_sector_momentum(sector, macro_events or [])

    # Build a preliminary trade plan to evaluate the RR / chase gates.
    tentative_profile = "conservative"
    plan = (
        _build_long_plan(snap, tech_legacy, tentative_profile)
        if snap else TradePlan(None, None, None, None, None, "no data")
    )

    perf_1m = snap.perf_1m_pct if snap else None
    last_close = snap.last_close if snap else None
    avg_dollar_vol = snap.dollar_volume_30d if snap else None
    if avg_dollar_vol is None and avg_volume and last_close:
        avg_dollar_vol = float(avg_volume) * float(last_close)

    # ---- Layer 1: Gates ----
    gates = check_all_gates(
        snap=snap,
        avg_dollar_vol_30d=avg_dollar_vol,
        perf_1m_pct=perf_1m,
        beta=beta,
        has_negative_catalyst=news_breakdown.has_negative_catalyst,
        entry=plan.entry,
        stop=plan.stop,
        target=plan.target_1 or plan.target_2,
        last_close=last_close,
        ticker=getattr(info, "ticker", "") if info else "",
    )

    if not gates.all_pass:
        return _rejected_result(
            gates=gates,
            tech_legacy=tech_legacy,
            news=news_breakdown,
            fund=fund,
            macro=macro,
            liq=liq,
            squeeze=squeeze,
            plan=plan,
            setup=setup,
            perf_1m=perf_1m,
            last_close=last_close,
        )

    # ---- Layer 2: Factor scores ----
    integrity = compute_setup_integrity(snap)

    # v3: analyst targets BOOST the integrity factor multiplicatively.
    target_info = compute_target_premium(info, last_close=last_close)
    integrity_score = integrity.score * float(target_info.get("integrity_mult") or 1.0)
    integrity_score = max(0.0, min(100.0, integrity_score))

    # v3: institutional_flow combines the legacy volume-pattern score
    # with insider-cluster signal and short-interest delta.
    base_inst_flow = compute_institutional_flow_score(snap)
    insider_info = compute_insider_flow(insider_df)
    short_delta_info = compute_short_int_delta(short_rows or [])
    inst_flow_score = base_inst_flow + insider_info["factor_delta"] + short_delta_info["factor_delta"]
    inst_flow_score = max(0.0, min(100.0, inst_flow_score))

    factor_scores = {
        "quality": compute_quality_score(info),
        "setup_integrity": integrity_score,
        "rr": compute_rr_factor_score(plan.risk_reward),
        "catalyst": compute_catalyst_score(news_breakdown),
        "mean_reversion": compute_mean_reversion_score(snap, info),
        "macro_sector": compute_macro_sector_score(sector, macro_events or []),
        "institutional_flow": inst_flow_score,
        "vol_regime": compute_vol_regime_score(snap),
        "earnings_momentum": compute_earnings_momentum(info),
    }

    raw = sum(factor_scores[k] * w for k, w in FACTOR_WEIGHTS.items())

    # ---- Category (needed before final multiplier so regime tilt can apply) ----
    category = classify_category_long(
        snap=snap,
        info=info,
        setup_type=setup,
        beta=beta,
        has_positive_catalyst=news_breakdown.has_positive_catalyst,
        has_sector_momentum=has_sector_mom,
    )

    # ---- Layer 3: Multipliers ----
    ext_mult = compute_extension_multiplier(perf_1m)
    tim_mult = compute_timing_multiplier(
        news_breakdown.catalyst_age_days,
        news_breakdown.catalyst_is_digesting,
    )
    vol_mult = compute_vol_anchor_multiplier(snap.atr_pct if snap else None)
    # v3: macro-regime tilt — category-aware, defaults to 1.0 when no
    # regime is supplied or category isn't tilted by the active regime.
    reg_mult = regime_multiplier(macro_regime, category)
    final_mult = ext_mult * tim_mult * vol_mult * reg_mult

    final_score = max(0.0, min(100.0, raw * final_mult))

    multipliers = {
        "extension": round(ext_mult, 4),
        "timing": round(tim_mult, 4),
        "vol_anchor": round(vol_mult, 4),
        "regime": round(reg_mult, 4),
        "final_multiplier": round(final_mult, 4),
    }

    # ---- Tier (single-shot; daily caps applied at ranking time) ----
    tier = assign_tier_single(final_score)

    # Tag the legacy tech breakdown with the sector_momentum flag so the
    # legacy LLM template can render it.
    tech_legacy.has_sector_momentum = has_sector_mom

    profile = _profile_from_category(category)
    conviction = _conviction_from_tier(tier)
    horizon = _horizon(profile, setup)

    # Re-build trade plan with the correct profile (affects stop width/targets)
    plan = (
        _build_long_plan(snap, tech_legacy, profile if profile != "none" else "conservative")
        if snap else plan
    )

    # ---- Statuses & warnings & explanation ----
    extension_status = _extension_status(perf_1m)
    entry_zone_status = _entry_zone_status(last_close, plan.entry)

    warnings = generate_warnings(
        snap=snap,
        perf_1m_pct=perf_1m,
        last_close=last_close,
        entry_computed=plan.entry,
        rr=plan.risk_reward,
        catalyst_age_days=news_breakdown.catalyst_age_days,
        quality_score=factor_scores["quality"],
        macro_score=factor_scores["macro_sector"],
        avg_dollar_vol_30d=avg_dollar_vol,
        is_parabolic_30d=bool(getattr(snap, "is_parabolic_30d", False)) if snap else False,
    )

    explanation = generate_explanation_bullets(
        snap=snap,
        setup_type=setup,
        factor_scores=factor_scores,
        multipliers=multipliers,
        tier=tier,
        category=category,
        info=info,
        catalyst_age_days=news_breakdown.catalyst_age_days,
        catalyst_is_digesting=news_breakdown.catalyst_is_digesting,
        has_positive_catalyst=news_breakdown.has_positive_catalyst,
        perf_1m_pct=perf_1m,
        rr=plan.risk_reward,
        quality_reasons=fund.reasons,
        setup_reasons=integrity.reasons,
        target_info=target_info,
        insider_info=insider_info,
        short_delta_info=short_delta_info,
        macro_regime=macro_regime,
    )

    raw_score_data = {
        "tier": tier,
        "category": category,
        "factor_scores": {k: round(v, 2) for k, v in factor_scores.items()},
        "multipliers": multipliers,
        "warnings": warnings,
        "explanation": explanation,
        "extension_status": extension_status,
        "entry_zone_status": entry_zone_status,
        "perf_1m_pct": perf_1m,
        "rejected": False,
        "rejection_reasons": [],
        "gates": gates.to_dict(),
        # v3 edge factors — surfaced for observability / future UI use
        "edge_factors": {
            "target": _safe_dict(target_info),
            "insider": _safe_dict(insider_info),
            "short_delta": _safe_dict(short_delta_info),
            "macro_regime": _safe_dict(macro_regime) if macro_regime else None,
        },
    }

    return FinalScore(
        total=round(final_score, 1),
        technical=tech_legacy,
        news=news_breakdown,
        fundamental=fund,
        macro=macro,
        liquidity=liq,
        squeeze=squeeze,
        setup_type=setup,
        conviction=conviction,
        horizon=horizon,
        profile=profile,
        trade_plan=plan,
        rejected=False,
        rejection_reasons=[],
        factor_scores={k: round(v, 2) for k, v in factor_scores.items()},
        multipliers=multipliers,
        category=category,
        tier=tier,
        warnings=warnings,
        explanation=explanation,
        extension_status=extension_status,
        entry_zone_status=entry_zone_status,
        perf_1m_pct=perf_1m,
        raw_score_data=raw_score_data,
    )


def _rejected_result(
    *,
    gates: GatesResult,
    tech_legacy: TechnicalScoreBreakdown,
    news: NewsScoreBreakdown,
    fund: FundamentalScoreBreakdown,
    macro: MacroScoreBreakdown,
    liq: LiquidityScoreBreakdown,
    squeeze: SqueezeRiskBreakdown,
    plan: TradePlan,
    setup: str,
    perf_1m: Optional[float],
    last_close: Optional[float],
) -> FinalScore:
    """Construct a zero-score result for a rejected (gate-failed) candidate."""
    raw_score_data = {
        "tier": "D",
        "category": None,
        "factor_scores": {},
        "multipliers": {},
        "warnings": [],
        "explanation": [],
        "extension_status": _extension_status(perf_1m),
        "entry_zone_status": _entry_zone_status(last_close, plan.entry),
        "perf_1m_pct": perf_1m,
        "rejected": True,
        "rejection_reasons": list(gates.failure_reasons),
        "gates": gates.to_dict(),
    }
    return FinalScore(
        total=0.0,
        technical=tech_legacy,
        news=news,
        fundamental=fund,
        macro=macro,
        liquidity=liq,
        squeeze=squeeze,
        setup_type=setup,
        conviction="low",
        horizon="swing",
        profile="none",
        trade_plan=plan,
        rejected=True,
        rejection_reasons=list(gates.failure_reasons),
        factor_scores={},
        multipliers={},
        category=None,
        tier="D",
        warnings=[],
        explanation=[],
        extension_status=raw_score_data["extension_status"],
        entry_zone_status=raw_score_data["entry_zone_status"],
        perf_1m_pct=perf_1m,
        raw_score_data=raw_score_data,
    )
