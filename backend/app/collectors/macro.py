"""Macro & geopolitical signals collector.

Two sources:
  1. RSS feeds (Reuters world, BBC business, FT markets, ECB news) — always free.
  2. FRED (St. Louis Fed) — for US/EU rates, oil, FX, when API key provided.

Both are best-effort: failures are logged and an empty list is returned.
"""
from __future__ import annotations

from datetime import datetime, date as DateType
from typing import Optional

import feedparser

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)
settings = get_settings()


# Public RSS feeds covering markets, macro and geopolitics
RSS_FEEDS: dict[str, str] = {
    "reuters_business": "https://feeds.reuters.com/reuters/businessNews",
    "ft_markets": "https://www.ft.com/markets?format=rss",
    "bbc_business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "marketwatch_top": "https://feeds.marketwatch.com/marketwatch/topstories/",
}

# Mapping de palabras clave -> sectores afectados
MACRO_KEYWORDS = {
    "rate hike": ["Banks", "Real Estate", "Utilities", "Biotechnology"],
    "rate cut": ["Real Estate", "Utilities"],
    "inflation": ["Consumer Discretionary", "Retail"],
    "oil": ["Airlines", "Transportation", "Energy"],
    "crude": ["Airlines", "Transportation", "Energy"],
    "recession": ["Consumer Discretionary", "Retail", "Industrials"],
    "tariff": ["Industrials", "Technology", "Auto Manufacturers"],
    "china": ["Technology", "Auto Manufacturers", "Semiconductors"],
    "war": ["Energy", "Defense", "Airlines"],
    "sanction": ["Energy", "Banks"],
    "regulation": ["Big Tech", "Banks", "Pharmaceuticals"],
    "fda": ["Biotechnology", "Pharmaceuticals"],
    "lawsuit": [],
    "guidance cut": [],
    "default": ["Banks"],
    "credit": ["Banks", "Real Estate"],
}


def fetch_macro_news(max_per_feed: int = 15) -> list[dict]:
    """Pull recent items from RSS feeds. Returns dicts with title/summary/link/published/source."""
    items: list[dict] = []
    for source_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title = getattr(entry, "title", "")
                if not title:
                    continue
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                link = getattr(entry, "link", "")
                pub_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                pub = datetime(*pub_struct[:6]) if pub_struct else datetime.utcnow()
                items.append({
                    "title": title,
                    "summary": summary[:1000],
                    "link": link,
                    "source": source_name,
                    "published_at": pub,
                })
        except Exception as e:
            log.warning("RSS fetch failed for %s: %s", source_name, e)
    return items


def classify_macro_item(title: str, summary: str) -> tuple[str, list[str], float]:
    """Naive classifier returning (category, affected_sectors, impact_score 0-1)."""
    text = f"{title} {summary}".lower()
    matched_sectors: set[str] = set()
    matched_categories: list[str] = []
    for kw, sectors in MACRO_KEYWORDS.items():
        if kw in text:
            matched_categories.append(kw)
            matched_sectors.update(sectors)
    if not matched_categories:
        return "general", [], 0.1
    category = matched_categories[0]
    # Impact: more keywords matched -> higher impact, capped at 0.9
    impact = min(0.9, 0.3 + 0.15 * len(matched_categories))
    return category, sorted(matched_sectors), impact


def fetch_fred_indicator(series_id: str) -> Optional[float]:
    """Fetch latest value of a FRED series. Returns None if no key or fetch fails."""
    if not settings.fred_api_key:
        return None
    try:
        from fredapi import Fred  # local import to make it optional
        fred = Fred(api_key=settings.fred_api_key)
        s = fred.get_series_latest_release(series_id)
        if s is None or s.empty:
            return None
        val = float(s.dropna().iloc[-1])
        return val
    except Exception as e:
        log.warning("FRED fetch failed for %s: %s", series_id, e)
        return None
