"use client";

import { useEffect, useState } from "react";
import { getRanking, type RankingFilters } from "@/lib/api";
import { RankingTable } from "@/components/RankingTable";
import { RankingFiltersBar } from "@/components/RankingFiltersBar";
import type { ScoreOut } from "@/lib/types";

export default function RankingPage() {
  const [filters, setFilters] = useState<RankingFilters>({ limit: 100 });
  const [rows, setRows] = useState<ScoreOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getRanking(filters)
      .then((r) => { if (!cancelled) setRows(r); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [filters]);

  return (
    <div>
      <div className="mb-8">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-2">Ranking</div>
        <h1 className="display-heading text-5xl tracking-tightest">
          Candidatos <span className="italic text-bear">cortos</span>
        </h1>
        <p className="text-ink-light mt-2 max-w-2xl">
          Filtra por mercado, sector, setup y horizonte. El score va de 0 a 100 — superior a 65 indica
          confluencia fuerte de señales bajistas. Recuerda revisar el riesgo de squeeze.
        </p>
      </div>

      <RankingFiltersBar initial={filters} onChange={setFilters} />

      {loading && (
        <div className="border border-ink/15 p-12 text-center text-ink-muted">
          <div className="font-mono text-xs uppercase tracking-widest animate-pulse">Cargando…</div>
        </div>
      )}

      {error && (
        <div className="border border-bear/40 bg-bear/5 p-4 text-sm">
          <strong className="text-bear">Error:</strong> {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="text-xs text-ink-muted font-mono mb-2">
            {rows.length} resultado{rows.length === 1 ? "" : "s"}
          </div>
          <RankingTable rows={rows} />
        </>
      )}
    </div>
  );
}
