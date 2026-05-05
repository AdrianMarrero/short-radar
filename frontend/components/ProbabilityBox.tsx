"use client";

import type { EdgeClass } from "@/lib/types";

/**
 * ProbabilityBox — displays Monte Carlo probabilistic odds for a signal.
 *
 * Renders nothing when the simulation didn't run (no vol data). Comes in
 * two layouts: compact (inline, for ranking rows) and full (detail page).
 *
 * IMPORTANT: this is INFORMATION, not prediction. The numbers reflect
 * "given the historical volatility of this stock, what's the chance of
 * touching each level before the others". They do NOT predict binary
 * events (earnings, FDA, M&A, surprise macro shocks).
 */

const EDGE_CLASS_LABEL: Record<EdgeClass, string> = {
  high_edge: "Alta ventaja",
  positive_edge: "Ventaja",
  neutral: "Neutral",
  negative_edge: "Sin ventaja",
};

function edgeChipClasses(edge: EdgeClass | null | undefined): string {
  switch (edge) {
    case "high_edge":
      return "bg-bull text-paper border border-bull";
    case "positive_edge":
      return "bg-bull-soft text-bull border border-bull/40";
    case "neutral":
      return "bg-paper-deep text-ink-muted border border-ink/15";
    case "negative_edge":
      return "bg-bear-soft text-bear border border-bear/40";
    default:
      return "bg-paper-deep text-ink-muted border border-ink/15";
  }
}

function fmtPctOdds(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

function fmtR(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}R`;
}

export function ProbabilityBox({
  probTarget1,
  probTarget2,
  probStop,
  probExpire,
  expectedR,
  edgeClass,
  compact = false,
}: {
  probTarget1?: number | null;
  probTarget2?: number | null;
  probStop?: number | null;
  probExpire?: number | null;
  expectedR?: number | null;
  edgeClass?: EdgeClass | null;
  compact?: boolean;
}) {
  if (probTarget1 == null) return null;

  const chipCls = edgeChipClasses(edgeClass);
  const edgeLabel = edgeClass ? EDGE_CLASS_LABEL[edgeClass] : "—";

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] uppercase tracking-wider font-mono ${chipCls}`}
        title={`P(T1) ${fmtPctOdds(probTarget1)} · P(stop) ${fmtPctOdds(probStop)} · ${edgeLabel}`}
      >
        <span className="tnum">{fmtR(expectedR)}</span>
      </span>
    );
  }

  return (
    <div className="border border-ink/15 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="display-heading text-base">Probabilidades (Monte Carlo)</h4>
        <span className={`px-2 py-0.5 text-[10px] uppercase tracking-wider font-mono ${chipCls}`}>
          {edgeLabel}
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
        <ProbCell label="P(Target 1)" value={fmtPctOdds(probTarget1)} accent="bull" />
        {probTarget2 != null && (
          <ProbCell label="P(Target 2)" value={fmtPctOdds(probTarget2)} accent="bull" />
        )}
        <ProbCell label="P(Stop)" value={fmtPctOdds(probStop)} accent="bear" />
        <ProbCell label="P(Expira)" value={fmtPctOdds(probExpire)} />
      </div>

      <div className="flex items-baseline justify-between pt-3 border-t border-ink/10">
        <span className="text-[11px] uppercase tracking-widest font-mono text-ink-muted">
          Esperanza
        </span>
        <span
          className={`font-mono tnum font-bold text-lg ${
            (expectedR ?? 0) > 0 ? "text-bull" : (expectedR ?? 0) < 0 ? "text-bear-bright" : "text-ink"
          }`}
        >
          {fmtR(expectedR)}
        </span>
      </div>

      <p className="text-[11px] text-ink-muted mt-3 leading-relaxed">
        Monte Carlo 10.000 paths, GBM con volatilidad histórica. NO predice eventos binarios
        (resultados, FDA, M&amp;A). Es información, no garantía.
      </p>
    </div>
  );
}

function ProbCell({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "bull" | "bear";
}) {
  const cls =
    accent === "bull" ? "text-bull" : accent === "bear" ? "text-bear-bright" : "text-ink";
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-0.5">
        {label}
      </div>
      <div className={`font-mono tnum font-bold text-xl ${cls}`}>{value}</div>
    </div>
  );
}
