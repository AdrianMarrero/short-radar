"""Pure technical indicator calculations on a price DataFrame.

Input DataFrame must contain at least ['close', 'high', 'low', 'volume'] columns
indexed by date.
"""
from __future__ import annotations

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

    return TechnicalSnapshot(
        last_close=float(close.iloc[-1]),
        sma_20=_safe_last(sma(20)),
        sma_50=_safe_last(sma(50)),
        sma_100=_safe_last(sma(100)),
        sma_200=_safe_last(sma(200)),
        ema_20=_safe_last(ema(20)),
        ema_50=_safe_last(ema(50)),
        rsi_14=_safe_last(rsi),
        macd=_safe_last(macd),
        macd_signal=_safe_last(macd_signal),
        atr_14=_safe_last(atr),
        relative_volume=float(rel_vol) if rel_vol is not None else None,
        high_52w=float(close.iloc[-252:].max()) if len(close) >= 252 else float(close.max()),
        low_52w=float(close.iloc[-252:].min()) if len(close) >= 252 else float(close.min()),
        support_level=support,
        resistance_level=resistance,
        change_1d=_change(close, 1),
        change_5d=_change(close, 5),
        change_1m=_change(close, 21),
        change_6m=_change(close, 126),
    )
