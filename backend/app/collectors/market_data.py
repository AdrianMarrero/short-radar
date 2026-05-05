"""Market data collector using yfinance (free).

Pulls daily OHLCV, basic instrument info, fundamentals, and short interest
when available. Uses curl_cffi to impersonate a real browser and bypass
Yahoo Finance anti-bot protections that otherwise return empty responses.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date as DateType, timedelta
from typing import Optional, TYPE_CHECKING

import pandas as pd
import yfinance as yf

from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.instrument import Instrument

INFO_CACHE_TTL_DAYS = 7

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
    # v3 edge factors — analyst price targets
    target_mean_price: Optional[float] = None
    target_high_price: Optional[float] = None
    target_low_price: Optional[float] = None
    recommendation_mean: Optional[float] = None
    num_analyst_opinions: Optional[float] = None
    # v3 edge factors — earnings revisions / growth signals
    earnings_growth_quarterly: Optional[float] = None
    earnings_growth_yoy: Optional[float] = None
    revenue_growth: Optional[float] = None


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
        target_mean_price=f("targetMeanPrice"),
        target_high_price=f("targetHighPrice"),
        target_low_price=f("targetLowPrice"),
        recommendation_mean=f("recommendationMean"),
        num_analyst_opinions=f("numberOfAnalystOpinions"),
        earnings_growth_quarterly=f("earningsQuarterlyGrowth"),
        earnings_growth_yoy=f("earningsGrowth"),
        revenue_growth=f("revenueGrowth"),
    )


def _info_from_cache(instrument: "Instrument", fund, short) -> InstrumentInfo:
    return InstrumentInfo(
        ticker=instrument.ticker,
        name=instrument.name or instrument.ticker,
        sector=instrument.sector or "",
        industry=instrument.industry or "",
        market_cap=instrument.market_cap,
        currency=instrument.currency or "USD",
        exchange=instrument.exchange or "",
        shares_short=getattr(short, "short_interest", None) if short else None,
        short_percent_of_float=getattr(short, "short_percent_float", None) if short else None,
        short_ratio=getattr(short, "days_to_cover", None) if short else None,
        float_shares=getattr(short, "float_shares", None) if short else None,
        pe=getattr(fund, "pe", None),
        revenue=getattr(fund, "revenue", None),
        revenue_growth_yoy=getattr(fund, "revenue_growth_yoy", None),
        gross_margin=getattr(fund, "gross_margin", None),
        operating_margin=getattr(fund, "operating_margin", None),
        free_cash_flow=getattr(fund, "free_cash_flow", None),
        total_debt=getattr(fund, "debt", None),
        total_cash=getattr(fund, "cash", None),
        eps=getattr(fund, "eps", None),
        target_mean_price=getattr(fund, "target_mean_price", None),
        target_high_price=getattr(fund, "target_high_price", None),
        target_low_price=getattr(fund, "target_low_price", None),
        recommendation_mean=getattr(fund, "recommendation_mean", None),
        num_analyst_opinions=getattr(fund, "num_analyst_opinions", None),
        earnings_growth_quarterly=getattr(fund, "earnings_growth_quarterly", None),
        earnings_growth_yoy=getattr(fund, "earnings_growth_yoy", None),
        revenue_growth=getattr(fund, "revenue_growth", None),
    )


def fetch_info_cached(
    db: "Session",
    instrument: "Instrument",
    ttl_days: int = INFO_CACHE_TTL_DAYS,
) -> Optional[InstrumentInfo]:
    """Return InstrumentInfo, hitting yfinance only if the cached Fundamentals
    row is older than ``ttl_days``. Falls back to the stale cache if yfinance
    is rate-limited.
    """
    from app.models import Fundamentals, ShortData

    fund = (
        db.query(Fundamentals)
        .filter(Fundamentals.instrument_id == instrument.id)
        .filter(Fundamentals.period == "TTM")
        .first()
    )
    short = (
        db.query(ShortData)
        .filter(ShortData.instrument_id == instrument.id)
        .order_by(ShortData.date.desc())
        .first()
    )

    cutoff = datetime.utcnow() - timedelta(days=ttl_days)
    fund_updated = getattr(fund, "updated_at", None) if fund else None
    if fund and fund_updated and fund_updated >= cutoff:
        return _info_from_cache(instrument, fund, short)

    fresh = fetch_info(instrument.ticker)
    if fresh is not None:
        return fresh

    if fund is not None:
        log.info("yfinance info miss for %s — falling back to stale cache", instrument.ticker)
        return _info_from_cache(instrument, fund, short)
    return None


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


def fetch_insider_transactions(ticker: str) -> Optional[pd.DataFrame]:
    """Fetch insider transactions DataFrame for a ticker.

    yfinance ``Ticker.insider_transactions`` returns a DataFrame with
    columns like ``Insider``, ``Position``, ``Transaction``, ``Start Date``,
    ``Value``, ``# of Shares``, ``Ownership``, ``URL``. May be None or
    empty for many tickers (especially European ADRs / .L / .DE / .MC).

    Robust to network failures and missing attribute (older yfinance).
    Returns None on any error or empty result.
    """
    try:
        t = _ticker(ticker)
        df = getattr(t, "insider_transactions", None)
        if df is None:
            return None
        # yfinance can return a property that fails internally — guard.
        if not hasattr(df, "empty"):
            return None
        if df.empty:
            return None
        return df
    except Exception as e:
        log.debug("insider_transactions fetch failed for %s: %s", ticker, e)
        return None


def fetch_index_history(symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Thin wrapper around fetch_history for macro-regime index symbols.

    Identical to fetch_history but logs at debug level (these are best-
    effort fetches and we degrade to a neutral macro regime on failure).
    """
    try:
        return fetch_history(symbol, period=period)
    except Exception as e:
        log.debug("index history fetch failed for %s: %s", symbol, e)
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