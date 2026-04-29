interface ScoreBarsProps {
  technical: number;
  news: number;
  fundamental: number;
  macro: number;
  liquidity: number;
  squeeze: number;
}

export function ScoreBars({ technical, news, fundamental, macro, liquidity, squeeze }: ScoreBarsProps) {
  const items = [
    { label: "Técnico", value: technical, color: "bg-bear/70" },
    { label: "Noticias", value: news, color: "bg-bear/70" },
    { label: "Fundamental", value: fundamental, color: "bg-bear/70" },
    { label: "Macro", value: macro, color: "bg-bear/70" },
    { label: "Liquidez", value: liquidity, color: "bg-bull/70" },
    { label: "Squeeze risk", value: squeeze, color: "bg-amber" },
  ];
  return (
    <div className="space-y-2 font-mono text-xs">
      {items.map((it) => (
        <div key={it.label} className="grid grid-cols-[110px_1fr_40px] items-center gap-2">
          <div className="uppercase tracking-wider text-ink-muted">{it.label}</div>
          <div className="h-2 bg-ink/10 relative overflow-hidden">
            <div
              className={`absolute inset-y-0 left-0 ${it.color}`}
              style={{ width: `${Math.max(0, Math.min(100, it.value))}%` }}
            />
          </div>
          <div className="text-right tnum">{it.value.toFixed(0)}</div>
        </div>
      ))}
    </div>
  );
}
