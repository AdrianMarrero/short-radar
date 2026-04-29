import type {
  ScoreOut,
  TickerDetailOut,
  MacroEventOut,
  JobRunOut,
  StatsOut,
  BacktestOut,
  WeightsOut,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "";

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: ADMIN_TOKEN ? { "X-Admin-Token": ADMIN_TOKEN } : undefined,
  });
  if (!res.ok) {
    throw new Error(`API ${path} -> ${res.status}`);
  }
  return res.json();
}

async function apiPost<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(ADMIN_TOKEN ? { "X-Admin-Token": ADMIN_TOKEN } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${path} -> ${res.status}`);
  }
  return res.json();
}

export interface RankingFilters {
  market?: string;
  sector?: string;
  min_score?: number;
  max_squeeze?: number;
  min_liquidity?: number;
  setup?: string;
  horizon?: string;
  limit?: number;
}

export const fetcher = (path: string) => apiGet(path);

export async function getRanking(filters: RankingFilters = {}): Promise<ScoreOut[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  return apiGet<ScoreOut[]>(`/api/ranking?${params.toString()}`);
}

export const getTicker = (ticker: string) =>
  apiGet<TickerDetailOut>(`/api/ticker/${encodeURIComponent(ticker)}`);

export const getMacro = (limit = 20) =>
  apiGet<MacroEventOut[]>(`/api/macro?limit=${limit}`);

export const getJobRuns = () => apiGet<JobRunOut[]>(`/api/jobs/runs`);

export const getStats = () => apiGet<StatsOut>(`/api/stats`);

export const getBacktest = (min_score = 65, hold_days = 10) =>
  apiGet<BacktestOut>(`/api/backtest?min_score=${min_score}&hold_days=${hold_days}`);

export const getWeights = () => apiGet<WeightsOut>(`/api/config/weights`);

export const triggerDailyJob = (limit?: number) =>
  apiPost<{ status: string }>(`/api/jobs/run-daily${limit ? `?limit=${limit}` : ""}`);

export interface PositionSizeIn {
  capital: number;
  risk_pct: number;
  entry: number;
  stop: number;
  target?: number;
}
export interface PositionSizeOut {
  shares: number;
  risk_per_share: number | null;
  max_loss: number | null;
  max_gain: number | null;
  risk_reward: number | null;
  warning: string | null;
}

export const calcPositionSize = (payload: PositionSizeIn) =>
  apiPost<PositionSizeOut>(`/api/risk/position-size`, payload);
