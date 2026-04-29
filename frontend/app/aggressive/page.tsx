import Link from "next/link";
import { RankingTable } from "@/components/RankingTable";
import type { ScoreOut } from "@/lib/types";

export const dynamic = "force-dynamic";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAggressive(): Promise<ScoreOut[]> {
  const res = await fetch(`${API_URL}/api/ranking/aggressive?limit=15`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API -> ${res.status}`);
  return res.json();
}

export default async function AggressivePage() {
  let rows: ScoreOut[] = [];
  let error: string | null = null;
  try {
    rows = await getAggressive();
  } catch (e: any) {
    error = e.message;
  }

  return (
    <div>
      <div className="mb-8">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-2">
          Agresivo
        </div>
        <h1 className="display-heading text-5xl tracking-tightest">
          Catalizadores <span className="italic text-bear">en marcha</span>
        </h1>
        <p className="text-ink-light mt-2 max-w-3xl">
          Detección de breakouts con volumen, catalizadores positivos en fase de
          digestión (3-10 días, no titulares de hoy), rebotes de sobreventa en
          empresas sanas y rezagados con momentum sectorial. Mayor potencial,
          menor probabilidad: opera con tamaño reducido.
        </p>
      </div>

      <div className="border border-amber/40 bg-amber/5 p-4 mb-6 text-sm">
        <strong className="display-heading text-base">Perfil esperado:</strong>
        <ul className="mt-2 space-y-1 text-ink-light">
          <li>• Objetivo: <strong>+10% a +25%</strong> en 2-4 semanas</li>
          <li>• Win rate esperado: <strong>~45%</strong> (más fallos, mayores aciertos)</li>
          <li>• Stops más amplios: 5-7% bajo entrada</li>
          <li>• Riesgo por operación recomendado: <strong>1% del capital</strong> (20€ con 2.000€)</li>
        </ul>
      </div>

      <div className="border border-ink/30 bg-paper-deep/30 p-4 mb-6 text-xs">
        <strong className="display-heading text-sm">Filosofía del scoring agresivo:</strong>
        <p className="mt-2 text-ink-light leading-relaxed">
          La app NO recomienda comprar reaccionando a la noticia que acabas de leer.
          Cuando un retail lee un titular de catalizador, el movimiento ya está
          mayormente ejecutado por institucionales y algoritmos. Lo que aquí se
          busca son catalizadores con <strong>3-10 días de antigüedad</strong> donde
          el mercado los está digiriendo y aún hay recorrido. También breakouts
          técnicos con volumen y patrones de acumulación. Es realista, no fantasía.
        </p>
      </div>

      {error && (
        <div className="border border-bear/40 bg-bear/5 p-4 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}

      {!error && rows.length === 0 && (
        <div className="border border-ink/15 p-12 text-center">
          <p className="display-heading text-3xl mb-3">No hay catalizadores activos hoy</p>
          <p className="text-ink-light max-w-xl mx-auto">
            La paciencia es la mayor ventaja del retail disciplinado. No fuerces
            operaciones sin setup. Vuelve mañana.
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