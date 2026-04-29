"use client";

import { useState } from "react";
import { getBacktest } from "@/lib/api";
import type { BacktestOut } from "@/lib/types";
import { fmtPct } from "@/lib/format";

export default function BacktestPage() {
  const [minScore, setMinScore] = useState(65);
  const [holdDays, setHoldDays] = useState(10);
  const [res, setRes] = useState<BacktestOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setRes(await getBacktest(minScore, holdDays));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const inputCls = "bg-paper border border-ink/20 px-3 py-2 text-sm font-mono w-full focus:outline-none focus:border-bear";

  return (
    <div>
      <div className="mb-8">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-2">Backtest</div>
        <h1 className="display-heading text-5xl tracking-tightest">
          ¿Funciona <span className="italic text-bear">la idea</span>?
        </h1>
        <p className="text-ink-light mt-2 max-w-2xl">
          Simula entradas en corto sobre los scores históricos generados por el sistema. Cada idea
          entra al cierre del día de la señal y se cierra en stop, target 2 o tras N días.
        </p>
        <p className="text-xs text-ink-muted mt-2 italic">
          No incluye comisiones, slippage ni costes de borrow. Úsalo como sanity-check.
        </p>
      </div>

      <div className="border border-ink/15 bg-paper-deep/30 p-5 mb-6 grid grid-cols-3 gap-4 items-end max-w-2xl">
        <div>
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Score mín.</label>
          <input type="number" className={inputCls} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Hold días</label>
          <input type="number" className={inputCls} value={holdDays} onChange={(e) => setHoldDays(Number(e.target.value))} />
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="bg-ink text-paper px-4 py-2 text-sm uppercase tracking-widest font-mono hover:bg-bear transition-colors disabled:opacity-50"
        >
          {loading ? "Ejecutando…" : "Ejecutar"}
        </button>
      </div>

      {error && <div className="border border-bear/40 bg-bear/5 p-4 text-sm mb-6"><strong>Error:</strong> {error}</div>}

      {res && (
        <div className="space-y-6">
          <div className="grid md:grid-cols-4 gap-4">
            <Stat label="Trades" value={String(res.n_trades)} />
            <Stat label="Hit rate" value={`${res.win_rate_pct}%`} accent={res.win_rate_pct >= 50 ? "bull" : "bear"} />
            <Stat label="Retorno medio" value={fmtPct(res.avg_return_pct)} accent={res.avg_return_pct > 0 ? "bull" : "bear"} />
            <Stat label="Hold medio" value={`${res.avg_hold_days}d`} />
          </div>

          {Object.keys(res.by_setup).length > 0 && (
            <div className="border border-ink/15">
              <div className="border-b border-ink/15 p-4">
                <h3 className="display-heading text-xl">Por setup</h3>
              </div>
              <table className="w-full compact-table text-sm">
                <thead>
                  <tr className="text-[11px] uppercase tracking-widest text-ink-muted">
                    <th className="text-left p-3 font-medium">Setup</th>
                    <th className="text-right p-3 font-medium">N</th>
                    <th className="text-right p-3 font-medium">Retorno medio</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(res.by_setup).map(([k, v]) => (
                    <tr key={k} className="border-t border-ink/5">
                      <td className="p-3 capitalize">{k.replace("_", " ")}</td>
                      <td className="p-3 text-right font-mono tnum">{v.n}</td>
                      <td className={`p-3 text-right font-mono tnum ${v.avg_pct > 0 ? "text-bull" : "text-bear-bright"}`}>
                        {fmtPct(v.avg_pct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: "bull" | "bear" }) {
  const cls = accent === "bull" ? "text-bull" : accent === "bear" ? "text-bear" : "text-ink";
  return (
    <div className="border border-ink/15 p-4">
      <div className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">{label}</div>
      <div className={`display-heading text-3xl ${cls}`}>{value}</div>
    </div>
  );
}
