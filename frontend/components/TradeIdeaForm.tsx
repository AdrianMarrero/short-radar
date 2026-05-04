"use client";

import { useState } from "react";
import Link from "next/link";
import { createTrade } from "@/lib/api";
import type { ScoreOut, TradeProfile } from "@/lib/types";

interface Props {
  instrumentId: number;
  ticker: string;
  score: ScoreOut | null;
  lastClose: number | null;
}

export function TradeIdeaForm({ instrumentId, ticker, score, lastClose }: Props) {
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full mt-4 bg-ink text-paper px-4 py-2.5 text-xs uppercase tracking-widest font-mono hover:bg-bull transition-colors"
      >
        Operar esta idea
      </button>
    );
  }

  return (
    <div className="mt-4 border border-bull/40 bg-bull/5 p-4">
      <div className="flex justify-between items-center mb-4">
        <h4 className="display-heading text-lg">Registrar operación</h4>
        <button
          onClick={() => setOpen(false)}
          className="text-xs uppercase tracking-widest font-mono text-ink-muted hover:text-ink"
        >
          Cerrar ✕
        </button>
      </div>
      <Form
        instrumentId={instrumentId}
        ticker={ticker}
        score={score}
        lastClose={lastClose}
        onClose={() => setOpen(false)}
      />
    </div>
  );
}

function Form({
  instrumentId,
  ticker,
  score,
  lastClose,
  onClose,
}: Props & { onClose: () => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const defaultEntry = score?.entry_price ?? lastClose ?? 0;

  const [capital, setCapital] = useState<string>("2000");
  const [entry, setEntry] = useState<string>(defaultEntry ? defaultEntry.toFixed(2) : "");
  const [entryDate, setEntryDate] = useState<string>(today);
  const [stop, setStop] = useState<string>(score?.stop_price != null ? score.stop_price.toFixed(2) : "");
  const [target1, setTarget1] = useState<string>(
    score?.target_1 != null ? score.target_1.toFixed(2) : ""
  );
  const [target2, setTarget2] = useState<string>(
    score?.target_2 != null ? score.target_2.toFixed(2) : ""
  );
  const [profile, setProfile] = useState<TradeProfile>("conservative");
  const [notes, setNotes] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);

  const numeric = (s: string): number | null => {
    const n = parseFloat(s);
    return Number.isFinite(n) && n > 0 ? n : null;
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);

    const capitalN = numeric(capital);
    const entryN = numeric(entry);
    if (!capitalN) {
      setErr("Capital inválido");
      return;
    }
    if (!entryN) {
      setErr("Entry price inválido");
      return;
    }

    setSubmitting(true);
    try {
      const trade = await createTrade({
        instrument_id: instrumentId,
        ticker,
        setup_type: score?.setup_type || "",
        profile,
        capital_eur: capitalN,
        entry_price: entryN,
        entry_date: entryDate,
        stop_price: numeric(stop),
        target_1: numeric(target1),
        target_2: numeric(target2),
        notes,
      });
      setSavedId(trade.id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (savedId !== null) {
    return (
      <div className="text-sm">
        <p className="mb-2">
          ✓ Operación <strong>#{savedId}</strong> registrada para {ticker}.
        </p>
        <div className="flex gap-3">
          <Link
            href="/journal"
            className="text-xs uppercase tracking-widest font-mono border-b border-bull text-bull hover:text-ink hover:border-ink"
          >
            Ver en el diario →
          </Link>
          <button
            onClick={onClose}
            className="text-xs uppercase tracking-widest font-mono text-ink-muted hover:text-ink"
          >
            Cerrar
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid md:grid-cols-3 gap-3">
        <Field label="Capital (€)">
          <input
            type="number"
            step="0.01"
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            className={inputCls}
            required
          />
        </Field>
        <Field label="Entry price">
          <input
            type="number"
            step="0.01"
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
            className={inputCls}
            required
          />
        </Field>
        <Field label="Entry date">
          <input
            type="date"
            value={entryDate}
            onChange={(e) => setEntryDate(e.target.value)}
            className={inputCls}
          />
        </Field>
      </div>

      <div className="grid md:grid-cols-3 gap-3">
        <Field label="Stop">
          <input
            type="number"
            step="0.01"
            value={stop}
            onChange={(e) => setStop(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Target 1">
          <input
            type="number"
            step="0.01"
            value={target1}
            onChange={(e) => setTarget1(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label="Target 2">
          <input
            type="number"
            step="0.01"
            value={target2}
            onChange={(e) => setTarget2(e.target.value)}
            className={inputCls}
          />
        </Field>
      </div>

      <Field label="Perfil">
        <div className="flex gap-2">
          <ProfileRadio
            value="conservative"
            current={profile}
            onChange={setProfile}
            label="Conservador"
          />
          <ProfileRadio
            value="aggressive"
            current={profile}
            onChange={setProfile}
            label="Agresivo"
          />
        </div>
      </Field>

      <Field label="Notas (opcional)">
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className={`${inputCls} font-sans`}
          placeholder="Ej: catalizador upgrade, entrada tras pullback al SMA20…"
        />
      </Field>

      {score && (
        <div className="text-[11px] text-ink-muted leading-relaxed">
          Setup capturado: <span className="font-mono">{score.setup_type}</span> ·
          Score actual <span className="font-mono">{score.total_score.toFixed(0)}</span>
        </div>
      )}

      {err && <div className="text-xs text-bear-bright">{err}</div>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="bg-ink text-paper px-5 py-2 text-xs uppercase tracking-widest font-mono hover:bg-bull transition-colors disabled:opacity-50"
        >
          {submitting ? "Guardando…" : "Registrar operación"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-5 py-2 text-xs uppercase tracking-widest font-mono text-ink-muted hover:text-ink"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}

const inputCls =
  "w-full border border-ink/20 px-2 py-1.5 font-mono text-sm bg-paper focus:border-bull focus:outline-none";

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

function ProfileRadio({
  value,
  current,
  onChange,
  label,
}: {
  value: TradeProfile;
  current: TradeProfile;
  onChange: (v: TradeProfile) => void;
  label: string;
}) {
  const active = current === value;
  return (
    <button
      type="button"
      onClick={() => onChange(value)}
      className={`flex-1 px-3 py-2 text-xs uppercase tracking-widest font-mono border transition-colors ${
        active
          ? value === "aggressive"
            ? "border-bear bg-bear text-paper"
            : "border-bull bg-bull text-paper"
          : "border-ink/20 text-ink hover:border-ink/50"
      }`}
    >
      {label}
    </button>
  );
}
