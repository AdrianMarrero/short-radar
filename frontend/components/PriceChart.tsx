"use client";

import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import type { PriceOut, TechnicalsOut } from "@/lib/types";

interface Props {
  prices: PriceOut[];
  technicals: TechnicalsOut | null;
  entry?: number | null;
  stop?: number | null;
  target?: number | null;
}

export function PriceChart({ prices, technicals, entry, stop, target }: Props) {
  if (!prices.length) {
    return (
      <div className="h-72 border border-ink/15 flex items-center justify-center text-ink-muted">
        Sin datos de precio
      </div>
    );
  }

  const data = prices.map((p) => ({
    date: p.date,
    close: p.close,
    high: p.high,
    low: p.low,
  }));

  return (
    <div className="border border-ink/15 p-4">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="display-heading text-lg">Precio (60 días)</h3>
        <div className="flex gap-3 text-[10px] uppercase tracking-widest font-mono text-ink-muted">
          <span><span className="inline-block w-3 h-px bg-ink mr-1 align-middle"></span>Cierre</span>
          {entry && <span><span className="inline-block w-3 h-px bg-bear mr-1 align-middle"></span>Entry</span>}
          {stop && <span><span className="inline-block w-3 h-px bg-bear-bright mr-1 align-middle"></span>Stop</span>}
          {target && <span><span className="inline-block w-3 h-px bg-bull mr-1 align-middle"></span>Target</span>}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id="closeFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1B1816" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#1B1816" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tickFormatter={(v) => new Date(v).toLocaleDateString("es-ES", { day: "2-digit", month: "short" })}
            stroke="#7A7368"
            tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
            tickLine={false}
            axisLine={{ stroke: "#1B1816", strokeOpacity: 0.2 }}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            stroke="#7A7368"
            tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
            tickLine={false}
            axisLine={{ stroke: "#1B1816", strokeOpacity: 0.2 }}
            domain={["auto", "auto"]}
            tickFormatter={(v) => v.toFixed(0)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#F2EDE4",
              border: "1px solid #1B1816",
              borderRadius: 0,
              fontFamily: "JetBrains Mono",
              fontSize: 12,
            }}
            labelFormatter={(v) =>
              new Date(v).toLocaleDateString("es-ES", { day: "2-digit", month: "long", year: "numeric" })
            }
            formatter={(v: number) => v.toFixed(2)}
          />
          <Area type="monotone" dataKey="close" stroke="none" fill="url(#closeFill)" />
          <Line type="monotone" dataKey="close" stroke="#1B1816" strokeWidth={1.5} dot={false} />
          {entry && <ReferenceLine y={entry} stroke="#7A1F1F" strokeDasharray="4 4" label={{ value: "Entry", fill: "#7A1F1F", fontSize: 10, position: "right" }} />}
          {stop && <ReferenceLine y={stop} stroke="#C03B3B" strokeDasharray="4 4" label={{ value: "Stop", fill: "#C03B3B", fontSize: 10, position: "right" }} />}
          {target && <ReferenceLine y={target} stroke="#1F4D2C" strokeDasharray="4 4" label={{ value: "Target", fill: "#1F4D2C", fontSize: 10, position: "right" }} />}
          {technicals?.support_level && <ReferenceLine y={technicals.support_level} stroke="#7A7368" strokeDasharray="2 6" label={{ value: "Sup", fill: "#7A7368", fontSize: 9, position: "left" }} />}
          {technicals?.resistance_level && <ReferenceLine y={technicals.resistance_level} stroke="#7A7368" strokeDasharray="2 6" label={{ value: "Res", fill: "#7A7368", fontSize: 9, position: "left" }} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
