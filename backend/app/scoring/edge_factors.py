"""Edge-factor signals — v3 add-on to the v2 scoring engine.

Five pure(ish) functions plus a top-level macro-regime detector:

  - compute_target_premium(info)              -> dict   (analyst targets)
  - compute_earnings_momentum(info)           -> float  (0-100)
  - compute_insider_flow(insider_df)          -> dict   (cluster buy/sell)
  - compute_short_int_delta(short_rows)       -> dict   (latest vs ~30d ago)
  - detect_macro_regime()                     -> dict   (regime + tilts)

All functions are robust to missing data (None / NaN / empty DataFrame)
and degrade to a neutral default rather than raising.

Conventions:
  - "delta" / "premium" pcts are stored as percent units (e.g. 12.5 means
    +12.5%), not fractions.
  - Functions that feed an EXISTING factor return a small dict so the
    engine can both apply the modifier AND surface an explanation hint.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd


# ---------------- Common helpers ----------------

def _finite(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ---------------- (A) Analyst price targets ----------------

def compute_target_premium(info, last_close: Optional[float] = None) -> dict:
    """Analyst-target premium feeder for the ``setup_integrity`` factor.

    Output dict:
      - applicable: bool — True when we have >= 3 analyst opinions AND
        a finite target_mean_price.
      - target_premium_pct: float | None — (target - current)/current * 100
      - integrity_mult: float — multiplier to apply to the integrity
        factor. Always >= 1.0 (we boost, never penalize, since a
        rich target reflects analyst optimism). Capped at 1.15.
      - num_analyst_opinions: float | None
      - target_mean_price: float | None
    """
    out = {
        "applicable": False,
        "target_premium_pct": None,
        "integrity_mult": 1.0,
        "num_analyst_opinions": None,
        "target_mean_price": None,
    }
    if info is None:
        return out

    target = _finite(getattr(info, "target_mean_price", None))
    n = _finite(getattr(info, "num_analyst_opinions", None))
    out["num_analyst_opinions"] = n
    out["target_mean_price"] = target

    # Need both
    if target is None or last_close is None or last_close <= 0:
        return out

    # Coverage gate — too thin a panel, ignore.
    if n is None or n < 3:
        return out

    premium_pct = (target - float(last_close)) / float(last_close) * 100.0
    out["target_premium_pct"] = round(premium_pct, 2)

    # Multiplier: 1 + clip(premium/200, 0, 0.15). A +30% target = ×1.15.
    # Negative premium (target below price) collapses to 1.0 (no boost,
    # but not a penalty either — analysts can lag and we don't want to
    # double-count downside which is already in mean_reversion / quality).
    boost = max(0.0, premium_pct / 200.0)
    out["integrity_mult"] = round(1.0 + min(0.15, boost), 4)
    out["applicable"] = True
    return out


# ---------------- (B) Earnings estimate revisions ----------------

def compute_earnings_momentum(info) -> float:
    """0-100 factor capturing earnings/revenue growth direction.

    Academically the strongest known anomaly (PEAD, Bernard & Thomas
    1989). yfinance does not expose the full estimate-revision time
    series cheaply, so we use the available signals:

      - earningsQuarterlyGrowth (most recent qtr vs year-ago qtr)
      - earningsGrowth (yoy aggregate, sometimes named "earnings_growth")
      - revenueGrowth (top-line growth, fallback if EPS is None)

    Higher growth -> higher score. Strong negatives heavily penalized
    (PEAD works in BOTH directions — earnings disappointments drift
    down too).

    Schedule (max one bonus per signal, additive on a 50 base):
      eps_qtr_growth > +25%:  +22
      eps_qtr_growth > +10%:  +12
      eps_qtr_growth > 0%:    +4
      eps_qtr_growth < -15%: -22
      eps_qtr_growth < -5%:   -12

      earnings_yoy > +20%:    +14
      earnings_yoy > +8%:     +6
      earnings_yoy < -10%:   -12

      rev_growth > +15%:      +10
      rev_growth > +5%:       +4
      rev_growth < -5%:       -8
    """
    if info is None:
        return 50.0

    eps_q = _finite(getattr(info, "earnings_growth_quarterly", None))
    eps_y = _finite(getattr(info, "earnings_growth_yoy", None))
    rev = _finite(getattr(info, "revenue_growth", None))
    # Fallback to legacy field on Fundamentals if the new fields are absent
    if rev is None:
        rev = _finite(getattr(info, "revenue_growth_yoy", None))

    score = 50.0

    # Quarterly EPS growth — most timely PEAD signal
    if eps_q is not None:
        if eps_q > 0.25:
            score += 22
        elif eps_q > 0.10:
            score += 12
        elif eps_q > 0.0:
            score += 4
        elif eps_q < -0.15:
            score -= 22
        elif eps_q < -0.05:
            score -= 12

    # Annual EPS growth
    if eps_y is not None:
        if eps_y > 0.20:
            score += 14
        elif eps_y > 0.08:
            score += 6
        elif eps_y < -0.10:
            score -= 12

    # Revenue growth — fallback when EPS is volatile/missing
    if rev is not None:
        if rev > 0.15:
            score += 10
        elif rev > 0.05:
            score += 4
        elif rev < -0.05:
            score -= 8

    # If we got NO earnings signals at all, back off to neutral 50.
    if eps_q is None and eps_y is None and rev is None:
        return 50.0

    return _clip(score, 0.0, 100.0)


# ---------------- (C) Insider transactions ----------------

# Position-substring filter for "C-suite" + directors
_CSUITE_TOKENS = ("CEO", "CFO", "PRES", "DIR", "CHAIR", "CHIEF")
_VALUE_THRESHOLD = 100_000.0  # USD


def compute_insider_flow(insider_df: Optional[pd.DataFrame]) -> dict:
    """Detect cluster buying / cluster selling among insiders in the
    last 90 days.

    Args:
        insider_df: yfinance ``insider_transactions`` DataFrame, or None.

    Returns:
        dict with:
          - applicable: bool
          - cluster_buy: bool          (>= 2 qualifying purchases)
          - cluster_sell: bool         (>= 2 qualifying sales)
          - buy_count: int
          - sell_count: int
          - total_buy_value: float     (sum USD)
          - total_sell_value: float    (sum USD)
          - factor_delta: float        — to be ADDED to institutional_flow
                                          factor (capped at +15 / -10)
    """
    out = {
        "applicable": False,
        "cluster_buy": False,
        "cluster_sell": False,
        "buy_count": 0,
        "sell_count": 0,
        "total_buy_value": 0.0,
        "total_sell_value": 0.0,
        "factor_delta": 0.0,
    }
    if insider_df is None or not hasattr(insider_df, "empty") or insider_df.empty:
        return out

    df = insider_df.copy()
    cutoff = datetime.utcnow() - timedelta(days=90)

    # Date column is "Start Date" in modern yfinance (older versions used
    # "Date"). Be lenient.
    date_col = None
    for cand in ("Start Date", "Date", "start_date"):
        if cand in df.columns:
            date_col = cand
            break

    if date_col is not None:
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df[df[date_col].notna()]
            df = df[df[date_col] >= cutoff]
        except Exception:
            # If parsing fails outright, fall back to using all rows.
            pass

    if df.empty:
        return out

    out["applicable"] = True

    txn_col = "Transaction" if "Transaction" in df.columns else None
    pos_col = "Position" if "Position" in df.columns else None
    val_col = "Value" if "Value" in df.columns else None

    buy_count = 0
    sell_count = 0
    buy_value = 0.0
    sell_value = 0.0

    for _, row in df.iterrows():
        txn = str(row.get(txn_col, "")).strip().lower() if txn_col else ""
        pos = str(row.get(pos_col, "")).upper() if pos_col else ""
        val = _finite(row.get(val_col)) if val_col else None

        if val is None or val < _VALUE_THRESHOLD:
            continue
        if pos and not any(tok in pos for tok in _CSUITE_TOKENS):
            continue

        # yfinance's Transaction labels: "Purchase", "Sale", "Sale (Multiple)",
        # "Stock Award", "Option Exercise", etc. Treat anything starting
        # with "purchase" as a buy, "sale" as a sell.
        if txn.startswith("purchase") or txn == "buy":
            buy_count += 1
            buy_value += val
        elif txn.startswith("sale") or txn == "sell":
            sell_count += 1
            sell_value += val

    out["buy_count"] = buy_count
    out["sell_count"] = sell_count
    out["total_buy_value"] = round(buy_value, 2)
    out["total_sell_value"] = round(sell_value, 2)
    out["cluster_buy"] = buy_count >= 2
    out["cluster_sell"] = sell_count >= 2

    delta = 0.0
    if out["cluster_buy"]:
        delta += 15.0
    if out["cluster_sell"]:
        delta -= 10.0
    out["factor_delta"] = delta
    return out


# ---------------- (D) Short interest delta ----------------

def compute_short_int_delta(short_rows: list) -> dict:
    """Compute change in short_percent_of_float vs ~30d ago.

    Args:
        short_rows: list of ShortData rows for a single instrument,
            ordered ASC or DESC by date — we re-sort defensively.

    Returns:
        dict with:
          - applicable: bool
          - latest_pct: float | None     (latest short % of float)
          - prior_pct: float | None      (~30d-ago value)
          - delta_pct: float | None      (latest - prior, percent units)
          - factor_delta: float          ADDED to institutional_flow
                                          (+10 if delta < -2%; -10 if > +2%)
    """
    out = {
        "applicable": False,
        "latest_pct": None,
        "prior_pct": None,
        "delta_pct": None,
        "factor_delta": 0.0,
    }
    if not short_rows:
        return out

    # Pull (date, pct) pairs — short_percent_float is fraction, e.g. 0.12.
    pairs: list[tuple] = []
    for row in short_rows:
        d = getattr(row, "date", None)
        pct = _finite(getattr(row, "short_percent_float", None))
        if d is None or pct is None:
            continue
        pairs.append((d, pct))

    if not pairs:
        return out

    pairs.sort(key=lambda x: x[0])  # ascending by date
    latest_date, latest_pct = pairs[-1]

    # Find the row closest to ~30 days before latest.
    target_date = latest_date - timedelta(days=30)
    # Pick the most recent row at or before target_date.
    prior_pct: Optional[float] = None
    for d, pct in reversed(pairs[:-1]):
        if d <= target_date:
            prior_pct = pct
            break
    # Fallback: use the OLDEST available row if we don't have ~30d of history.
    if prior_pct is None and len(pairs) >= 2:
        prior_pct = pairs[0][1]

    out["latest_pct"] = round(latest_pct * 100.0, 2)  # convert to percent
    if prior_pct is None:
        return out

    out["prior_pct"] = round(prior_pct * 100.0, 2)
    delta_pct = (latest_pct - prior_pct) * 100.0  # in percent units
    out["delta_pct"] = round(delta_pct, 2)
    out["applicable"] = True

    if delta_pct < -2.0:
        out["factor_delta"] = 10.0
    elif delta_pct > 2.0:
        out["factor_delta"] = -10.0
    return out


# ---------------- (E) Macro regime detector ----------------

# Tilt schedule by regime — applied to final_score in engine.py
_REGIME_TILTS = {
    "risk_on":         {"speculative": 1.10, "investment": 0.95, "swing_trade": 1.0, "cyclical": 1.05},
    "risk_off":        {"speculative": 0.85, "investment": 1.10, "swing_trade": 1.0, "cyclical": 0.90},
    "late_cycle":      {"speculative": 0.95, "investment": 1.0,  "swing_trade": 1.0, "cyclical": 1.0},
    "recession_risk":  {"speculative": 0.85, "investment": 1.05, "swing_trade": 1.0, "cyclical": 0.90},
    "mixed":           {"speculative": 1.0,  "investment": 1.0,  "swing_trade": 1.0, "cyclical": 1.0},
}


def _neutral_regime() -> dict:
    return {
        "regime": "mixed",
        "tilt": dict(_REGIME_TILTS["mixed"]),
        "yield_curve_slope_pct": None,
        "vix": None,
        "dxy_change_30d_pct": None,
        "spx_above_50d": None,
        "spx_above_200d": None,
        "asof": datetime.utcnow().isoformat(timespec="seconds"),
    }


def detect_macro_regime() -> dict:
    """Detect a high-level macro regime once per daily run.

    Inputs (best-effort yfinance fetches):
      - ^TNX (10y treasury yield)
      - ^IRX (3m treasury yield)
      - ^VIX (vol index)
      - DX-Y.NYB or ^DXY (USD index)
      - ^GSPC (SPX) for 50d/200d MA position

    Returns dict with:
      regime: str    one of risk_on / risk_off / late_cycle /
                     recession_risk / mixed
      tilt: dict     per-category multiplier
      ...telemetry fields...

    On ANY failure (network, missing symbols, NaN math) returns the
    neutral "mixed" regime with all tilts = 1.0. Lenient by design.
    """
    try:
        # Local import to avoid making collectors a hard dep at module load
        # (and to allow unit tests to monkeypatch).
        from app.collectors.market_data import fetch_index_history
    except Exception:
        return _neutral_regime()

    try:
        out = _neutral_regime()

        def _last_close(symbol: str, period: str = "3mo") -> Optional[float]:
            df = fetch_index_history(symbol, period=period)
            if df is None or df.empty or "close" not in df.columns:
                return None
            try:
                v = float(df["close"].dropna().iloc[-1])
                return v if math.isfinite(v) else None
            except Exception:
                return None

        # Yield curve: 10y - 3m. ^TNX/^IRX are quoted in percent × 10
        # (e.g. ^TNX=42.5 means 4.25% yield). We don't really care about
        # absolute level — only the SLOPE for inversion detection.
        tnx = _last_close("^TNX", "3mo")
        irx = _last_close("^IRX", "3mo")
        slope = None
        if tnx is not None and irx is not None:
            slope = tnx - irx  # negative = inverted (recession signal)
            out["yield_curve_slope_pct"] = round(slope, 3)

        vix = _last_close("^VIX", "3mo")
        out["vix"] = round(vix, 2) if vix is not None else None

        # USD 30d change — inputs DX-Y.NYB or ^DXY
        dxy_df = fetch_index_history("DX-Y.NYB", period="3mo")
        if dxy_df is None or dxy_df.empty:
            dxy_df = fetch_index_history("^DXY", period="3mo")
        dxy_change = None
        if dxy_df is not None and not dxy_df.empty and "close" in dxy_df.columns:
            try:
                series = dxy_df["close"].dropna()
                if len(series) >= 22:
                    latest = float(series.iloc[-1])
                    prior = float(series.iloc[-22])  # ~30 trading days
                    if math.isfinite(latest) and math.isfinite(prior) and prior > 0:
                        dxy_change = (latest / prior - 1.0) * 100.0
                        out["dxy_change_30d_pct"] = round(dxy_change, 2)
            except Exception:
                pass

        # SPX MA position
        spx_df = fetch_index_history("^GSPC", period="1y")
        spx_above_50 = None
        spx_above_200 = None
        if spx_df is not None and not spx_df.empty and "close" in spx_df.columns:
            try:
                close = spx_df["close"].dropna()
                if len(close) >= 50:
                    sma50 = float(close.tail(50).mean())
                    spx_above_50 = float(close.iloc[-1]) > sma50
                if len(close) >= 200:
                    sma200 = float(close.tail(200).mean())
                    spx_above_200 = float(close.iloc[-1]) > sma200
            except Exception:
                pass
        out["spx_above_50d"] = spx_above_50
        out["spx_above_200d"] = spx_above_200

        # ---- Regime classification ----
        # 1) recession_risk: yield curve inverted AND SPX below 200d
        if slope is not None and slope < 0 and spx_above_200 is False:
            regime = "recession_risk"
        # 2) risk_off: VIX elevated (>22) OR strong USD spike (>+3% in 30d)
        elif (vix is not None and vix > 22.0) or (dxy_change is not None and dxy_change > 3.0):
            regime = "risk_off"
        # 3) late_cycle: SPX > 50d > 200d AND VIX low (<14) but slope flat (<0.5%)
        elif (
            spx_above_50 is True
            and spx_above_200 is True
            and vix is not None and vix < 14.0
            and slope is not None and 0.0 <= slope < 5.0  # ^TNX-^IRX <0.5pp
        ):
            regime = "late_cycle"
        # 4) risk_on: SPX above 50d AND VIX < 18 AND no inversion
        elif (
            spx_above_50 is True
            and (vix is None or vix < 18.0)
            and (slope is None or slope >= 0)
        ):
            regime = "risk_on"
        else:
            regime = "mixed"

        out["regime"] = regime
        out["tilt"] = dict(_REGIME_TILTS[regime])
        return out
    except Exception:
        return _neutral_regime()


def regime_multiplier(regime: dict, category: Optional[str]) -> float:
    """Return the tilt multiplier for a given category from a regime dict.

    Lenient: missing regime / unknown category collapses to 1.0.
    """
    if not regime or not category:
        return 1.0
    tilts = regime.get("tilt") or {}
    try:
        v = float(tilts.get(category, 1.0))
        return v if math.isfinite(v) else 1.0
    except (TypeError, ValueError):
        return 1.0
