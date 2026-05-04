"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  closeTrade,
  deleteTrade,
  getTrades,
  getTradeStats,
  refreshTradePrices,
} from "@/lib/api";
import type { TradeOut, TradeStatsOut, TradeStatus } from "@/lib/types";
import { fmtNum, fmtPct, fmtDate, changeColor } from "@/lib/format";

type Tab = "open" | "closed" | "stats";

export default function JournalPage() {
  const [tab, setTab] = useState<Tab>("open");
  const [trades, setTrades] = useState<TradeOut[]>([]);
  const [stats, setStats] = useState<TradeStatsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshAt, setLastRefreshAt] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [list, s] = await Promise.all([getTrades("all"), getTradeStats()]);
      setTrades(list);
      setStats(s);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshPrices() {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const res = await refreshTradePrices();
      // Merge: replace open trades by id, leave closed ones untouched.
      setTrades((prev) => {
        const liveById = new Map(res.trades.map((t) => [t.id, t]));
        return prev.map((t) =>
          t.status === "open" && liveById.has(t.id) ? liveById.get(t.id)! : t
        );
      });
      setLastRefreshAt(res.fetched_at);
    } catch (e: any) {
      setRefreshError(e.message);
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const open = useMemo(() => trades.filter((t) => t.status === "open"), [trades]);
  const closed = useMemo(() => trades.filter((t) => t.status !== "open"), [trades]);

  const lastRefreshLabel = useMemo(() => {
    if (!lastRefreshAt) return null;
    try {
      const d = new Date(lastRefreshAt);
      return d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch {
      return null;
    }
  }, [lastRefreshAt]);

  return (
    <div>
      <div className="mb-8">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-ink-muted mb-2">
          Diario
        </div>
        <h1 className="display-heading text-5xl tracking-tightest">
          Diario de <span className="italic text-bull">operaciones</span>
        </h1>
        <p className="text-ink-light mt-2 max-w-3xl">
          Sin esto no sabés si el sistema te da edge. Anotá cada operación que
          abrís desde el ranking, cerrala cuando salgas, y mirá las estadísticas
          para ver qué setups funcionan en la práctica.
        </p>
      </div>

      {open.length > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2">
          <button
            onClick={handleRefreshPrices}
            disabled={refreshing}
            className="border border-ink/30 px-4 py-2 text-xs uppercase tracking-widest font-mono hover:bg-ink hover:text-paper transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {refreshing ? "Actualizando…" : "Actualizar precios"}
          </button>
          <span className="text-[11px] uppercase tracking-widest font-mono text-ink-muted">
            {lastRefreshLabel
              ? `Última actualización: ${lastRefreshLabel}`
              : "Sin actualizar"}
          </span>
          {refreshError && (
            <span className="text-[11px] font-mono text-bear-bright">
              Error: {refreshError}
            </span>
          )}
        </div>
      )}

      <div className="border-b border-ink/15 mb-6 flex gap-6 text-sm">
        <TabButton active={tab === "open"} onClick={() => setTab("open")}>
          Abiertas <span className="text-ink-muted font-mono">({open.length})</span>
        </TabButton>
        <TabButton active={tab === "closed"} onClick={() => setTab("closed")}>
          Cerradas <span className="text-ink-muted font-mono">({closed.length})</span>
        </TabButton>
        <TabButton active={tab === "stats"} onClick={() => setTab("stats")}>
          Estadísticas
        </TabButton>
      </div>

      {error && (
        <div className="border border-bear/40 bg-bear/5 p-4 mb-6 text-sm">
          <strong className="text-bear">Error:</strong>{" "}
          <span className="text-ink-light">{error}</span>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-ink-muted">Cargando…</div>
      ) : tab === "open" ? (
        <OpenTrades trades={open} onChanged={refresh} />
      ) : tab === "closed" ? (
        <ClosedTrades trades={closed} onChanged={refresh} />
      ) : (
        <StatsTab stats={stats} />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`pb-3 -mb-px border-b-2 transition-colors ${
        active
          ? "border-bull text-bull font-medium"
          : "border-transparent text-ink/70 hover:text-bull"
      }`}
    >
      {children}
    </button>
  );
}

// -------------------------------------------------------------- Open trades

function OpenTrades({
  trades,
  onChanged,
}: {
  trades: TradeOut[];
  onChanged: () => void;
}) {
  if (trades.length === 0) {
    return (
      <div className="border border-ink/15 p-12 text-center">
        <p className="display-heading text-2xl mb-2">Sin operaciones abiertas</p>
        <p className="text-ink-light">
          Abrí una desde la página de un ticker con el botón "Operar esta idea".
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {trades.map((t) => (
        <OpenRow key={t.id} trade={t} onChanged={onChanged} />
      ))}
    </div>
  );
}

function OpenRow({
  trade,
  onChanged,
}: {
  trade: TradeOut;
  onChanged: () => void;
}) {
  const [closing, setClosing] = useState(false);
  const pnlPctText =
    trade.pnl_pct_live != null
      ? `${trade.pnl_pct_live >= 0 ? "+" : ""}${fmtPct(trade.pnl_pct_live)}`
      : "—";
  const pnlEurText =
    trade.pnl_eur_live != null
      ? `${trade.pnl_eur_live >= 0 ? "+" : ""}${fmtNum(trade.pnl_eur_live, 2)}€`
      : "—";
  const valorActual = trade.capital_eur + (trade.pnl_eur_live ?? 0);

  return (
    <div className="border border-ink/15 p-6 bg-paper">
      {/* Header: company name + ticker on left, big gain on right */}
      <div className="flex justify-between items-start gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="display-heading text-3xl tracking-tightest leading-tight truncate">
            {trade.name || trade.ticker}
          </h3>
          <div className="mt-1 flex items-center gap-3">
            <Link
              href={`/ticker/${encodeURIComponent(trade.ticker)}`}
              className="text-xs font-mono text-ink-muted hover:text-bull tracking-wider"
            >
              {trade.ticker}
            </Link>
            <ProfileBadge profile={trade.profile} />
          </div>
        </div>

        <div className="text-right shrink-0">
          <div
            className={`display-heading text-4xl tracking-tightest leading-none ${changeColor(
              trade.pnl_pct_live
            )}`}
          >
            {pnlPctText}
          </div>
          <div
            className={`font-mono tnum text-lg mt-1 ${changeColor(
              trade.pnl_eur_live
            )}`}
          >
            {pnlEurText}
          </div>
        </div>
      </div>

      {/* Money summary: Invertido vs Valor actual */}
      <div className="border-t border-ink/10 pt-4 mt-5 grid grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1">
            Invertido
          </div>
          <div className="font-mono tnum text-2xl text-ink">
            {fmtNum(trade.capital_eur, 0)}€
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1">
            Valor actual
          </div>
          <div
            className={`font-mono tnum text-2xl ${changeColor(
              trade.pnl_eur_live
            )}`}
          >
            {fmtNum(valorActual, 0)}€
          </div>
        </div>
      </div>

      {/* Price details: Compraste a / Precio hoy / Días abierta */}
      <div className="border-t border-ink/10 pt-4 mt-4 grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1">
            Compraste a
          </div>
          <div className="font-mono tnum text-ink">
            {fmtNum(trade.entry_price)}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1">
            Precio hoy
          </div>
          <div className="font-mono tnum text-ink">
            {trade.current_price != null ? fmtNum(trade.current_price) : "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1">
            Días abierta
          </div>
          <div className="font-mono tnum text-ink">
            {trade.days_held ?? "—"}
          </div>
        </div>
      </div>

      {/* Limits row: stop + target in plain Spanish */}
      {(trade.stop_price != null || trade.target_1 != null) && (
        <div className="border-t border-ink/10 pt-4 mt-4 flex flex-col sm:flex-row sm:gap-8 gap-2 text-sm text-ink-muted">
          {trade.stop_price != null && (
            <div>
              Si baja a{" "}
              <span className="font-mono tnum text-ink">
                {fmtNum(trade.stop_price)}
              </span>{" "}
              → vendés (stop)
            </div>
          )}
          {trade.target_1 != null && (
            <div>
              Objetivo:{" "}
              <span className="font-mono tnum text-ink">
                {fmtNum(trade.target_1)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Action: Cerrar operación */}
      <div className="mt-5 flex justify-end">
        <button
          onClick={() => setClosing((v) => !v)}
          className="text-xs uppercase tracking-widest font-mono border border-ink/30 px-3 py-1.5 hover:bg-ink hover:text-paper transition-colors"
        >
          {closing ? "Cancelar" : "Cerrar operación"}
        </button>
      </div>

      {closing && (
        <div className="border-t border-ink/10 mt-4 pt-4">
          <CloseForm
            trade={trade}
            onDone={() => {
              setClosing(false);
              onChanged();
            }}
            onCancel={() => setClosing(false)}
          />
        </div>
      )}
    </div>
  );
}

function CloseForm({
  trade,
  onDone,
  onCancel,
}: {
  trade: TradeOut;
  onDone: () => void;
  onCancel: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [exitPrice, setExitPrice] = useState<string>(
    trade.current_price != null ? trade.current_price.toFixed(2) : ""
  );
  const [exitDate, setExitDate] = useState<string>(today);
  const [notes, setNotes] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const parsed = parseFloat(exitPrice);
    if (!parsed || parsed <= 0) {
      setErr("Exit price inválido");
      return;
    }
    setSubmitting(true);
    try {
      await closeTrade(trade.id, {
        exit_price: parsed,
        exit_date: exitDate,
        notes: notes || undefined,
      });
      onDone();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`¿Borrar la operación de ${trade.ticker}? Esta acción no se puede deshacer.`)) return;
    setSubmitting(true);
    try {
      await deleteTrade(trade.id);
      onDone();
    } catch (e: any) {
      setErr(e.message);
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid md:grid-cols-[1fr_1fr_2fr_auto] gap-3 items-end">
      <Field label="Exit price">
        <input
          type="number"
          step="0.01"
          value={exitPrice}
          onChange={(e) => setExitPrice(e.target.value)}
          className="w-full border border-ink/20 px-2 py-1.5 font-mono text-sm bg-paper"
          required
        />
      </Field>
      <Field label="Exit date">
        <input
          type="date"
          value={exitDate}
          onChange={(e) => setExitDate(e.target.value)}
          className="w-full border border-ink/20 px-2 py-1.5 font-mono text-sm bg-paper"
        />
      </Field>
      <Field label="Notas (opcional)">
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full border border-ink/20 px-2 py-1.5 text-sm bg-paper"
          placeholder="Ej: salí en target 1, mercado débil…"
        />
      </Field>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="bg-ink text-paper px-4 py-2 text-xs uppercase tracking-widest font-mono hover:bg-bull transition-colors disabled:opacity-50"
        >
          {submitting ? "…" : "Confirmar cierre"}
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={submitting}
          className="border border-bear/50 text-bear px-3 py-2 text-xs uppercase tracking-widest font-mono hover:bg-bear hover:text-paper transition-colors disabled:opacity-50"
          title="Borrar operación"
        >
          Borrar
        </button>
      </div>
      {err && <div className="md:col-span-4 text-xs text-bear-bright">{err}</div>}
    </form>
  );
}

// -------------------------------------------------------------- Closed trades

function ClosedTrades({
  trades,
  onChanged,
}: {
  trades: TradeOut[];
  onChanged: () => void;
}) {
  if (trades.length === 0) {
    return (
      <div className="border border-ink/15 p-12 text-center">
        <p className="display-heading text-2xl mb-2">Sin operaciones cerradas</p>
        <p className="text-ink-light">Cuando cierres alguna, aparecerá acá.</p>
      </div>
    );
  }

  return (
    <div className="border border-ink/15 overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-paper-deep">
          <tr className="text-[10px] uppercase tracking-widest font-mono text-ink-muted">
            <Th>Ticker</Th>
            <Th>Setup</Th>
            <Th>Perfil</Th>
            <Th>Status</Th>
            <Th align="right">Entry</Th>
            <Th align="right">Exit</Th>
            <Th align="right">P&L %</Th>
            <Th align="right">P&L €</Th>
            <Th align="right">Días</Th>
            <Th>Fechas</Th>
            <Th></Th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <ClosedRow key={t.id} trade={t} onChanged={onChanged} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClosedRow({
  trade,
  onChanged,
}: {
  trade: TradeOut;
  onChanged: () => void;
}) {
  const days =
    trade.exit_date && trade.entry_date
      ? Math.max(
          0,
          Math.round(
            (new Date(trade.exit_date).getTime() - new Date(trade.entry_date).getTime()) /
              86400000
          )
        )
      : null;
  return (
    <tr className="border-t border-ink/10 hover:bg-paper-deep/50">
      <Td>
        <Link
          href={`/ticker/${encodeURIComponent(trade.ticker)}`}
          className="font-bold hover:text-bull"
        >
          {trade.ticker}
        </Link>
      </Td>
      <Td>
        <span className="text-xs uppercase tracking-wider font-mono">
          {trade.setup_type || "—"}
        </span>
      </Td>
      <Td>
        <ProfileBadge profile={trade.profile} />
      </Td>
      <Td>
        <StatusBadge status={trade.status} />
      </Td>
      <Td align="right" mono>{fmtNum(trade.entry_price)}</Td>
      <Td align="right" mono>{fmtNum(trade.exit_price)}</Td>
      <Td align="right" mono>
        <span className={changeColor(trade.pnl_pct)}>
          {trade.pnl_pct != null ? fmtPct(trade.pnl_pct) : "—"}
        </span>
      </Td>
      <Td align="right" mono>
        <span className={changeColor(trade.pnl_eur)}>
          {trade.pnl_eur != null ? `${trade.pnl_eur >= 0 ? "+" : ""}${fmtNum(trade.pnl_eur, 2)}€` : "—"}
        </span>
      </Td>
      <Td align="right" mono>{days ?? "—"}</Td>
      <Td>
        <div className="text-[11px] text-ink-muted font-mono">
          {fmtDate(trade.entry_date)} → {fmtDate(trade.exit_date)}
        </div>
      </Td>
      <Td align="right">
        <button
          onClick={async () => {
            if (!confirm(`¿Borrar la operación cerrada de ${trade.ticker}?`)) return;
            try {
              await deleteTrade(trade.id);
              onChanged();
            } catch (e: any) {
              alert(e.message);
            }
          }}
          className="text-[10px] uppercase tracking-widest font-mono text-ink-muted hover:text-bear-bright"
        >
          Borrar
        </button>
      </Td>
    </tr>
  );
}

// -------------------------------------------------------------- Stats

function StatsTab({ stats }: { stats: TradeStatsOut | null }) {
  if (!stats) return null;

  if (stats.total === 0) {
    return (
      <div className="border border-ink/15 p-12 text-center">
        <p className="display-heading text-2xl mb-2">Aún no hay datos</p>
        <p className="text-ink-light">
          Las estadísticas aparecerán cuando registres operaciones.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="grid md:grid-cols-3 lg:grid-cols-6 gap-3">
        <BigStat label="Total" value={stats.total.toString()} />
        <BigStat label="Abiertas" value={stats.open.toString()} />
        <BigStat label="Cerradas" value={stats.closed.toString()} />
        <BigStat
          label="Win rate"
          value={`${stats.win_rate_pct.toFixed(0)}%`}
          accent={stats.win_rate_pct >= 50 ? "bull" : "bear"}
        />
        <BigStat
          label="Retorno medio"
          value={fmtPct(stats.avg_return_pct)}
          accent={stats.avg_return_pct >= 0 ? "bull" : "bear"}
        />
        <BigStat label="Días medios" value={stats.avg_days_held.toFixed(1)} />
      </section>

      <section className="grid md:grid-cols-3 gap-4">
        <BigStat
          label="P&L total"
          value={`${stats.total_pnl_eur >= 0 ? "+" : ""}${fmtNum(stats.total_pnl_eur, 2)}€`}
          accent={stats.total_pnl_eur >= 0 ? "bull" : "bear"}
          big
        />
        <BigStat
          label={`Mejor trade${stats.best_trade_ticker ? ` · ${stats.best_trade_ticker}` : ""}`}
          value={stats.best_trade_pct != null ? fmtPct(stats.best_trade_pct) : "—"}
          accent="bull"
          big
        />
        <BigStat
          label={`Peor trade${stats.worst_trade_ticker ? ` · ${stats.worst_trade_ticker}` : ""}`}
          value={stats.worst_trade_pct != null ? fmtPct(stats.worst_trade_pct) : "—"}
          accent="bear"
          big
        />
      </section>

      <section className="grid md:grid-cols-2 gap-6">
        <BucketTable title="Por setup" buckets={stats.by_setup} />
        <BucketTable title="Por perfil" buckets={stats.by_profile} />
      </section>
    </div>
  );
}

function BigStat({
  label,
  value,
  accent,
  big,
}: {
  label: string;
  value: string;
  accent?: "bull" | "bear";
  big?: boolean;
}) {
  const accentCls =
    accent === "bull" ? "text-bull" : accent === "bear" ? "text-bear-bright" : "text-ink";
  return (
    <div className="border border-ink/15 p-4">
      <div className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">
        {label}
      </div>
      <div
        className={`display-heading tracking-tightest ${accentCls} ${
          big ? "text-4xl" : "text-3xl"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function BucketTable({
  title,
  buckets,
}: {
  title: string;
  buckets: Record<
    string,
    { n: number; n_closed: number; win_rate_pct: number; avg_return_pct: number; total_pnl_eur: number }
  >;
}) {
  const entries = Object.entries(buckets).sort((a, b) => b[1].n - a[1].n);
  if (entries.length === 0) {
    return (
      <div className="border border-ink/15 p-4">
        <h3 className="display-heading text-xl mb-2">{title}</h3>
        <p className="text-sm text-ink-muted">Sin datos.</p>
      </div>
    );
  }
  return (
    <div className="border border-ink/15">
      <h3 className="display-heading text-xl px-4 pt-4 pb-2">{title}</h3>
      <table className="w-full text-sm">
        <thead className="bg-paper-deep">
          <tr className="text-[10px] uppercase tracking-widest font-mono text-ink-muted">
            <Th>Categoría</Th>
            <Th align="right">N</Th>
            <Th align="right">Win %</Th>
            <Th align="right">Retorno medio</Th>
            <Th align="right">P&L €</Th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([k, b]) => (
            <tr key={k} className="border-t border-ink/10">
              <Td>
                <span className="capitalize">{k.replace("_", " ")}</span>
              </Td>
              <Td align="right" mono>
                {b.n_closed}/{b.n}
              </Td>
              <Td align="right" mono>{b.win_rate_pct.toFixed(0)}%</Td>
              <Td align="right" mono>
                <span className={changeColor(b.avg_return_pct)}>
                  {fmtPct(b.avg_return_pct)}
                </span>
              </Td>
              <Td align="right" mono>
                <span className={changeColor(b.total_pnl_eur)}>
                  {b.total_pnl_eur >= 0 ? "+" : ""}{fmtNum(b.total_pnl_eur, 0)}€
                </span>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// -------------------------------------------------------------- Shared cells

function Th({
  children,
  align,
}: {
  children?: React.ReactNode;
  align?: "right" | "left";
}) {
  return (
    <th className={`px-3 py-2 ${align === "right" ? "text-right" : "text-left"} font-normal`}>
      {children}
    </th>
  );
}

function Td({
  children,
  align,
  mono,
}: {
  children?: React.ReactNode;
  align?: "right" | "left";
  mono?: boolean;
}) {
  return (
    <td
      className={`px-3 py-2 ${align === "right" ? "text-right" : "text-left"} ${
        mono ? "font-mono tnum" : ""
      }`}
    >
      {children}
    </td>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

function ProfileBadge({ profile }: { profile: string }) {
  const isAggr = profile === "aggressive";
  return (
    <span
      className={`text-[10px] uppercase tracking-widest font-mono px-2 py-0.5 border ${
        isAggr ? "border-bear/50 text-bear" : "border-bull/50 text-bull"
      }`}
    >
      {isAggr ? "Agresivo" : "Conservador"}
    </span>
  );
}

function StatusBadge({ status }: { status: TradeStatus }) {
  const label = (
    {
      open: "Abierta",
      closed_win: "Ganada",
      closed_loss: "Perdida",
      stopped: "Stop",
    } as Record<TradeStatus, string>
  )[status];
  const cls =
    status === "closed_win"
      ? "border-bull/50 text-bull"
      : status === "open"
      ? "border-ink/30 text-ink"
      : "border-bear/50 text-bear-bright";
  return (
    <span
      className={`text-[10px] uppercase tracking-widest font-mono px-2 py-0.5 border ${cls}`}
    >
      {label}
    </span>
  );
}
