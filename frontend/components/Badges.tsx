import { setupLabel, convictionLabel } from "@/lib/format";

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
