"""News & catalysts score for LONG bias (0-100).

CRITICAL CONCEPT (validated by user, do NOT change):
We deliberately favor catalysts that are 3-10 days OLD over fresh ones.
Reason: by the time retail reads a fresh headline, the move is already
done. A catalyst that's 5-7 days old where price is still digesting
(not exhausted) is where realistic edge exists for retail.

v2 redesign exposes a second function `compute_catalyst_score` that
collapses the breakdown into a single 0-100 catalyst factor. The
3-10 day digestion window is the cornerstone of that score and is
preserved exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass
class NewsScoreBreakdown:
    score: float
    has_negative_catalyst: bool
    has_positive_catalyst: bool
    catalyst_age_days: float | None     # age of strongest catalyst
    catalyst_is_digesting: bool          # 3-10 days old, not exhausted
    top_negative_titles: list[str]
    top_positive_titles: list[str]


# Categories that act as strong positive catalysts (worth chasing, with care)
POSITIVE_BOOST_CATEGORIES = {
    "upgrade", "m_a", "product",
    "earnings",         # only if positive sentiment, otherwise negative
    "regulatory",       # FDA approval, gov contract
    "guidance",         # raised guidance
}

# Categories of strong negative catalysts (kill the long thesis)
NEGATIVE_BOOST_CATEGORIES = {
    "lawsuit", "downgrade", "dilution", "fraud",
}


def score_news_long(items: Iterable, now: datetime | None = None) -> NewsScoreBreakdown:
    """Returns long-bias news score.

    Algorithm:
      - For each news item, weight by recency × impact
      - POSITIVE sentiment increases score; NEGATIVE decreases
      - "Digesting" sweet spot: 3-10 days old positive catalyst gets bonus
      - Fresh (<24h) very positive news gets PENALIZED for chasing risk
    """
    now = now or datetime.utcnow()
    score = 50.0
    has_neg = False
    has_pos = False
    top_neg: list[tuple[float, str]] = []
    top_pos: list[tuple[float, str]] = []
    strongest_pos_age: float | None = None
    strongest_pos_strength = 0.0

    items = list(items)
    if not items:
        return NewsScoreBreakdown(50.0, False, False, None, False, [], [])

    total_weight = 0.0
    weighted_sentiment = 0.0

    for it in items:
        # Recency in days
        days = max(0.0, (now - it.published_at).total_seconds() / 86400.0)
        recency = max(0.05, 1.0 / (1.0 + days / 5.0))

        impact = float(it.impact_score or 0.0)
        sentiment = float(it.sentiment_score or 0.0)
        cat = (it.category or "").lower()

        weight = recency * (0.3 + 0.7 * impact)
        weighted_sentiment += sentiment * weight  # POSITIVE sentiment -> POSITIVE score
        total_weight += weight

        # Track top items
        score_item = sentiment * impact
        if score_item > 0.15:
            has_pos = True
            top_pos.append((score_item, it.title))
            if score_item > strongest_pos_strength:
                strongest_pos_strength = score_item
                strongest_pos_age = days
        elif score_item < -0.15:
            has_neg = True
            top_neg.append((-score_item, it.title))

        # Category boosts
        if cat in POSITIVE_BOOST_CATEGORIES and sentiment > 0:
            score += 5 * recency
        if cat in NEGATIVE_BOOST_CATEGORIES and sentiment < 0:
            score -= 6 * recency

    if total_weight > 0:
        avg = weighted_sentiment / total_weight
        score += avg * 30.0

    # --- "Digesting catalyst" sweet spot detection (PRESERVED) ---
    catalyst_is_digesting = False
    if strongest_pos_age is not None:
        if 3.0 <= strongest_pos_age <= 10.0:
            catalyst_is_digesting = True
            score += 8
        elif strongest_pos_age < 1.0 and strongest_pos_strength > 0.5:
            score -= 4

    top_neg.sort(reverse=True)
    top_pos.sort(reverse=True)

    score = max(0.0, min(100.0, score))
    return NewsScoreBreakdown(
        score=score,
        has_negative_catalyst=has_neg,
        has_positive_catalyst=has_pos,
        catalyst_age_days=strongest_pos_age,
        catalyst_is_digesting=catalyst_is_digesting,
        top_negative_titles=[t for _, t in top_neg[:3]],
        top_positive_titles=[t for _, t in top_pos[:3]],
    )


def compute_catalyst_score(news: NewsScoreBreakdown) -> float:
    """Collapse the news breakdown into a single 0-100 factor for the
    new weighted-score formula in engine.py.

    The 3-10 day digestion window (from `score_news_long`) is the core.
    This function does not RECOMPUTE digestion; it consumes the flag.

    Schedule:
      - Start at 50 (neutral baseline).
      - +30 if positive catalyst AND digesting (sweet spot).
      - +10 if positive catalyst but fresh (<3d) — chase risk, modest credit.
      - +5 if positive catalyst but stale (>10d) — already priced.
      - -40 if negative catalyst — kills the long thesis.
      - 0 if no catalysts.
    Final clamp [0, 100].
    """
    score = 50.0
    age = news.catalyst_age_days

    if news.has_negative_catalyst:
        score -= 40

    if news.has_positive_catalyst:
        if news.catalyst_is_digesting:
            score += 30
        elif age is not None and age < 3.0:
            score += 10
        else:
            score += 5

    return max(0.0, min(100.0, score))


# Backward-compat alias
score_news = score_news_long
