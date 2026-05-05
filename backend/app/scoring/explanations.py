"""Explanation bullets + warnings.

Two outputs per stock:

  - bullets: 2-4 short sentences referencing CONCRETE numbers from the
    score breakdown. Bad: "Strong fundamentals." Good: "ROIC ~28%,
    debt/equity 0.4 — top decile quality."

  - warnings: short tags from a controlled vocabulary that the frontend
    can render as chips. Examples: "extended", "chased",
    "earnings_approaching", "rr_below_standard", "sector_weakening".
"""
from __future__ import annotations

from typing import Optional

from app.scoring.technicals import TechnicalSnapshot


# Controlled warning vocabulary — frontend can map these to i18n strings
WARNING_EXTENDED = "extended"
WARNING_CHASED = "chased"
WARNING_EARNINGS = "earnings_approaching"
WARNING_RR_LOW = "rr_below_standard"
WARNING_SECTOR_WEAK = "sector_weakening"
WARNING_HIGH_VOL = "high_realized_vol"
WARNING_FRESH_NEWS = "fresh_news_chase_risk"
WARNING_NEAR_52W_HIGH = "near_52w_high"
WARNING_THIN_LIQUIDITY = "thin_liquidity"
WARNING_PARABOLIC = "parabolic_shape"
WARNING_LOW_QUALITY = "low_quality_fundamentals"


def generate_warnings(
    *,
    snap: Optional[TechnicalSnapshot],
    perf_1m_pct: Optional[float],
    last_close: Optional[float],
    entry_computed: Optional[float],
    rr: Optional[float],
    catalyst_age_days: Optional[float],
    quality_score: float,
    macro_score: float,
    avg_dollar_vol_30d: Optional[float],
    is_parabolic_30d: bool,
) -> list[str]:
    """Produce 0-N warning tags. Each is a stable, machine-readable string."""
    out: list[str] = []

    if perf_1m_pct is not None and perf_1m_pct >= 25.0:
        out.append(WARNING_EXTENDED)
    if last_close is not None and entry_computed is not None and entry_computed > 0:
        if (last_close - entry_computed) / entry_computed * 100.0 >= 3.0:
            out.append(WARNING_CHASED)
    if rr is not None and rr < 1.8:
        out.append(WARNING_RR_LOW)
    if macro_score < 40:
        out.append(WARNING_SECTOR_WEAK)
    if catalyst_age_days is not None and catalyst_age_days < 1.0:
        out.append(WARNING_FRESH_NEWS)
    if is_parabolic_30d:
        out.append(WARNING_PARABOLIC)
    if snap is not None:
        rv = getattr(snap, "realized_vol_30d", None)
        if rv is not None and rv > 0.55:
            out.append(WARNING_HIGH_VOL)
        if snap.high_52w and snap.last_close >= snap.high_52w * 0.97:
            out.append(WARNING_NEAR_52W_HIGH)
    if avg_dollar_vol_30d is not None and avg_dollar_vol_30d < 5_000_000:
        out.append(WARNING_THIN_LIQUIDITY)
    if quality_score < 40:
        out.append(WARNING_LOW_QUALITY)

    return out


