"use client";

/**
 * External link to Yahoo Finance for a ticker — for quick double-check
 * against the source. Stops click propagation so it doesn't trigger row
 * navigation in tables.
 */
export function YahooLink({
  ticker,
  className,
  label = "Yahoo",
}: {
  ticker: string;
  className?: string;
  label?: string;
}) {
  return (
    <a
      href={`https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}`}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      title={`Ver ${ticker} en Yahoo Finance`}
      className={
        className ||
        "text-[10px] font-mono uppercase tracking-widest text-ink-muted hover:text-bull whitespace-nowrap"
      }
    >
      ↗ {label}
    </a>
  );
}
