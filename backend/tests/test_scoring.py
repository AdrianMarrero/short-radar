"""Smoke tests for scoring engine and indicators.

Run with: pytest backend/tests
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.collectors.sentiment import analyze_news
from app.scoring.technicals import compute_technical_snapshot
from app.scoring.engine import compute_final_score
from app.scoring.other_scores import score_squeeze_risk, score_liquidity


def _fake_history(n=260, start=100.0, drift=-0.001, vol=0.02, seed=0):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, size=n)
    closes = start * np.exp(np.cumsum(rets))
    highs = closes * (1 + np.abs(rng.normal(0, vol/2, size=n)))
    lows  = closes * (1 - np.abs(rng.normal(0, vol/2, size=n)))
    opens = closes * (1 + rng.normal(0, vol/2, size=n))
    vols  = rng.integers(500_000, 2_000_000, size=n).astype(float)
    idx = pd.date_range(end=datetime.utcnow(), periods=n, freq="B")
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols}, index=idx)


def test_technical_snapshot_basic():
    df = _fake_history()
    snap = compute_technical_snapshot(df)
    assert snap is not None
    assert snap.last_close > 0
    assert snap.sma_20 is not None
    assert snap.rsi_14 is not None
    assert 0 <= snap.rsi_14 <= 100


def test_engine_returns_score_in_range():
    df = _fake_history(drift=-0.002)  # downtrend
    snap = compute_technical_snapshot(df)
    fs = compute_final_score(
        snap=snap,
        news_items=[],
        info=None,
        macro_events=[],
        avg_volume=df["volume"].tail(20).mean(),
    )
    assert 0 <= fs.total <= 100
    assert fs.setup_type in {"deterioration", "event", "technical", "overextension", "avoid_squeeze"}
    assert fs.conviction in {"low", "medium", "high"}


def test_engine_penalises_strong_uptrend():
    """A clear uptrend at 52w highs should NOT score high as a short."""
    df = _fake_history(drift=0.003, n=260)
    snap = compute_technical_snapshot(df)
    fs = compute_final_score(snap, [], None, [], avg_volume=df["volume"].tail(20).mean())
    # Uptrend should yield a sub-50 short score
    assert fs.total < 60


def test_squeeze_extreme_marks_high():
    class Info:
        short_percent_of_float = 0.40
        short_ratio = 9.5
        float_shares = 30_000_000
    res = score_squeeze_risk(Info(), has_negative_catalyst=False)
    assert res.classification in {"high", "extreme"}


def test_sentiment_negative_phrase():
    s, i, c = analyze_news("Company X misses earnings, cuts guidance")
    assert s < 0
    assert i > 0.3
    assert c in {"earnings", "guidance"}


def test_sentiment_positive_phrase():
    s, _, _ = analyze_news("Company X beats earnings, raises guidance")
    assert s > 0


def test_liquidity_score_low_for_thin_volume():
    res = score_liquidity(avg_volume=20_000, last_close=10.0)
    assert res.score < 40
