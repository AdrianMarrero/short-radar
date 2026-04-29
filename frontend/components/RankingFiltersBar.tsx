"use client";

import { useState } from "react";
import type { RankingFilters } from "@/lib/api";

const MARKETS = [
  { value: "", label: "Todos" },
  { value: "NASDAQ", label: "NASDAQ" },
  { value: "NYSE", label: "NYSE" },
  { value: "IBEX", label: "IBEX 35" },
  { value: "DAX", label: "DAX" },
  { value: "CAC", label: "CAC 40" },
  { value: "FTSE", label: "FTSE 100" },
];

const SETUPS = [
  { value: "", label: "Cualquiera" },
  { value: "deterioration", label: "Deterioro" },
  { value: "event", label: "Evento" },
  { value: "technical", label: "Técnico" },
  { value: "overextension", label: "Sobre-extensión" },
];

const HORIZONS = [
  { value: "", label: "Cualquiera" },
  { value: "intraday", label: "Intradía" },
  { value: "swing", label: "Swing" },
  { value: "positional", label: "Posicional" },
];

interface Props {
  initial: RankingFilters;
  onChange: (f: RankingFilters) => void;
}

export function RankingFiltersBar({ initial, onChange }: Props) {
  const [filters, setFilters] = useState<RankingFilters>(initial);

  function update(patch: Partial<RankingFilters>) {
    const next = { ...filters, ...patch };
    setFilters(next);
    onChange(next);
  }

  const inputCls =
    "bg-paper border border-ink/20 px-3 py-2 text-sm focus:outline-none focus:border-bear hover:border-ink/40 transition-colors";

  return (
    <div className="border border-ink/15 bg-paper-deep/30 p-4 mb-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">
            Mercado
          </label>
          <select
            className={inputCls}
            value={filters.market || ""}
            onChange={(e) => update({ market: e.target.value || undefined })}
          >
            {MARKETS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">
            Sector
          </label>
          <input
            className={inputCls}
            placeholder="ej. Healthcare"
            value={filters.sector || ""}
            onChange={(e) => update({ sector: e.target.value || undefined })}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">
            Setup
          </label>
          <select
            className={inputCls}
            value={filters.setup || ""}
            onChange={(e) => update({ setup: e.target.value || undefined })}
          >
            {SETUPS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">
            Horizonte
          </label>
          <select
            className={inputCls}
            value={filters.horizon || ""}
            onChange={(e) => update({ horizon: e.target.value || undefined })}
          >
            {HORIZONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">
            Score mín.
          </label>
          <input
            type="number"
            min={0}
            max={100}
            className={inputCls}
            value={filters.min_score ?? 0}
            onChange={(e) => update({ min_score: Number(e.target.value) })}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase tracking-widest text-ink-muted font-mono">
            Squeeze máx.
          </label>
          <input
            type="number"
            min={0}
            max={100}
            className={inputCls}
            value={filters.max_squeeze ?? 100}
            onChange={(e) => update({ max_squeeze: Number(e.target.value) })}
          />
        </div>
      </div>
    </div>
  );
}
