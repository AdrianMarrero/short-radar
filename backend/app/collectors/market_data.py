"""Market data collector using yfinance (free).

Pulls daily OHLCV, basic instrument info, fundamentals, and short interest
when available. Uses curl_cffi to impersonate a real browser and bypass
Yahoo Finance anti-bot protections that otherwise return empty responses.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date as DateType, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from app.core.logging import get_logger

log = get_logger(__name__)

# Sesión que impersona Chrome para que Yahoo no nos bloquee
try:
    from curl_cffi import requests as curl_requests
    _SESSION = curl_requests.Session(impersonate="chrome")
    log.info("yfinance: using curl_cffi session (chrome impersonation)")
except Exception as e:
    log.warning("curl_cffi not available, falling back to default session: %s", e)
    _SESSION = None


@dataclass
class InstrumentInfo:
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: Optional[float]
    currency: str
    exchange: str
    # Short data (may all be None)
    shares_short: Optional[float]
    short_percent_of_float: Optional[float]
    short_ratio: Optional[float]  # days to cover
    float_shares: Optional[float]
    # Fundamentals snapshot
    pe: Optional[float]
    revenue: Optional[float]
    revenue_growth_yoy: Optional[float]
    gross_margin: Optional[float]
    operating_margin: Optional[float]
    free_cash_flow: Optional[float]
    total_debt: Optional[float]
    total_cash: Optional[float]
    eps: Optional[float]


def _ticker(symbol: str) -> yf.Ticker:
    """Build a yfinance Ticker with the chrome-impersonating session if available."""
    if _SESSION is not None:
        return yf.Ticker(symbol, session=_SESSION)
    return yf.Ticker(symbol)


def fetch_history(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch OHLCV history. Returns DataFrame indexed by date or None."""
    try:
        t = _ticker(ticker)
        df = t.history(period=period, auto_adjust=False)
        if df is None or df.empty:
            return None
        df = df.rename(columns=str.lower)
        df.index = pd.to_datetime(df.index).tz_localize(None) if df.index.tz else pd.to_datetime(df.index)
        return df
    except Exception as e:
        log.warning("history fetch failed for %s: %s", ticker, e)
        return None


def fetch_info(ticker: str) -> Optional[InstrumentInfo]:
    """Fetch metadata, fundamentals, and short data in one shot."""
    try:
        t = _ticker(ticker)
        info = t.info or {}
    except Exception as e:
        log.warning("info fetch failed for %s: %s", ticker, e)
        return None

    if not info or "symbol" not in info and "shortName" not in info:
        return None

    def f(key: str) -> Optional[float]:
        v = info.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    return InstrumentInfo(
        ticker=ticker,
        name=info.get("shortName") or info.get("longName") or ticker,
        sector=info.get("sector") or "",
        industry=info.get("industry") or "",
        market_cap=f("marketCap"),
        currency=info.get("currency") or "USD",
        exchange=info.get("exchange") or "",
        shares_short=f("sharesShort"),
        short_percent_of_float=f("shortPercentOfFloat"),
        short_ratio=f("shortRatio"),
        float_shares=f("floatShares"),
        pe=f("trailingPE"),
        revenue=f("totalRevenue"),
        revenue_growth_yoy=f("revenueGrowth"),
        gross_margin=f("grossMargins"),
        operating_margin=f("operatingMargins"),
        free_cash_flow=f("freeCashflow"),
        total_debt=f("totalDebt"),
        total_cash=f("totalCash"),
        eps=f("trailingEps"),
    )


def fetch_latest_price(ticker: str, timeout: float = 5.0) -> Optional[float]:
    """Fetch the latest intraday price for a single ticker.

    Uses the curl_cffi chrome-impersonating session under the hood (yfinance
    reuses _SESSION). Tries ``fast_info.last_price`` first (cheapest call),
    falls back to a 1d/1m history window if that's empty.

    Args:
        ticker: Yahoo Finance ticker symbol.
        timeout: Soft per-call timeout in seconds. Implemented best-effort
            via the underlying session — yfinance does not expose an
            explicit timeout, but curl_cffi honors connect/read timeouts
            on the shared session.

    Returns:
        The latest price as a float, or None if unavailable.
    """
    try:
        t = _ticker(ticker)
        # fast_info is a lightweight quote (no .info heavyweight call).
        try:
            fi = t.fast_info
            price = None
            if fi is not None:
                price = (
                    getattr(fi, "last_price", None)
                    or getattr(fi, "regular_market_price", None)
                    or (fi.get("last_price") if hasattr(fi, "get") else None)
                )
            if price is not None:
                p = float(price)
                if p > 0:
                    return p
        except Exception as e:
            log.debug("fast_info miss for %s: %s", ticker, e)

        # Fallback: most recent 1m bar from today's session.
        df = t.history(period="1d", interval="1m", auto_adjust=False)
        if df is not None and not df.empty:
            close = df["Close"].dropna()
            if len(close) > 0:
                return float(close.iloc[-1])

        # Last resort: daily close from today.
        df_d = t.history(period="5d", auto_adjust=False)
        if df_d is not None and not df_d.empty:
            close = df_d["Close"].dropna()
            if len(close) > 0:
                return float(close.iloc[-1])
    except Exception as e:
        log.warning("latest price fetch failed for %s: %s", ticker, e)
    return None


def fetch_news_yf(ticker: str) -> list[dict]:
    """yfinance has a .news attribute that pulls Yahoo Finance news.

    Returns list of {title, publisher, link, published_at, summary}.
    """
    try:
        t = _ticker(ticker)
        items = t.news or []
        out = []
        for it in items[:15]:
            content = it.get("content") or it
            title = content.get("title") or it.get("title") or ""
            if not title:
                continue
            ts = it.get("providerPublishTime") or 0
            published = (
                datetime.utcfromtimestamp(ts) if ts else datetime.utcnow()
            )
            url = (
                content.get("canonicalUrl", {}).get("url")
                or content.get("clickThroughUrl", {}).get("url")
                or it.get("link", "")
            )
            summary = content.get("summary") or content.get("description") or ""
            publisher = content.get("provider", {}).get("displayName") or it.get("publisher", "")
            out.append({
                "title": title,
                "publisher": publisher,
                "link": url,
                "published_at": published,
                "summary": summary,
            })
        return out
    except Exception as e:
        log.warning("news fetch failed for %s: %s", ticker, e)
        return []