import Link from "next/link";
import { getRanking, getStats, getMacro } from "@/lib/api";
import { RankingTable } from "@/components/RankingTable";
import { fmtRelativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let ranking: any[] = [];
  let stats: any = null;
  let macro: any[] = [];
  let apiError: string | null = null;

  try {
    [ranking, stats, macro] = await Promise.all([
      getRanking({ limit: 20, min_score: 50 }),
      getStats(),
      getMacro(6),
    ]);
  } catch (e: any) {
    apiError = e.message;
  }

  return (
    <div>
      {/* Hero */}
      <section className="mb-10 border-b border-ink/15 pb-10">
        <div className="grid lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-8">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-3">
              Edición del {new Date().toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
            </div>
            <h1 className="display-heading text-5xl md:text-7xl leading-[0.95] tracking-tightest mb-4">
              Hoy hay <span className="text-bear italic">{stats?.total_scores_today ?? 0}</span> ideas
              <br />en el radar.
            </h1>
            <p className="text-lg text-ink-light max-w-2xl">
              Ranking diario de candidatos a operar en corto, ordenados por score combinado de
              técnico, noticias, fundamentales, macro y riesgo de squeeze.
            </p>
          </div>

          <div className="lg:col-span-4 grid grid-cols-2 gap-3 text-sm">
            <Stat label="Universo" value={stats?.total_instruments ?? "—"} />
            <Stat label="Score medio" value={stats?.avg_score?.toFixed(1) ?? "—"} />
            <Stat label="Último update" value={stats?.last_job_run ? fmtRelativeTime(stats.last_job_run.started_at) : "nunca"} />
            <Stat
              label="Estado"
              value={stats?.last_job_run?.status ?? "—"}
              accent={stats?.last_job_run?.status === "ok" ? "bull" : stats?.last_job_run?.status === "error" ? "bear" : undefined}
            />
          </div>
        </div>
      </section>

      {apiError && (
        <div className="border border-bear/40 bg-bear/5 p-4 mb-8 text-sm">
          <strong className="text-bear">No se pudo conectar al backend.</strong>{" "}
          <span className="text-ink-light">¿Está arrancado?</span>{" "}
          <code className="font-mono text-xs">{apiError}</code>
          <div className="text-xs text-ink-muted mt-2">
            Si es la primera vez, ejecuta el job para poblar el ranking:{" "}
            <code className="bg-paper-deep px-2 py-1">POST /api/jobs/run-daily</code>
          </div>
        </div>
      )}

      {/* Top setups */}
      <section className="mb-10">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="display-heading text-3xl">Top 20</h2>
          <Link href="/ranking" className="text-sm border-b border-bear text-bear hover:text-ink hover:border-ink transition-colors">
            Ver ranking completo →
          </Link>
        </div>
        <RankingTable rows={ranking} />
      </section>

      {/* Setup distribution */}
      {stats?.top_setup_distribution && Object.keys(stats.top_setup_distribution).length > 0 && (
        <section className="mb-10 grid md:grid-cols-2 gap-8">
          <div>
            <h2 className="display-heading text-2xl mb-3">Distribución de setups (hoy)</h2>
            <div className="border border-ink/15 p-4 space-y-2">
              {Object.entries(stats.top_setup_distribution as Record<string, number>).map(([k, v]) => (
                <div key={k} className="flex justify-between font-mono text-sm">
                  <span className="capitalize">{k.replace("_", " ")}</span>
                  <span className="tnum">{v}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="display-heading text-2xl mb-3">Macro reciente</h2>
            {macro.length === 0 ? (
              <div className="border border-ink/15 p-4 text-sm text-ink-muted">Sin eventos macro relevantes.</div>
            ) : (
              <div className="border border-ink/15">
                {macro.slice(0, 5).map((ev, i) => (
                  <div key={i} className="border-b border-ink/10 last:border-0 p-3">
                    <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1 flex justify-between">
                      <span>{ev.category}</span>
                      <span>{new Date(ev.date).toLocaleDateString("es-ES", { day: "2-digit", month: "short" })}</span>
                    </div>
                    <div className="text-sm leading-snug">{ev.title}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: "bear" | "bull" }) {
  const accentCls = accent === "bear" ? "text-bear" : accent === "bull" ? "text-bull" : "text-ink";
  return (
    <div className="border border-ink/15 p-3">
      <div className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">{label}</div>
      <div className={`display-heading text-2xl ${accentCls}`}>{value}</div>
    </div>
  );
}
