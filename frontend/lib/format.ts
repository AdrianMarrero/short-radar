export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(v);
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
}

export function fmtMoney(v: number | null | undefined, currency = "USD"): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(2)}K`;
  return v.toFixed(2);
}

export function fmtDate(v: string | Date | null | undefined): string {
  if (!v) return "—";
  const d = typeof v === "string" ? new Date(v) : v;
  return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
}

export function fmtRelativeTime(v: string | Date): string {
  const d = typeof v === "string" ? new Date(v) : v;
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "ahora";
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `hace ${Math.floor(diff / 86400)}d`;
  return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
}

export function setupLabel(s: string): string {
  return ({
    deterioration: "Deterioro",
    event: "Evento",
    technical: "Técnico",
    overextension: "Sobre-extensión",
    avoid_squeeze: "Evitar (squeeze)",
  } as Record<string, string>)[s] || s;
}

export function convictionLabel(c: string): string {
  return ({ low: "Baja", medium: "Media", high: "Alta" } as Record<string, string>)[c] || c;
}

export function horizonLabel(h: string): string {
  return ({ intraday: "Intradía", swing: "Swing", positional: "Posicional" } as Record<string, string>)[h] || h;
}

export function changeColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-ink-muted";
  if (v > 0) return "text-bull";
  if (v < 0) return "text-bear-bright";
  return "text-ink";
}

export function scoreColor(s: number): string {
  if (s >= 75) return "text-bear-bright";
  if (s >= 60) return "text-bear";
  if (s >= 45) return "text-amber";
  return "text-ink-muted";
}
