"use client";

import { useEffect, useState } from "react";
import { getWeights, getJobRuns, triggerDailyJob } from "@/lib/api";
import type { WeightsOut, JobRunOut } from "@/lib/types";
import { fmtRelativeTime } from "@/lib/format";

export default function SettingsPage() {
  const [weights, setWeights] = useState<WeightsOut | null>(null);
  const [runs, setRuns] = useState<JobRunOut[]>([]);
  const [running, setRunning] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      const [w, r] = await Promise.all([getWeights(), getJobRuns()]);
      setWeights(w);
      setRuns(r);
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function trigger() {
    setRunning(true);
    setMsg(null);
    try {
      await triggerDailyJob();
      setMsg("✓ Job lanzado. Refresca en unos minutos para ver resultados.");
      setTimeout(refresh, 2000);
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <div className="mb-8">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-2">Ajustes</div>
        <h1 className="display-heading text-5xl tracking-tightest">Sistema</h1>
        <p className="text-ink-light mt-2 max-w-2xl">
          Pesos del scoring, ejecuciones del job y datos del entorno. Para cambiar pesos en
          producción, edita las variables de entorno y reinicia el servicio.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="border border-ink/15 p-5">
          <h3 className="display-heading text-2xl mb-4">Pesos del scoring</h3>
          {weights ? (
            <div className="space-y-3 font-mono text-sm">
              <WeightRow label="Técnico" value={weights.technical} />
              <WeightRow label="Noticias" value={weights.news} />
              <WeightRow label="Fundamental" value={weights.fundamental} />
              <WeightRow label="Macro" value={weights.macro} />
              <WeightRow label="Liquidez" value={weights.liquidity} />
              <div className="border-t border-ink/10 pt-3 flex justify-between font-bold">
                <span>Total</span>
                <span className="tnum">
                  {(weights.technical + weights.news + weights.fundamental + weights.macro + weights.liquidity).toFixed(2)}
                </span>
              </div>
            </div>
          ) : (
            <div className="text-sm text-ink-muted">Cargando…</div>
          )}
          <p className="text-[11px] text-ink-muted mt-4 leading-relaxed">
            Configurable vía variables de entorno: <code className="bg-paper-deep px-1">WEIGHT_TECHNICAL</code>,{" "}
            <code className="bg-paper-deep px-1">WEIGHT_NEWS</code>, etc.
          </p>
        </div>

        <div className="border border-ink/15 p-5">
          <h3 className="display-heading text-2xl mb-2">Job diario</h3>
          <p className="text-sm text-ink-muted mb-4">
            Ejecuta el pipeline completo: ingesta de precios, fundamentales, noticias, scoring y
            generación de explicaciones.
          </p>
          <button
            onClick={trigger}
            disabled={running}
            className="bg-ink text-paper px-6 py-3 text-sm uppercase tracking-widest font-mono hover:bg-bear transition-colors disabled:opacity-50 w-full"
          >
            {running ? "Lanzando…" : "Ejecutar job ahora"}
          </button>
          {msg && <div className="mt-3 text-sm">{msg}</div>}

          <div className="mt-6 pt-6 border-t border-ink/10">
            <h4 className="display-heading text-lg mb-2">Últimas ejecuciones</h4>
            {runs.length === 0 ? (
              <div className="text-sm text-ink-muted">Sin ejecuciones registradas.</div>
            ) : (
              <div className="space-y-2 text-xs font-mono">
                {runs.slice(0, 8).map((r) => (
                  <div key={r.id} className="flex justify-between border-b border-ink/5 pb-1">
                    <span className="text-ink-muted">{fmtRelativeTime(r.started_at)}</span>
                    <span className={r.status === "ok" ? "text-bull" : r.status === "error" ? "text-bear-bright" : "text-amber"}>
                      {r.status}
                    </span>
                    <span className="tnum">{r.scores_generated}/{r.instruments_processed}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function WeightRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-xs uppercase tracking-wider text-ink-muted">{label}</span>
        <span className="tnum">{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1.5 bg-ink/10">
        <div className="h-full bg-bear" style={{ width: `${value * 100 * 2.5}%`, maxWidth: "100%" }} />
      </div>
    </div>
  );
}
