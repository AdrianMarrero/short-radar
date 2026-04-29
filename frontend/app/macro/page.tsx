import { getMacro } from "@/lib/api";
import { fmtRelativeTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function MacroPage() {
  let events: any[] = [];
  let error: string | null = null;
  try {
    events = await getMacro(50);
  } catch (e: any) {
    error = e.message;
  }

  return (
    <div>
      <div className="mb-8">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-2">Macro</div>
        <h1 className="display-heading text-5xl tracking-tightest">
          Vientos de cola <span className="italic text-bear">y de cara</span>
        </h1>
        <p className="text-ink-light mt-2 max-w-2xl">
          Eventos macro y geopolíticos recientes que afectan a sectores enteros del mercado. La app
          consulta RSS de Reuters, FT, BBC y otros para detectar señales con impacto sectorial.
        </p>
      </div>

      {error && (
        <div className="border border-bear/40 bg-bear/5 p-4 text-sm">
          <strong className="text-bear">Error:</strong> {error}
        </div>
      )}

      {events.length === 0 && !error && (
        <div className="border border-ink/15 p-12 text-center">
          <p className="display-heading text-2xl mb-2">Sin eventos relevantes hoy</p>
          <p className="text-sm text-ink-muted">Los eventos se actualizan al ejecutar el job diario.</p>
        </div>
      )}

      <div className="space-y-4">
        {events.map((ev, i) => (
          <article key={i} className="border border-ink/15 p-5 grid md:grid-cols-[120px_1fr_120px] gap-4 hover:bg-paper-deep/30 transition-colors">
            <div className="font-mono text-xs uppercase tracking-widest text-ink-muted">
              <div>{new Date(ev.date).toLocaleDateString("es-ES", { day: "2-digit", month: "short" })}</div>
              <div className="text-[10px] mt-1">{ev.region}</div>
              <div className="text-[10px] mt-1 text-bear">{ev.category}</div>
            </div>
            <div>
              <h3 className="text-base leading-snug">{ev.title}</h3>
              {ev.summary && <p className="text-sm text-ink-muted mt-2 line-clamp-3">{ev.summary}</p>}
              {ev.affected_sectors && (
                <div className="mt-2 flex gap-2 flex-wrap">
                  {ev.affected_sectors.split(",").filter((s: string) => s).map((s: string) => (
                    <span key={s} className="text-[10px] uppercase tracking-widest font-mono px-2 py-0.5 border border-ink/20">
                      {s.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">Impact</div>
              <div className="font-mono text-2xl tnum text-bear">
                {(ev.impact_score * 100).toFixed(0)}
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
