import Link from "next/link";
import { RankingTable } from "@/components/RankingTable";
import type { ScoreOut } from "@/lib/types";

export const dynamic = "force-dynamic";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getConservative(): Promise<ScoreOut[]> {
  const res = await fetch(`${API_URL}/api/ranking/conservative?limit=15`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API -> ${res.status}`);
  return res.json();
}

export default async function ConservativePage() {
  let rows: ScoreOut[] = [];
  let error: string | null = null;
  try {
    rows = await getConservative();
  } catch (e: any) {
    error = e.message;
  }

  return (
    <div>
      <div className="mb-8">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-2">
          Conservador
        </div>
        <h1 className="display-heading text-5xl tracking-tightest">
          Tendencias <span className="italic text-bull">confirmadas</span>
        </h1>
        <p className="text-ink-light mt-2 max-w-3xl">
          Empresas en tendencia alcista clara, con fundamentales sanos, sin
          catalizadores negativos y volumen estable. Ideas para mantener 3-6 semanas
          buscando subidas moderadas pero con alta probabilidad de éxito.
        </p>
      </div>

      <div className="border border-bull/30 bg-bull/5 p-4 mb-6 text-sm">
        <strong className="display-heading text-base">Perfil esperado:</strong>
        <ul className="mt-2 space-y-1 text-ink-light">
          <li>• Objetivo: <strong>+5% a +12%</strong> en 3-6 semanas</li>
          <li>• Win rate esperado: <strong>~60%</strong></li>
          <li>• Stops ajustados: 3-5% bajo entrada</li>
          <li>• Riesgo por operación recomendado: <strong>1.5% del capital</strong> (30€ con 2.000€)</li>
        </ul>
      </div>

      {error && (
        <div className="border border-bear/40 bg-bear/5 p-4 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}

      {!error && rows.length === 0 && (
        <div className="border border-ink/15 p-12 text-center">
          <p className="display-heading text-3xl mb-3">Hoy no hay ideas conservadoras</p>
          <p className="text-ink-light max-w-xl mx-auto">
            Los filtros son estrictos por diseño. Que no haya ideas hoy es la
            herramienta protegiéndote. Mira la pestaña Agresivo si tienes mayor
            tolerancia al riesgo, o vuelve mañana.
          </p>
        </div>
      )}

      {rows.length > 0 && (
        <>
          <div className="text-xs text-ink-muted font-mono mb-2">
            {rows.length} idea{rows.length === 1 ? "" : "s"} pasa{rows.length === 1 ? "" : "n"} todos los filtros
          </div>
          <RankingTable rows={rows} />
        </>
      )}
    </div>
  );
}