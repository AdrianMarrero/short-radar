import "./globals.css";
import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";

export const metadata: Metadata = {
  title: "Short Radar — Screening de candidatos a corto",
  description:
    "Ranking diario de candidatos a operar en corto en mercados US y europeos. Análisis basado en señales técnicas, fundamentales, noticias y macro.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen flex flex-col">
        <DisclaimerBanner />
        <Header />
        <main className="flex-1 max-w-[1400px] w-full mx-auto px-6 py-8 relative z-10">
          {children}
        </main>
        <footer className="border-t border-ink/15 mt-12 py-6 text-xs text-ink-muted">
          <div className="max-w-[1400px] mx-auto px-6 flex flex-wrap gap-4 justify-between">
            <div>
              <span className="font-mono uppercase tracking-widest">Short·Radar</span> · open source ·
              datos de yfinance, RSS feeds y FRED
            </div>
            <div className="font-mono">
              No es asesoramiento financiero · Operar en corto tiene riesgo elevado
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
