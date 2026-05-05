"""Risk classification — replaces the binary conservative/aggressive split.

A stock is categorized into ONE of four risk profiles based on its
fundamentals (market cap, beta) and price-action (vol regime, setup type).
The frontend's `/conservative` and `/aggressive` endpoints become VIEWS
over these categories rather than being computed during scoring.

Categories:
  - investment:    large-cap, low beta, sustained uptrend, low realized
                   vol. Suitable for buy-and-hold positional trades.
  - swing_trade:   mid/large-cap with moderate vol. Trend or breakout
                   setups. The default "good idea" bucket.
  - speculative:   small-mid cap, higher beta or higher vol. Catalysts
                   and emerging breakouts. Higher risk/reward.
  - cyclical:      sector-momentum / macro-driven names with broad
                   industry tailwind. Volatility is event-driven.
"""
from __future__ import annotations

from typing import Optional

from app.scoring.technicals import TechnicalSnapshot


# Market cap thresholds in USD (yfinance returns marketCap in USD even
# for European tickers — close enough for classification purposes).
LARGE_CAP_USD = 10_000_000_000     # >= $10B
MID_CAP_USD = 2_000_000_000        # >= $2B and < $10B


def classify_category_long(
    *,
    snap: Optional[TechnicalSnapshot],
    info,
    setup_type: str,
    beta: Optional[float],
    has_positive_catalyst: bool,
    has_sector_momentum: bool,
) -> str:
    """Return one of: investment / swing_trade / speculative / cyclical.

    Rules (evaluated in order — first match wins):
      1. Cyclical: explicit sector momentum signal AND macro-tailwind
         setup ('momentum' or large positive macro_score signal).
      2. Investment: large-cap, low realized vol (<= 0.30), low beta
         (<= 1.3 if known), confirmed structural uptrend.
      3. Speculative: small-cap, OR realized vol > 0.50, OR beta > 2,
         OR setup is 'breakout' / 'reversion' / 'catalyst' on a non-
         large-cap.
      4. Default: swing_trade.
    """
    market_cap = _market_cap(info)
    realized_vol = getattr(snap, "realized_vol_30d", None) if snap else None

    # 1. Cyclical: macro-driven names with sector tailwind
    if has_sector_momentum and setup_type in ("momentum",):
        return "cyclical"

    # 2. Investment: large-cap, low vol, low beta, confirmed trend
    is_large_cap = market_cap is not None and market_cap >= LARGE_CAP_USD
    is_low_vol = realized_vol is None or realized_vol <= 0.30
    is_low_beta = beta is None or beta <= 1.3
    if is_large_cap and is_low_vol and is_low_beta and setup_type in ("trend",):
        return "investment"

    # 3. Speculative: REQUIRES positive evidence — small cap, high realized
    # vol, or high beta. Setup type alone is NOT enough to condemn a ticker
    # to speculative; doing so misclassifies large caps when yfinance info
    # is unavailable (rate-limited or stale).
    is_small_cap = market_cap is not None and market_cap < MID_CAP_USD
    is_high_vol = realized_vol is not None and realized_vol > 0.50
    is_high_beta = beta is not None and beta > 2.0

    if is_small_cap or is_high_vol or is_high_beta:
        return "speculative"

    # 4. Default — when we lack the data to confidently classify, swing_trade
    # is the safer bucket (visible in the Conservative view) than speculative.
    return "swing_trade"


def _market_cap(info) -> Optional[float]:
    if info is None:
        return None
    mc = getattr(info, "market_cap", None)
    if mc is None:
        return None
    try:
        v = float(mc)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None
