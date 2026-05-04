export type SetupType =
  | "deterioration"
  | "event"
  | "technical"
  | "overextension"
  | "avoid_squeeze";

export type Conviction = "low" | "medium" | "high";

export interface ScoreOut {
  instrument_id: number;
  ticker: string;
  name: string;
  exchange: string;
  sector: string;
  last_close: number | null;
  change_1d: number | null;
  change_5d: number | null;
  change_1m: number | null;
  total_score: number;
  technical_score: number;
  news_score: number;
  fundamental_score: number;
  macro_score: number;
  squeeze_risk_score: number;
  liquidity_score: number;
  setup_type: SetupType;
  conviction: Conviction;
  horizon: string;
  entry_price: number | null;
  stop_price: number | null;
  target_1: number | null;
  target_2: number | null;
  invalidation_reason: string;
}

export interface InstrumentOut {
  id: number;
  ticker: string;
  name: string;
  exchange: string;
  country: string;
  currency: string;
  sector: string;
  industry: string;
  market_cap: number | null;
}

export interface TechnicalsOut {
  date: string;
  sma_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
  ema_20: number | null;
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  atr_14: number | null;
  relative_volume: number | null;
  support_level: number | null;
  resistance_level: number | null;
  high_52w: number | null;
  low_52w: number | null;
  change_1d: number | null;
  change_5d: number | null;
  change_1m: number | null;
  change_6m: number | null;
}

export interface FundamentalsOut {
  period: string;
  revenue: number | null;
  revenue_growth_yoy: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  free_cash_flow: number | null;
  debt: number | null;
  cash: number | null;
  eps: number | null;
  pe: number | null;
}

export interface ShortDataOut {
  date: string;
  short_interest: number | null;
  short_percent_float: number | null;
  days_to_cover: number | null;
  float_shares: number | null;
}

export interface NewsItemOut {
  title: string;
  source: string;
  url: string;
  published_at: string;
  summary: string;
  sentiment_score: number;
  impact_score: number;
  category: string;
}

export interface PriceOut {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface TickerDetailOut {
  instrument: InstrumentOut;
  score: ScoreOut | null;
  technicals: TechnicalsOut | null;
  fundamentals: FundamentalsOut | null;
  short_data: ShortDataOut | null;
  recent_prices: PriceOut[];
  recent_news: NewsItemOut[];
  explanation: string;
}

export interface MacroEventOut {
  date: string;
  region: string;
  category: string;
  title: string;
  summary: string;
  impact_score: number;
  affected_sectors: string;
}

export interface JobRunOut {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  instruments_processed: number;
  scores_generated: number;
  error: string;
  triggered_by: string;
}

export interface StatsOut {
  total_instruments: number;
  total_scores_today: number;
  last_job_run: JobRunOut | null;
  avg_score: number;
  top_setup_distribution: Record<string, number>;
}

export interface BacktestOut {
  n_trades: number;
  win_rate_pct: number;
  avg_return_pct: number;
  avg_hold_days: number;
  by_setup: Record<string, { n: number; avg_pct: number }>;
}

export interface WeightsOut {
  technical: number;
  news: number;
  fundamental: number;
  macro: number;
  liquidity: number;
}

// -------- Trades (operations journal) --------

export type TradeStatus = "open" | "closed_win" | "closed_loss" | "stopped";
export type TradeProfile = "conservative" | "aggressive";

export interface TradeIn {
  instrument_id?: number;
  ticker?: string;
  setup_type?: string;
  profile: TradeProfile;
  capital_eur: number;
  entry_price: number;
  entry_date?: string;
  stop_price?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  notes?: string;
}

export interface TradeCloseIn {
  exit_price: number;
  exit_date?: string;
  notes?: string;
}

export interface TradeOut {
  id: number;
  instrument_id: number;
  ticker: string;
  name: string;
  setup_type: string;
  profile: TradeProfile;
  capital_eur: number;
  entry_price: number;
  entry_date: string;
  stop_price: number | null;
  target_1: number | null;
  target_2: number | null;
  exit_price: number | null;
  exit_date: string | null;
  status: TradeStatus;
  notes: string;
  pnl_pct: number | null;
  pnl_eur: number | null;
  created_at: string;
  updated_at: string;
  current_price: number | null;
  pnl_pct_live: number | null;
  pnl_eur_live: number | null;
  days_held: number | null;
}

export interface TradeStatsBucket {
  n: number;
  n_closed: number;
  win_rate_pct: number;
  avg_return_pct: number;
  total_pnl_eur: number;
}

export interface TradeStatsOut {
  total: number;
  open: number;
  closed: number;
  win_rate_pct: number;
  avg_return_pct: number;
  avg_days_held: number;
  total_pnl_eur: number;
  best_trade_pct: number | null;
  worst_trade_pct: number | null;
  best_trade_ticker: string | null;
  worst_trade_ticker: string | null;
  by_setup: Record<string, TradeStatsBucket>;
  by_profile: Record<string, TradeStatsBucket>;
}
