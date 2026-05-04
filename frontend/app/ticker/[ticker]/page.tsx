import { notFound } from "next/navigation";
import Link from "next/link";
import { getTicker } from "@/lib/api";
import { PriceChart } from "@/components/PriceChart";
import { ScoreBars } from "@/components/ScoreBars";
import { SetupBadge, ConvictionBadge } from "@/components/Badges";
import { PositionSizer } from "@/components/PositionSizer";
import { TradeIdeaForm } from "@/components/TradeIdeaForm";
import {
  fmtNum, fmtPct, fmtMoney, fmtRelativeTime, scoreColor, changeColor,
  horizonLabel,
} from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function TickerPage({ params }: { params: { ticker: string } }) {
  let detail;
  try {
    detail = await getTicker(decodeURIComponent(params.ticker));
  } catch (e: any) {
    notFound();
  }

  const { instrument, score, technicals, fundamentals, short_data, recent_prices, recent_news, explanation } = detail;
  const lastPrice = recent_prices.length ? recent_prices[recent_prices.length - 1].close : null;

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <Link href="/ranking" className="text-xs uppercase tracking-widest font-mono text-ink-muted hover:text-bear">
        ← Volver al ranking
      </Link>

      {/* Header */}
      <header className="border-b border-ink/15 pb-6 grid md:grid-cols-[1fr_auto] gap-6 items-end">
        <div>
          <div className="flex items-baseline gap-3 mb-1">
            <h1 className="display-heading text-6xl tracking-tightest">{instrument.ticker}</h1>
            <span className="text-xs uppercase tracking-widest font-mono text-ink-muted border border-ink/30 px-2 py-0.5">
              {instrument.exchange}
            </span>
          </div>
          <div className="text-xl text-ink-light">{instrument.name}</div>
          <div className="text-sm text-ink-muted mt-1">
            {instrument.sector} {instrument.industry && `· ${instrument.industry}`} · {instrument.currency}
          </div>
        </div>

        <div className="text-right">
          <div className="font-mono text-3xl tnum">{fmtMoney(lastPrice, instrument.currency)}</div>
          {technicals && (
            <div className={`font-mono text-sm tnum ${changeColor(technicals.change_1d)}`}>
              {fmtPct(technicals.change_1d)} hoy · {fmtPct(technicals.change_1m)} 1M
            </div>
          )}
          {score && (
            <div className="mt-3 flex justify-end items-baseline gap-2">
              <span className={`display-heading text-5xl tracking-tightest ${scoreColor(score.total_score)}`}>
                {score.total_score.toFixed(0)}
              </span>
              <span className="text-xs uppercase tracking-widest font-mono text-ink-muted">/100</span>
            </div>
          )}
        </div>
      </header>

      {!score && (
        <div className="border border-amber/40 bg-amber/5 p-4 text-sm">
          Aún no hay score calculado para este ticker. Lanza el job diario.
        </div>
      )}

      {/* Setup & Plan */}
      {score && (
        <section className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 border border-ink/15 p-5">
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <SetupBadge setup={score.setup_type} />
              <span className="text-xs uppercase tracking-widest font-mono text-ink-muted">·</span>
              <span className="text-xs uppercase tracking-widest font-mono">{horizonLabel(score.horizon)}</span>
              <span className="text-xs uppercase tracking-widest font-mono text-ink-muted">·</span>
              <ConvictionBadge conviction={score.conviction} />
            </div>

            <h3 className="display-heading text-xl mb-2">Tesis</h3>
            <p className="text-base leading-relaxed text-ink-light whitespace-pre-line">
              {explanation || "Sin explicación generada."}
            </p>
          </div>

          <div className="border border-ink/15 p-5">
            <h3 className="display-heading text-xl mb-3">Plan operativo</h3>
            <div className="space-y-2 font-mono text-sm">
              <PlanRow label="Entry" value={score.entry_price} />
              <PlanRow label="Stop" value={score.stop_price} accent="bear" />
              <PlanRow label="Target 1" value={score.target_1} accent="bull" />
              <PlanRow label="Target 2" value={score.target_2} accent="bull" />
            </div>
            {score.invalidation_reason && (
              <div className="mt-4 pt-3 border-t border-ink/10 text-xs">
                <div className="uppercase tracking-widest font-mono text-ink-muted mb-1">Invalidación</div>
                <div className="text-ink-light">{score.invalidation_reason}</div>
              </div>
            )}
            <TradeIdeaForm
              instrumentId={instrument.id}
              ticker={instrument.ticker}
              score={score}
              lastClose={lastPrice ?? null}
            />
          </div>
        </section>
      )}

      {/* Chart */}
      <section>
        <PriceChart
          prices={recent_prices}
          technicals={technicals}
          entry={score?.entry_price}
          stop={score?.stop_price}
          target={score?.target_2}
        />
      </section>

      {/* Score breakdown + Position sizer */}
      <section className="grid lg:grid-cols-2 gap-6">
        {score && (
          <div className="border border-ink/15 p-5">
            <h3 className="display-heading text-xl mb-4">Desglose del score</h3>
            <ScoreBars
              technical={score.technical_score}
              news={score.news_score}
              fundamental={score.fundamental_score}
              macro={score.macro_score}
              liquidity={score.liquidity_score}
              squeeze={score.squeeze_risk_score}
            />
            <p className="text-[11px] text-ink-muted mt-4 leading-relaxed">
              Pesos por defecto: técnico 30%, noticias 25%, fundamental 20%, macro 15%, liquidez 10%.
              El squeeze risk se aplica como penalización al final.
            </p>
          </div>
        )}

        <PositionSizer
          defaultEntry={score?.entry_price}
          defaultStop={score?.stop_price}
          defaultTarget={score?.target_2}
        />
      </section>

      {/* Indicators + Fundamentals + Short */}
      <section className="grid md:grid-cols-3 gap-6">
        {technicals && (
          <Card title="Indicadores técnicos">
            <Row label="RSI 14" value={fmtNum(technicals.rsi_14, 1)} />
            <Row label="MACD" value={fmtNum(technicals.macd, 2)} />
            <Row label="MACD signal" value={fmtNum(technicals.macd_signal, 2)} />
            <Row label="ATR 14" value={fmtNum(technicals.atr_14, 2)} />
            <Row label="Vol relativo" value={fmtNum(technicals.relative_volume, 2)} />
            <Row label="SMA 50" value={fmtNum(technicals.sma_50, 2)} />
            <Row label="SMA 200" value={fmtNum(technicals.sma_200, 2)} />
            <Row label="Soporte" value={fmtNum(technicals.support_level, 2)} />
            <Row label="Resistencia" value={fmtNum(technicals.resistance_level, 2)} />
            <Row label="52w high" value={fmtNum(technicals.high_52w, 2)} />
            <Row label="52w low" value={fmtNum(technicals.low_52w, 2)} />
          </Card>
        )}

        {fundamentals && (
          <Card title="Fundamentales (TTM)">
            <Row label="Revenue" value={fmtMoney(fundamentals.revenue)} />
            <Row label="Crec. revenue" value={fundamentals.revenue_growth_yoy != null ? fmtPct(fundamentals.revenue_growth_yoy * 100) : "—"} />
            <Row label="Margen op." value={fundamentals.operating_margin != null ? fmtPct(fundamentals.operating_margin * 100) : "—"} />
            <Row label="Margen bruto" value={fundamentals.gross_margin != null ? fmtPct(fundamentals.gross_margin * 100) : "—"} />
            <Row label="Free cash flow" value={fmtMoney(fundamentals.free_cash_flow)} />
            <Row label="Deuda" value={fmtMoney(fundamentals.debt)} />
            <Row label="Caja" value={fmtMoney(fundamentals.cash)} />
            <Row label="EPS" value={fmtNum(fundamentals.eps)} />
            <Row label="P/E" value={fmtNum(fundamentals.pe, 1)} />
          </Card>
        )}

        {short_data && (
          <Card title="Short interest">
            <Row label="SI / float" value={short_data.short_percent_float != null ? fmtPct(short_data.short_percent_float * 100) : "—"} />
            <Row label="Days to cover" value={fmtNum(short_data.days_to_cover, 1)} />
            <Row label="Short shares" value={fmtMoney(short_data.short_interest)} />
            <Row label="Float" value={fmtMoney(short_data.float_shares)} />
            <div className="text-[11px] text-ink-muted mt-3 leading-relaxed">
              Squeeze risk score: <strong>{score?.squeeze_risk_score.toFixed(0) ?? "—"}/100</strong>.
              Datos vía yfinance, pueden tener varios días de retraso.
            </div>
          </Card>
        )}
      </section>

      {/* News */}
      {recent_news.length > 0 && (
        <section>
          <h2 className="display-heading text-2xl mb-4">Noticias recientes</h2>
          <div className="border border-ink/15">
            {recent_news.map((n, i) => (
              <article key={i} className="border-b border-ink/10 last:border-0 p-4 flex gap-4">
                <div className="flex-shrink-0 w-12 text-center">
                  <div className={`font-mono text-sm tnum font-bold ${
                    n.sentiment_score < -0.3 ? "text-bear-bright" :
                    n.sentiment_score > 0.3 ? "text-bull" : "text-ink-muted"
                  }`}>
                    {n.sentiment_score > 0 ? "+" : ""}{n.sentiment_score.toFixed(2)}
                  </div>
                  <div className="text-[9px] uppercase tracking-widest text-ink-muted font-mono">sent.</div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] uppercase tracking-widest font-mono text-ink-muted mb-1 flex gap-2 flex-wrap">
                    <span>{n.source}</span>
                    {n.category && <><span>·</span><span>{n.category}</span></>}
                    <span>·</span>
                    <span>{fmtRelativeTime(n.published_at)}</span>
                  </div>
                  <a
                    href={n.url || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm leading-snug hover:text-bear transition-colors block"
                  >
                    {n.title}
                  </a>
                  {n.summary && (
                    <p className="text-xs text-ink-muted mt-1 line-clamp-2">{n.summary}</p>
                  )}
                </div>
                <div className="flex-shrink-0 text-right">
                  <div className="text-[9px] uppercase tracking-widest text-ink-muted font-mono">impact</div>
                  <div className="font-mono text-sm tnum">{(n.impact_score * 100).toFixed(0)}</div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-ink/15 p-4">
      <h3 className="display-heading text-lg mb-3">{title}</h3>
      <div className="space-y-1.5 text-sm">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-ink/5 last:border-0 py-1">
      <span className="text-ink-muted text-xs uppercase tracking-wider">{label}</span>
      <span className="font-mono tnum">{value}</span>
    </div>
  );
}

function PlanRow({ label, value, accent }: { label: string; value: number | null; accent?: "bear" | "bull" }) {
  const cls = accent === "bear" ? "text-bear" : accent === "bull" ? "text-bull" : "text-ink";
  return (
    <div className="flex justify-between items-baseline border-b border-ink/5 last:border-0 py-2">
      <span className="text-ink-muted text-xs uppercase tracking-wider">{label}</span>
      <span className={`tnum font-bold text-lg ${cls}`}>{value != null ? value.toFixed(2) : "—"}</span>
    </div>
  );
}
