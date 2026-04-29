"""Universe definition: which tickers populate each market on first run.

CURATED FOR RETAIL SHORTING:
- US ONLY (NASDAQ + NYSE). European exchanges have wide spreads and
  high borrow costs that make retail shorting impractical with CFDs.
- High liquidity names only (avg daily $vol > 25M): tight spreads,
  reasonable borrow rates, reliable short interest data from Yahoo.
- Mix of mega caps (for trend-following shorts) and well-known
  speculative names (for event/deterioration setups).

yfinance suffix conventions:
  - US (NASDAQ/NYSE): no suffix          (e.g. AAPL)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    country: str
    currency: str
    tickers: tuple[str, ...]


# --- NASDAQ liquid mega/large caps + traders' favorites ---
NASDAQ_TICKERS = (
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "COST", "ADBE",
    # Large caps with consistent volume
    "AMD", "INTC", "CSCO", "PEP", "NFLX", "QCOM", "TMUS", "AMAT", "TXN", "INTU",
    "BKNG", "SBUX", "ISRG", "GILD", "MDLZ", "ADP", "MU", "LRCX", "REGN", "VRTX",
    "PANW", "KLAC", "MRVL", "SNPS", "CDNS", "ORLY", "FTNT", "ADSK", "MELI",
    "PYPL", "MAR", "ABNB", "DDOG", "TEAM", "ZS", "CRWD", "MDB", "DOCU", "ROKU",
    # High-volume speculative / often shorted
    "PLTR", "COIN", "HOOD", "RIVN", "LCID", "SOFI", "DKNG", "HIMS", "UPST",
    "CVNA", "ENPH", "SEDG", "RUN", "SNAP", "PINS", "AFRM", "CHWY", "RBLX", "U",
    "NET", "SHOP", "TWLO", "SPOT", "ZM", "MSTR", "RIOT", "MARA",
    # Auto/EV
    "NIO", "XPEV", "LI",
)

# --- NYSE liquid mega/large caps + traders' favorites ---
NYSE_TICKERS = (
    # Mega caps
    "BRK-B", "JPM", "V", "MA", "WMT", "JNJ", "PG", "UNH", "HD", "BAC",
    "XOM", "CVX", "PFE", "KO", "DIS", "MCD", "T", "VZ", "NKE", "CRM",
    "ORCL", "ABT", "TMO", "DHR", "LIN", "WFC", "C", "GS", "MS", "BLK",
    # Industrials, energy, materials
    "BA", "CAT", "GE", "DE", "MMM", "LMT", "RTX", "NOC", "GD", "F",
    "GM", "UBER", "LYFT", "DASH",
    # Retail / Consumer
    "TGT", "LOW", "BBY", "M", "AEO", "ANF", "GAP",
    # Energy
    "BKR", "SLB", "OXY", "DVN", "FCX", "NEM", "AA", "X", "CLF",
    # International ADRs
    "BABA", "PDD", "JD", "BIDU",
    # Speculative / often shorted
    "GME", "AMC", "SPCE",
)


MARKETS: tuple[Market, ...] = (
    Market("NASDAQ", "NASDAQ", "US", "USD", NASDAQ_TICKERS),
    Market("NYSE",   "NYSE",   "US", "USD", NYSE_TICKERS),
)


def all_tickers() -> list[tuple[str, str, str, str]]:
    """Return list of (ticker, exchange, country, currency) for the whole universe."""
    out = []
    for m in MARKETS:
        for t in m.tickers:
            out.append((t, m.code, m.country, m.currency))
    return out