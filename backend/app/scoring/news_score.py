"""News & catalysts score for LONG bias (0-100).

Higher score = stronger positive catalyst environment.

Critical concept for the AGGRESSIVE profile:
We deliberately favor catalysts that are 3-10 days OLD over fresh ones.
Reason: by the time retail reads a fresh headline, the move is already done.
A catalyst that's 5-7 days old where price is still digesting (not exhausted)
is where realistic edge exists for retail.
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

    # --- "Digesting catalyst" sweet spot detection ---
    catalyst_is_digesting = False
    if strongest_pos_age is not None:
        if 3.0 <= strongest_pos_age <= 10.0:
            # Sweet spot: news has been digested by market but still has runway
            catalyst_is_digesting = True
            score += 8  # bonus for the realistic-edge zone
        elif strongest_pos_age < 1.0 and strongest_pos_strength > 0.5:
            # Very fresh strong news: chasing risk, slight penalty for retail
            score -= 4

    # Sort & truncate top lists
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


# Backward-compat alias
score_news = score_news_long