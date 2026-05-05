"""Pure technical indicator calculations on a price DataFrame.

Input DataFrame must contain at least ['close', 'high', 'low', 'volume'] columns
indexed by date.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class TechnicalSnapshot:
    last_close: float
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_100: Optional[float]
    sma_200: Optional[float]
    ema_20: Optional[float]
    ema_50: Optional[float]
    rsi_14: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    atr_14: Optional[float]
    relative_volume: Optional[float]   # volume vs 20d avg
    high_52w: Optional[float]
    low_52w: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]
    change_1d: Optional[float]
    change_5d: Optional[float]
    change_1m: Optional[float]
    change_6m: Optional[float]
    # v2 redesign helpers (lazy-populated by compute_technical_snapshot)
    perf_1m_pct: Optional[float] = None         # alias of change_1m, semantic clarity
    sma_200_slope: Optional[float] = None       # 20-bar slope of SMA200
    realized_vol_30d: Optional[float] = None    # annualized stddev of 30d daily returns
    atr_pct: Optional[float] = None             # ATR as % of last close
    dollar_volume_30d: Optional[float] = None   # avg(close * volume) over 30 days
    is_parabolic_30d: bool = False              # 30d price ROC > 50% AND consecutive 5+ green days


def _safe_last(series: pd.Series) -> Optional[float]:
    if series is None or series.empty:
        return None
    val = series.dropna()
    if val.empty:
        return None
    return float(val.iloc[-1])


def _change(close: pd.Series, periods: int) -> Optional[float]:
    if len(close) <= periods:
        return None
    try:
        return float((close.iloc[-1] / close.iloc[-1 - periods] - 1.0) * 100.0)
    except (ZeroDivisionError, IndexError):
        return None


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def detect_support_resistance(close: pd.Series, lookback: int = 60) -> tuple[Optional[float], Optional[float]]:
    """Simple S/R: rolling min/max over a lookback window, ignoring the very last bar."""
    if len(close) < lookback + 2:
        return None, None
    window = close.iloc[-lookback - 1:-1]
    return float(window.min()), float(window.max())


def _finite(v) -> Optional[float]:
    """Return v as float if it's finite (not NaN/Inf), else None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def compute_perf_1m(close: pd.Series) -> Optional[float]:
    """1-month (~21 trading days) performance in percent."""
    return _finite(_change(close, 21))


def compute_sma_200_slope(close: pd.Series, window: int = 20) -> Optional[float]:
    """Rate-of-change of the SMA200 over the last `window` bars.

    Returns the relative change (e.g. 0.012 = SMA200 grew 1.2% over the
    window). None if insufficient data. Used as a structural trend gate:
    a sloping-up SMA200 indicates a healthy long-term uptrend.
    """
    if close is None or len(close) < 200 + window:
        return None
    sma = close.rolling(200).mean()
    sma = sma.dropna()
    if len(sma) < window + 1:
        return None
    try:
        recent = float(sma.iloc[-1])
        past = float(sma.iloc[-1 - window])
        if past == 0 or not math.isfinite(recent) or not math.isfinite(past):
            return None
        return (recent - past) / past
    except (IndexError, ZeroDivisionError):
        return None


def compute_realized_vol(df: pd.DataFrame, period: int = 30) -> Optional[float]:
    """Annualized realized volatility over `period` trading days.

    Uses log returns. Returns None if insufficient data. Typical values:
    ~0.20 = 20% annualized (low), 0.60 = 60% (very high).
    """
    if df is None or "close" not in df.columns or len(df) < period + 2:
        return None
    close = df["close"].dropna()
    if len(close) < period + 2:
        return None
    try:
        rets = np.log(close / close.shift(1)).dropna().tail(period)
        if rets.empty:
            return None
        vol = float(rets.std() * math.sqrt(252))
        return vol if math.isfinite(vol) else None
    except (ValueError, ZeroDivisionError):
        return None


def compute_beta_vs_spy(
    stock_close: pd.Series,
    spy_close: Optional[pd.Series],
    period: int = 252,
) -> Optional[float]:
    """Stock beta vs SPY using overlapping daily returns over `period`.

    Lenient by design: if SPY data is missing or insufficient history exists,
    returns None and the gate falls back to passing.
    """
    if stock_close is None or spy_close is None:
        return None
    if len(stock_close) < period + 2 or len(spy_close) < period + 2:
        return None
    try:
        s = stock_close.tail(period + 1)
        m = spy_close.tail(period + 1)
        # Align by date if both are date-indexed; otherwise zip-align via tail
        joined = pd.concat([s.rename("s"), m.rename("m")], axis=1).dropna()
        if len(joined) < period // 2:
            return None
        rs = np.log(joined["s"] / joined["s"].shift(1)).dropna()
        rm = np.log(joined["m"] / joined["m"].shift(1)).dropna()
        n = min(len(rs), len(rm))
        if n < 30:
            return None
        rs = rs.tail(n)
        rm = rm.tail(n)
        var_m = float(rm.var())
        if var_m <= 0 or not math.isfinite(var_m):
            return None
        cov = float(np.cov(rs, rm)[0, 1])
        beta = cov / var_m
        return beta if math.isfinite(beta) else None
    except Exception:
        return None


