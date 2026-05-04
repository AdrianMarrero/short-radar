"""Pydantic response schemas."""
from __future__ import annotations

from datetime import datetime, date as DateType
from typing import Optional

from pydantic import BaseModel, ConfigDict


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    name: str
    exchange: str
    country: str
    currency: str
    sector: str
    industry: str
    market_cap: Optional[float] = None


class TechnicalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: DateType
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    ema_20: Optional[float]
    rsi_14: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    atr_14: Optional[float]
    relative_volume: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]
    high_52w: Optional[float]
    low_52w: Optional[float]
    change_1d: Optional[float]
    change_5d: Optional[float]
    change_1m: Optional[float]
    change_6m: Optional[float]


class FundamentalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: str
    revenue: Optional[float]
    revenue_growth_yoy: Optional[float]
    gross_margin: Optional[float]
    operating_margin: Optional[float]
    free_cash_flow: Optional[float]
    debt: Optional[float]
    cash: Optional[float]
    eps: Optional[float]
    pe: Optional[float]


class ShortDataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: DateType
    short_interest: Optional[float]
    short_percent_float: Optional[float]
    days_to_cover: Optional[float]
    float_shares: Optional[float]


class NewsItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    source: str
    url: str
    published_at: datetime
    summary: str
    sentiment_score: float
    impact_score: float
    category: str


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: DateType
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]


class ScoreOut(BaseModel):
    """Compact ranking row."""
    instrument_id: int
    ticker: str
    name: str
    exchange: str
    sector: str
    last_close: Optional[float]
    change_1d: Optional[float]
    change_5d: Optional[float]
    change_1m: Optional[float]
    total_score: float
    technical_score: float
    news_score: float
    fundamental_score: float
    macro_score: float
    squeeze_risk_score: float
    liquidity_score: float
    setup_type: str
    conviction: str
    horizon: str
    entry_price: Optional[float]
    stop_price: Optional[float]
    target_1: Optional[float]
    target_2: Optional[float]
    invalidation_reason: str


class TickerDetailOut(BaseModel):
    instrument: InstrumentOut
    score: Optional[ScoreOut]
    technicals: Optional[TechnicalsOut]
    fundamentals: Optional[FundamentalsOut]
    short_data: Optional[ShortDataOut]
    recent_prices: list[PriceOut]
    recent_news: list[NewsItemOut]
    explanation: str


class MacroEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: DateType
    region: str
    category: str
    title: str
    summary: str
    impact_score: float
    affected_sectors: str


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    instruments_processed: int
    scores_generated: int
    error: str
    triggered_by: str


class PositionSizeIn(BaseModel):
    capital: float
    risk_pct: float = 1.5
    entry: float
    stop: float
    target: Optional[float] = None


class PositionSizeOut(BaseModel):
    shares: int
    risk_per_share: Optional[float]
    max_loss: Optional[float]
    max_gain: Optional[float]
    risk_reward: Optional[float]
    warning: Optional[str]


class WeightsIn(BaseModel):
    technical: float
    news: float
    fundamental: float
    macro: float
    liquidity: float


class StatsOut(BaseModel):
    total_instruments: int
    total_scores_today: int
    last_job_run: Optional[JobRunOut]
    avg_score: float
    top_setup_distribution: dict[str, int]


class BacktestOut(BaseModel):
    n_trades: int
    win_rate_pct: float
    avg_return_pct: float
    avg_hold_days: float
    by_setup: dict[str, dict]


# -------- Trades (operations journal) --------


class TradeIn(BaseModel):
    """Payload to open a new trade. Either instrument_id or ticker is required."""
    instrument_id: Optional[int] = None
    ticker: Optional[str] = None
    setup_type: str = ""
    profile: str = "conservative"  # conservative / aggressive
    capital_eur: float
    entry_price: float
    entry_date: Optional[DateType] = None  # defaults to today on the server
    stop_price: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    notes: str = ""


class TradeCloseIn(BaseModel):
    exit_price: float
    exit_date: Optional[DateType] = None  # defaults to today on the server
    notes: Optional[str] = None  # appended to existing notes if provided


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    instrument_id: int
    ticker: str
    name: str
    setup_type: str
    profile: str
    capital_eur: float
    entry_price: float
    entry_date: DateType
    stop_price: Optional[float]
    target_1: Optional[float]
    target_2: Optional[float]
    exit_price: Optional[float]
    exit_date: Optional[DateType]
    status: str
    notes: str
    pnl_pct: Optional[float]
    pnl_eur: Optional[float]
    created_at: datetime
    updated_at: datetime

    # Derived live fields (only meaningful while open)
    current_price: Optional[float] = None
    pnl_pct_live: Optional[float] = None
    pnl_eur_live: Optional[float] = None
    days_held: Optional[int] = None


class TradeStatsBucket(BaseModel):
    n: int
    n_closed: int
    win_rate_pct: float
    avg_return_pct: float
    total_pnl_eur: float


class TradeStatsOut(BaseModel):
    total: int
    open: int
    closed: int
    win_rate_pct: float
    avg_return_pct: float
    avg_days_held: float
    total_pnl_eur: float
    best_trade_pct: Optional[float]
    worst_trade_pct: Optional[float]
    best_trade_ticker: Optional[str]
    worst_trade_ticker: Optional[str]
    by_setup: dict[str, TradeStatsBucket]
    by_profile: dict[str, TradeStatsBucket]
