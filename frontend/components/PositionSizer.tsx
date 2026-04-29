"use client";

import { useState } from "react";
import { calcPositionSize, type PositionSizeOut } from "@/lib/api";
import { fmtNum, fmtMoney } from "@/lib/format";

interface Props {
  defaultEntry?: number | null;
  defaultStop?: number | null;
  defaultTarget?: number | null;
}

export function PositionSizer({ defaultEntry, defaultStop, defaultTarget }: Props) {
  const [capital, setCapital] = useState(10000);
  const [riskPct, setRiskPct] = useState(1.5);
  const [entry, setEntry] = useState(defaultEntry || 100);
  const [stop, setStop] = useState(defaultStop || 105);
  const [target, setTarget] = useState(defaultTarget || 90);
  const [result, setResult] = useState<PositionSizeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function calc() {
    setLoading(true);
    setError(null);
    try {
      const r = await calcPositionSize({ capital, risk_pct: riskPct, entry, stop, target });
      setResult(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const inputCls = "bg-paper border border-ink/20 px-3 py-2 text-sm font-mono w-full focus:outline-none focus:border-bear";

  return (
    <div className="border border-ink/15 p-5">
      <h3 className="display-heading text-xl mb-1">Calculadora de posición</h3>
      <p className="text-xs text-ink-muted mb-4">Cuántas acciones cubrir para arriesgar el % deseado del capital.</p>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Capital</label>
          <input type="number" className={inputCls} value={capital} onChange={(e) => setCapital(Number(e.target.value))} />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Riesgo %</label>
          <input type="number" step="0.1" className={inputCls} value={riskPct} onChange={(e) => setRiskPct(Number(e.target.value))} />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Entry</label>
          <input type="number" step="0.01" className={inputCls} value={entry} onChange={(e) => setEntry(Number(e.target.value))} />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Stop</label>
          <input type="number" step="0.01" className={inputCls} value={stop} onChange={(e) => setStop(Number(e.target.value))} />
        </div>
        <div className="col-span-2">
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Target</label>
          <input type="number" step="0.01" className={inputCls} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
        </div>
      </div>

      <button
        onClick={calc}
        disabled={loading}
        className="mt-4 w-full bg-ink text-paper px-4 py-2.5 text-sm uppercase tracking-widest font-mono hover:bg-bear transition-colors disabled:opacity-50"
      >
        {loading ? "Calculando…" : "Calcular"}
      </button>

      {error && <div className="mt-3 text-xs text-bear-bright">{error}</div>}

      {result && (
        <div className="mt-4 border-t border-ink/15 pt-4 space-y-2 text-sm font-mono">
          <Row label="Acciones" value={fmtNum(result.shares, 0)} />
          <Row label="Riesgo / acción" value={result.risk_per_share != null ? `$${fmtNum(result.risk_per_share, 2)}` : "—"} />
          <Row label="Pérdida máx." value={result.max_loss != null ? `$${fmtNum(result.max_loss, 2)}` : "—"} highlight />
          <Row label="Ganancia obj." value={result.max_gain != null ? `$${fmtNum(result.max_gain, 2)}` : "—"} positive />
          <Row label="R:R" value={result.risk_reward != null ? `${result.risk_reward}:1` : "—"} />
          {result.warning && (
            <div className="text-xs text-amber border-l-2 border-amber pl-2 mt-3">{result.warning}</div>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, highlight, positive }: { label: string; value: string; highlight?: boolean; positive?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-ink-muted text-xs uppercase tracking-wider">{label}</span>
      <span className={highlight ? "text-bear font-bold" : positive ? "text-bull font-bold" : "text-ink"}>{value}</span>
    </div>
  );
}
