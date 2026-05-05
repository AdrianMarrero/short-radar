import Link from "next/link";
import type { ScoreOut } from "@/lib/types";
import { fmtMoney, fmtPct, scoreColor, changeColor } from "@/lib/format";
import { SetupBadge, ConvictionBadge, TierBadge, WarningChips } from "./Badges";

export function RankingTable({ rows }: { rows: ScoreOut[] }) {
  if (!rows.length) {
    return (
      <div className="border border-ink/15 p-12 text-center">
        <p className="display-heading text-2xl mb-3">Sin resultados</p>
        <p className="text-sm text-ink-muted">
          Ejecuta el job diario para poblar el ranking, o relaja los filtros.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-ink/15 overflow-x-auto compact-table">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink/15 text-[11px] uppercase tracking-widest text-ink-muted">
            <th className="text-left px-3 py-3 font-medium">Tier</th>
            <th className="text-left px-4 py-3 font-medium">#</th>
            <th className="text-left px-4 py-3 font-medium">Ticker</th>
            <th className="text-left px-4 py-3 font-medium">Nombre</th>
            <th className="text-right px-4 py-3 font-medium">Último</th>
            <th className="text-right px-4 py-3 font-medium">1d</th>
            <th className="text-right px-4 py-3 font-medium">1m</th>
            <th className="text-right px-4 py-3 font-medium">Score</th>
            <th className="text-left px-4 py-3 font-medium">Setup</th>
            <th className="text-left px-4 py-3 font-medium">Convicción</th>
            <th className="text-right px-4 py-3 font-medium">Squeeze</th>
            <th className="text-right px-4 py-3 font-medium">Plan</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.instrument_id}
              className="border-b border-ink/5 hover:bg-paper-deep/40 transition-colors"
            >
              <td className="px-3 py-3"><TierBadge tier={r.tier} /></td>
              <td className="px-4 py-3 text-ink-muted font-mono tnum">{i + 1}</td>
              <td className="px-4 py-3">
                <Link
                  href={`/ticker/${encodeURIComponent(r.ticker)}`}
                  className="font-mono font-bold text-base hover:text-bear transition-colors"
                >
                  {r.ticker}
                </Link>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-mono">
                  {r.exchange}
                </div>
                <WarningChips warnings={r.warnings} />
              </td>
              <td className="px-4 py-3 max-w-[260px]">
                <div className="truncate">{r.name}</div>
                <div className="text-[11px] text-ink-muted truncate">{r.sector}</div>
              </td>
              <td className="px-4 py-3 text-right font-mono tnum">{fmtMoney(r.last_close)}</td>
              <td className={`px-4 py-3 text-right font-mono tnum ${changeColor(r.change_1d)}`}>
                {fmtPct(r.change_1d)}
              </td>
              <td className={`px-4 py-3 text-right font-mono tnum ${changeColor(r.change_1m)}`}>
                {fmtPct(r.change_1m)}
              </td>
              <td className={`px-4 py-3 text-right font-mono font-bold tnum text-base ${scoreColor(r.total_score)}`}>
                {r.total_score.toFixed(0)}
              </td>
              <td className="px-4 py-3"><SetupBadge setup={r.setup_type} /></td>
              <td className="px-4 py-3"><ConvictionBadge conviction={r.conviction} /></td>
              <td className="px-4 py-3 text-right font-mono tnum text-ink-muted">
                {r.squeeze_risk_score.toFixed(0)}
              </td>
              <td className="px-4 py-3 text-right font-mono text-xs tnum text-ink-muted">
                {r.entry_price && r.stop_price && r.target_2 ? (
                  <span>
                    E {r.entry_price.toFixed(2)} / S {r.stop_price.toFixed(2)} / T {r.target_2.toFixed(2)}
                  </span>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
