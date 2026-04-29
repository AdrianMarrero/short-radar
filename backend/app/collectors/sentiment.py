"""Simple lexicon-based sentiment & impact classifier for news.

Loughran-McDonald-style word lists (financial domain) trimmed to the most
common terms. Output:
  - sentiment_score in [-1, +1]   negative <-> positive
  - impact_score in [0, 1]        how market-moving the headline is
  - category in {earnings, regulatory, downgrade, lawsuit, dilution,
                 m_a, product, insider, guidance, upgrade, generic}
"""
from __future__ import annotations

import re

# --- Word lists ---
NEG_WORDS = {
    "miss", "misses", "missed", "loss", "losses", "weak", "weaker", "weakness",
    "decline", "declines", "declined", "drop", "drops", "dropped", "fall", "falls", "fell",
    "fraud", "lawsuit", "investigation", "probe", "subpoena", "settlement",
    "downgrade", "downgraded", "underperform", "sell", "bearish",
    "guidance cut", "lower guidance", "below expectations", "warning", "profit warning",
    "dilution", "dilutive", "offering", "secondary offering", "convertible",
    "default", "bankruptcy", "restructuring", "layoff", "layoffs", "fired",
    "delay", "delayed", "halt", "halted", "recall", "recalled",
    "fda rejection", "rejected", "fail", "failed", "failure",
    "scandal", "accounting", "restate", "restatement", "going concern",
    "short", "shorted", "shortseller", "fraud", "manipulation",
    "ban", "banned", "tariff", "sanction", "sanctioned",
    "missed earnings", "missed revenue", "missed eps",
    "cuts", "cutting", "slashed", "slashing",
}

POS_WORDS = {
    "beat", "beats", "beats estimates", "beats expectations", "exceed", "exceeds",
    "record", "growth", "growing", "strong", "stronger", "strength",
    "rise", "rises", "rose", "surge", "surged", "rally", "rallied",
    "upgrade", "upgraded", "outperform", "buy", "bullish", "overweight",
    "guidance raised", "raised guidance", "above expectations",
    "buyback", "repurchase", "dividend increase",
    "approval", "approved", "fda approval", "partnership", "agreement",
    "acquisition", "acquired", "merger", "deal", "takeover", "bid",
    "expansion", "launch", "launched", "milestone",
    "profit", "profitable", "profitability",
    "insider buying", "bought shares",
}

# Categorías
CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("earnings",   ["earnings", "eps", "revenue", "quarterly results", "q1", "q2", "q3", "q4"]),
    ("guidance",   ["guidance", "outlook", "forecast"]),
    ("regulatory", ["fda", "sec", "ftc", "doj", "cnmv", "esma", "regulator", "regulation"]),
    ("lawsuit",    ["lawsuit", "sued", "investigation", "probe", "subpoena", "class action"]),
    ("downgrade",  ["downgrade", "downgraded", "cut to sell", "underperform"]),
    ("upgrade",    ["upgrade", "upgraded", "raised to buy", "outperform"]),
    ("dilution",   ["offering", "secondary", "convertible", "dilution", "dilutive", "share issuance"]),
    ("m_a",        ["acquisition", "acquired", "merger", "takeover", "buyout", "bid"]),
    ("product",    ["launch", "launches", "announces product", "unveil", "release"]),
    ("insider",    ["insider", "13d", "13g", "form 4"]),
]

HIGH_IMPACT_WORDS = {
    "fraud", "bankruptcy", "investigation", "probe", "subpoena", "halted",
    "fda rejection", "going concern", "default", "miss", "misses",
    "warning", "profit warning", "dilution", "offering", "downgrade",
    "scandal", "restated", "restatement", "lawsuit",
    "acquisition", "buyout", "merger", "takeover",
    "approval", "buyback", "guidance raised",
}


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s'-]", " ", text)
    return text.split()


def _phrase_count(text: str, phrases: set[str]) -> int:
    text = text.lower()
    count = 0
    for p in phrases:
        if " " in p:
            count += text.count(p)
        else:
            # match as word
            count += sum(1 for tok in _tokenize(text) if tok == p)
    return count


def analyze_news(title: str, summary: str = "") -> tuple[float, float, str]:
    """Return (sentiment, impact, category)."""
    text = f"{title}. {summary}"

    neg = _phrase_count(text, NEG_WORDS)
    pos = _phrase_count(text, POS_WORDS)
    high = _phrase_count(text, HIGH_IMPACT_WORDS)

    if neg + pos == 0:
        sentiment = 0.0
    else:
        sentiment = (pos - neg) / max(1, neg + pos)
        sentiment = max(-1.0, min(1.0, sentiment))

    # Impact base from total signal density, boosted by high-impact words
    total = neg + pos
    impact = min(1.0, 0.15 + 0.1 * total + 0.2 * high)

    # Category
    text_low = text.lower()
    category = "generic"
    for cat, patterns in CATEGORY_PATTERNS:
        if any(p in text_low for p in patterns):
            category = cat
            break

    return round(sentiment, 3), round(impact, 3), category
