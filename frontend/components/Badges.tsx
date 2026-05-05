import { setupLabel, convictionLabel } from "@/lib/format";
import type { Tier } from "@/lib/types";

const SETUP_STYLES: Record<string, string> = {
  deterioration: "bg-bear/10 text-bear border-bear/30",
  event: "bg-amber/10 text-amber border-amber/30",
  technical: "bg-ink/5 text-ink border-ink/20",
  overextension: "bg-bear-bright/10 text-bear-bright border-bear-bright/30",
  avoid_squeeze: "bg-ink text-paper border-ink",
};

export function SetupBadge({ setup }: { setup: string }) {
  const cls = SETUP_STYLES[setup] || SETUP_STYLES.technical;
  return (
    <span
      className={`inline-block text-[10px] uppercase tracking-widest font-mono px-2 py-0.5 border ${cls}`}
    >
      {setupLabel(setup)}
    </span>
  );
}

const CONV_STYLES: Record<string, string> = {
  high: "text-bear font-bold",
  medium: "text-ink font-medium",
  low: "text-ink-muted",
};

export function ConvictionBadge({ conviction }: { conviction: string }) {
  return (
    <span className={`text-xs uppercase tracking-wider ${CONV_STYLES[conviction] || ""}`}>
      {convictionLabel(conviction)}
    </span>
  );
}

const TIER_STYLES: Record<string, string> = {
  "A+": "bg-bull text-paper border-bull",
  A: "bg-paper text-bull border-bull",
  B: "bg-paper text-ink border-ink/40",
  C: "bg-paper text-ink-muted border-ink/20",
  D: "bg-paper text-ink-muted/60 border-ink/10",
};

export function TierBadge({ tier }: { tier?: Tier | null }) {
  if (!tier) return null;
  const cls = TIER_STYLES[tier] || TIER_STYLES.D;
  return (
    <span
      className={`inline-block text-[11px] uppercase tracking-widest font-mono font-bold px-2 py-0.5 border ${cls}`}
      title={`Tier ${tier}`}
    >
      {tier}
    </span>
  );
}

const WARNING_LABELS: Record<string, string> = {
  extended: "Sobre-extendido",
  chased: "Tarde para entrar",
  earnings_approaching: "Earnings próximo",
  rr_below_standard: "RR bajo estándar",
  sector_weakening: "Sector débil",
  high_realized_vol: "Volatilidad alta",
  fresh_news_chase_risk: "Noticia fresca (riesgo)",
  near_52w_high: "Cerca máximo 52s",
  thin_liquidity: "Liquidez baja",
  parabolic_shape: "Forma parabólica",
  low_quality_fundamentals: "Calidad baja",
};

export function warningLabel(code: string): string {
  return WARNING_LABELS[code] || code.replace(/_/g, " ");
}

export function WarningChips({ warnings }: { warnings?: string[] | null }) {
  if (!warnings || warnings.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {warnings.map((w) => (
        <span
          key={w}
          className="inline-block text-[10px] uppercase tracking-widest font-mono px-1.5 py-0.5 border border-bear-bright/40 text-bear-bright bg-bear-bright/5"
          title={w}
        >
          {warningLabel(w)}
        </span>
      ))}
    </div>
  );
}