def compute_dollar_volume_30d(df: pd.DataFrame) -> Optional[float]:
    """Average daily dollar volume (close * volume) over last 30 sessions."""
    if df is None or df.empty or "close" not in df.columns or "volume" not in df.columns:
        return None
    tail = df.tail(30)
    try:
        dv = (tail["close"].astype(float) * tail["volume"].astype(float)).dropna()
        if dv.empty:
            return None
        v = float(dv.mean())
        return v if math.isfinite(v) and v > 0 else None
    except (TypeError, ValueError):
        return None


def is_parabolic(df: pd.DataFrame, perf_1m: Optional[float]) -> bool:
    """Detect a parabolic blow-off pattern.

    Heuristic: 1-month perf > 50% AND a recent run of 5+ consecutive
    closes-up days (no real digestion). Conservative — both conditions
    must be true.
    """
    if perf_1m is None or perf_1m < 50.0:
        return False
    if df is None or "close" not in df.columns or len(df) < 10:
        return False
    try:
        last = df["close"].tail(10).dropna()
        if len(last) < 6:
            return False
        diffs = last.diff().dropna()
        # Count trailing positive days
        run = 0
        for v in reversed(list(diffs)):
            if v > 0:
                run += 1
            else:
                break
        return run >= 5
    except Exception:
        return False


def compute_technical_snapshot(df: pd.DataFrame) -> Optional[TechnicalSnapshot]:
    if df is None or df.empty or "close" not in df.columns:
        return None

    close = df["close"]
    if len(close) < 30:
        return None

    sma = lambda n: close.rolling(n).mean() if len(close) >= n else pd.Series(dtype=float)
    ema = lambda n: close.ewm(span=n, adjust=False).mean()

    macd, macd_signal = compute_macd(close)
    rsi = compute_rsi(close, 14)
    atr = compute_atr(df, 14)

    avg_vol_20 = df["volume"].rolling(20).mean()
    rel_vol = (df["volume"].iloc[-1] / avg_vol_20.iloc[-1]) if avg_vol_20.iloc[-1] and avg_vol_20.iloc[-1] > 0 else None

    support, resistance = detect_support_resistance(close, 60)

    last_close_v = float(close.iloc[-1])
    atr_last = _safe_last(atr)
    perf_1m = _change(close, 21)
    sma_200_slope = compute_sma_200_slope(close, 20)
    realized_vol = compute_realized_vol(df, 30)
    atr_pct = None
    if atr_last is not None and last_close_v and last_close_v > 0:
        v = atr_last / last_close_v
        atr_pct = v if math.isfinite(v) else None
    dvol_30d = compute_dollar_volume_30d(df)
    parabolic = is_parabolic(df, perf_1m)

    return TechnicalSnapshot(
        last_close=last_close_v,
        sma_20=_safe_last(sma(20)),
        sma_50=_safe_last(sma(50)),
        sma_100=_safe_last(sma(100)),
        sma_200=_safe_last(sma(200)),
        ema_20=_safe_last(ema(20)),
        ema_50=_safe_last(ema(50)),
        rsi_14=_safe_last(rsi),
        macd=_safe_last(macd),
        macd_signal=_safe_last(macd_signal),
        atr_14=atr_last,
        relative_volume=float(rel_vol) if rel_vol is not None else None,
        high_52w=float(close.iloc[-252:].max()) if len(close) >= 252 else float(close.max()),
        low_52w=float(close.iloc[-252:].min()) if len(close) >= 252 else float(close.min()),
        support_level=support,
        resistance_level=resistance,
        change_1d=_change(close, 1),
        change_5d=_change(close, 5),
        change_1m=perf_1m,
        change_6m=_change(close, 126),
        perf_1m_pct=perf_1m,
        sma_200_slope=sma_200_slope,
        realized_vol_30d=realized_vol,
        atr_pct=atr_pct,
        dollar_volume_30d=dvol_30d,
        is_parabolic_30d=parabolic,
    )