def generate_explanation_bullets(
    *,
    snap: Optional[TechnicalSnapshot],
    setup_type: str,
    factor_scores: dict,
    multipliers: dict,
    tier: str,
    category: str,
    info,
    catalyst_age_days: Optional[float],
    catalyst_is_digesting: bool,
    has_positive_catalyst: bool,
    perf_1m_pct: Optional[float],
    rr: Optional[float],
    quality_reasons: list[str],
    setup_reasons: list[str],
    target_info: Optional[dict] = None,
    insider_info: Optional[dict] = None,
    short_delta_info: Optional[dict] = None,
    macro_regime: Optional[dict] = None,
) -> list[str]:
    """Build 2-4 evidence-rich bullets. Always anchors on real numbers.

    v3: extra optional kwargs surface edge-factor narrative when relevant.
    Each adds AT MOST one bullet, and only if the signal is actionable.
    """
    bullets: list[str] = []

    # 1. Setup + structure summary
    if setup_type == "trend":
        if snap and snap.sma_50 and snap.sma_200:
            bullets.append(
                f"Confirmed uptrend: price {_fmt_price(snap.last_close)} above SMA50 "
                f"{_fmt_price(snap.sma_50)} and SMA200 {_fmt_price(snap.sma_200)}, MA stacking bullish."
            )
        else:
            bullets.append("Confirmed uptrend with bullish MA stacking.")
    elif setup_type == "breakout":
        if snap and snap.resistance_level:
            bullets.append(
                f"Breakout above resistance {_fmt_price(snap.resistance_level)} with rising volume "
                f"(rel vol {snap.relative_volume:.1f}x)." if snap.relative_volume
                else f"Breakout above resistance {_fmt_price(snap.resistance_level)}."
            )
        else:
            bullets.append("Breakout setup with volume confirmation.")
    elif setup_type == "catalyst":
        if catalyst_age_days is not None:
            if catalyst_is_digesting:
                bullets.append(
                    f"Positive catalyst {catalyst_age_days:.0f} days old, in the digestion window — "
                    f"institutional move printed, retail edge available."
                )
            else:
                bullets.append(f"Positive catalyst {catalyst_age_days:.0f} days old.")
        else:
            bullets.append("Positive catalyst recently identified.")
    elif setup_type == "reversion":
        rsi = snap.rsi_14 if snap else None
        if rsi is not None:
            bullets.append(f"Oversold bounce setup with RSI {rsi:.0f} recovering from extreme.")
        else:
            bullets.append("Oversold bounce setup in healthy stock.")
    elif setup_type == "momentum":
        bullets.append("Sector momentum setup — broader industry tailwind detected.")
    else:
        # Fall back to top setup reason
        if setup_reasons:
            bullets.append(setup_reasons[0])

    # 2. Quality / fundamentals
    if quality_reasons:
        # Take the most informative top reason
        top = quality_reasons[0]
        bullets.append(f"Quality: {top}.")
    elif factor_scores.get("quality") is not None:
        q = float(factor_scores["quality"])
        bullets.append(f"Quality factor {q:.0f}/100.")

    # 3. Risk-reward / extension context
    if rr is not None:
        if perf_1m_pct is not None:
            bullets.append(
                f"Risk/reward {rr:.1f}:1 with 1-month perf {perf_1m_pct:+.1f}% "
                f"(extension multiplier {multipliers.get('extension', 1.0):.2f})."
            )
        else:
            bullets.append(f"Risk/reward {rr:.1f}:1.")

    # 4. Edge-factor narrative (v3) — at most ONE extra bullet across
    # the four signals, prioritized by actionability.
    edge_bullet = _format_edge_bullet(
        target_info=target_info,
        insider_info=insider_info,
        short_delta_info=short_delta_info,
        macro_regime=macro_regime,
        factor_scores=factor_scores,
    )
    if edge_bullet:
        bullets.append(edge_bullet)

    # 5. Tier + category context
    bullets.append(
        f"Classified as {category.replace('_', ' ')} — tier {tier} after daily caps."
    )

    return bullets[:4]


def _format_edge_bullet(
    *,
    target_info: Optional[dict],
    insider_info: Optional[dict],
    short_delta_info: Optional[dict],
    macro_regime: Optional[dict],
    factor_scores: dict,
) -> Optional[str]:
    """Pick the strongest edge-factor signal to surface. Priority order:

      1. Insider cluster buying (rare and informative)
      2. Earnings momentum (strongest academic signal)
      3. Short-interest delta (covering = bullish)
      4. Analyst price-target premium
      5. Macro regime (only when not 'mixed')
    """
    # 1. Insiders
    if insider_info and insider_info.get("cluster_buy"):
        v = insider_info.get("total_buy_value") or 0.0
        n = insider_info.get("buy_count") or 0
        return f"Insiders compraron ~${v/1e6:.2f}M en últimos 90d ({n} compras de C-suite)."
    if insider_info and insider_info.get("cluster_sell"):
        v = insider_info.get("total_sell_value") or 0.0
        n = insider_info.get("sell_count") or 0
        return f"Insiders vendieron ~${v/1e6:.2f}M en últimos 90d ({n} ventas de C-suite) — bandera amarilla."

    # 2. Earnings momentum
    em = factor_scores.get("earnings_momentum") if factor_scores else None
    if em is not None and em >= 75:
        return f"Earnings momentum fuerte ({em:.0f}/100) — estimaciones revisándose al alza."
    if em is not None and em <= 30:
        return f"Earnings momentum débil ({em:.0f}/100) — estimaciones revisándose a la baja."

    # 3. Short-interest delta
    if short_delta_info and short_delta_info.get("applicable"):
        delta = short_delta_info.get("delta_pct")
        if delta is not None and delta < -2.0:
            return f"Short interest cayó {abs(delta):.1f}pp en 30d — covering bullish para longs."
        if delta is not None and delta > 2.0:
            return f"Short interest subió {delta:.1f}pp en 30d — apuestas bajistas creciendo."

    # 4. Analyst targets
    if target_info and target_info.get("applicable"):
        prem = target_info.get("target_premium_pct")
        n = target_info.get("num_analyst_opinions") or 0
        if prem is not None and prem >= 10.0:
            return f"Target promedio de analistas implica +{prem:.1f}% (n={int(n)})."

    # 5. Macro regime
    if macro_regime:
        regime = macro_regime.get("regime")
        if regime and regime != "mixed":
            return f"Régimen macro {regime.replace('_', ' ')} — sesgo aplicado al score."

    return None


def _fmt_price(p: Optional[float]) -> str:
    if p is None:
        return "n/a"
    if p >= 100:
        return f"{p:.2f}"
    if p >= 10:
        return f"{p:.2f}"
    return f"{p:.3f}"
