"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_ATTEMPTS = 60; // ~2 minutes at 2s intervals
const POLL_INTERVAL_MS = 2000;

export function WakeApiButton() {
  const [status, setStatus] = useState<"idle" | "waking" | "ok" | "failed">("idle");
  const [elapsed, setElapsed] = useState(0);

  async function wake() {
    setStatus("waking");
    setElapsed(0);
    const started = Date.now();
    for (let i = 0; i < MAX_ATTEMPTS; i++) {
      try {
        const res = await fetch(`${API_URL}/healthz`, { cache: "no-store" });
        if (res.ok) {
          setStatus("ok");
          setTimeout(() => window.location.reload(), 500);
          return;
        }
      } catch {
        // network error, keep polling
      }
      setElapsed(Math.round((Date.now() - started) / 1000));
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    setStatus("failed");
  }

  if (status === "idle") {
    return (
      <button
        onClick={wake}
        className="mt-3 border border-ink/40 px-4 py-2 text-xs uppercase tracking-widest font-mono hover:bg-ink hover:text-paper transition-colors"
      >
        Despertar API
      </button>
    );
  }

  if (status === "waking") {
    return (
      <div className="mt-3 text-xs font-mono text-ink-muted">
        Despertando API… <span className="tnum">{elapsed}s</span> (puede tardar hasta 2 min en el primer arranque)
      </div>
    );
  }

  if (status === "ok") {
    return <div className="mt-3 text-xs font-mono text-bull">API arriba — recargando…</div>;
  }

  return (
    <div className="mt-3 text-xs font-mono text-bear-bright">
      No respondió tras 2 min. Revisá el dashboard de Render.
    </div>
  );
}
