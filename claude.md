# Short Radar / Long Radar — Project Context for Claude Code

## What this project is

Originally built as **Short Radar**: a screening tool that ranked equities as
short candidates (bet on price going down) across US and European markets.

Currently being **reoriented to LONG bias** because the user (Adrián) operates
with **ING Broker Naranja**, which does not offer short selling, CFDs, or
derivatives to retail clients. Long positions are the only realistic operative
mode for this user.

The product name in the UI may still say "Short Radar" in places — this is
acceptable for now; full rebrand to "Long Radar" can happen later. The user
prefers minimal, surgical changes rather than wholesale rewrites.

## User profile (important for design decisions)

- **Capital**: ~2.000€ to allocate
- **Goal stated**: turn 2.000€ into ~2.500€ in a few weeks (+25%)
- **Knowledge level**: basic. Confused "operar en corto" (short selling) with
  "short-term operations" until clarified. Now understands the difference.
- **Broker**: ING Broker Naranja (long only, regular shares)
- **Risk tolerance**: low to moderate. Beginner; should NOT be using leverage.
- **Reality check given**: +25% in weeks is aggressive even for pros. Realistic
  expectations are +5/+12% per trade in the conservative profile, +10/+25%
  in the aggressive profile, with much higher failure rates in the latter.

## Key product decisions (from our planning conversations)

### Two profiles, NOT one ranking
The app exposes ranking results in two distinct tabs:

- **Conservador (`/conservative`)**: confirmed uptrends, healthy fundamentals,
  no near-term binary risk. Targets +5/+12% in 3-6 weeks, win rate ~60%,
  tight stops 3-5%.

- **Agresivo (`/aggressive`)**: emerging breakouts, positive catalysts in
  digestion phase (3-10 days old, NOT same-day news), oversold bounces in
  healthy stocks, sector momentum laggards. Targets +10/+25% in 2-4 weeks,
  win rate ~45%, wider stops 5-7%.

### Critical concept for "Aggressive": catalyst digestion window
We deliberately favor catalysts that are **3-10 days old** over fresh ones.
Reason: by the time retail reads a fresh headline, the move is already
mostly executed by institutional algorithms. A catalyst with 5-7 days that
still has price digestion ongoing is where realistic retail edge exists.
This is implemented in `news_score.py::score_news_long`.

### What we explicitly REJECTED
The user asked for "agressive features" like reading academic papers,
predicting future M&A, advanced research. These were rejected as not feasible
in a free retail app:
- Academic paper reading: no free structured API
- M&A prediction: requires insider information (illegal)
- Premium research: costs thousands per month

What we DO instead in the aggressive profile:
- Earnings calendar awareness (planned, not yet implemented)
- Upgrades/downgrades detection via RSS
- Sector momentum + relative strength
- Insider buying proxy via volume/price patterns
- Breakout detection with volume confirmation

## Technical stack

- **Backend**: Python 3.11, FastAPI 0.115, SQLAlchemy 2.0, APScheduler
- **Frontend**: Next.js 14 App Router + TypeScript + Tailwind CSS
- **DB**: PostgreSQL on Render, SQLite fallback locally
- **Hosting**: Render free tier (Frankfurt region for both API and DB)
- **Data**: yfinance 1.3.0 + curl_cffi 0.15 (Chrome impersonation to bypass
  Yahoo's anti-bot rate limits), feedparser RSS, optional FRED, optional
  Anthropic Claude (Haiku) for explanations

## Project structure

```
short-radar/
├── backend/
│   ├── requirements.txt        # yfinance==1.3.0, curl_cffi==0.15.0
│   ├── .env.example
│   └── app/
│       ├── main.py             # FastAPI app + lifespan
│       ├── api/
│       │   ├── ranking.py      # GET /api/ranking, /conservative, /aggressive
│       │   ├── ticker.py       # GET /api/ticker/{ticker}
│       │   └── admin.py        # POST /api/jobs/run-daily, etc.
│       ├── core/
│       │   ├── config.py
│       │   ├── database.py
│       │   └── logging.py
│       ├── models/
│       │   ├── instrument.py
│       │   ├── market.py
│       │   ├── intel.py
│       │   └── scoring.py
│       ├── scoring/
│       │   ├── engine.py            # LONG-BIAS — produces FinalScore
│       │   ├── technicals.py        # Indicators (pure functions)
│       │   ├── technical_score.py   # LONG-BIAS technical scoring
│       │   ├── news_score.py        # LONG-BIAS news + catalyst digestion
│       │   └── other_scores.py      # LONG-BIAS fundamentals, macro, liq
│       ├── collectors/
│       │   ├── universe.py          # NASDAQ + NYSE + IBEX + DAX + CAC + FTSE
│       │   ├── market_data.py       # yfinance + curl_cffi session
│       │   ├── macro.py             # RSS + FRED
│       │   └── sentiment.py         # English lexicon (limitation: bias to US news)
│       ├── jobs/
│       │   ├── daily.py             # Full pipeline orchestration
│       │   └── scheduler.py         # APScheduler 22:30 UTC
│       └── services/
│           ├── llm.py               # Optional Claude Haiku explanations
│           ├── risk.py              # Position sizing
│           └── backtest.py          # Naive backtest
└── frontend/
    ├── app/
    │   ├── page.tsx                 # Dashboard
    │   ├── conservative/page.tsx    # Conservative ideas
    │   ├── aggressive/page.tsx      # Aggressive ideas
    │   ├── ranking/page.tsx         # Full ranking with filters
    │   ├── ticker/[ticker]/page.tsx # Stock detail
    │   ├── macro/page.tsx
    │   ├── backtest/page.tsx
    │   └── settings/page.tsx        # Run job, weights, history
    ├── components/
    │   ├── Header.tsx               # Top nav
    │   ├── DisclaimerBanner.tsx
    │   ├── RankingTable.tsx
    │   ├── PriceChart.tsx           # Recharts
    │   ├── ScoreBars.tsx
    │   ├── PositionSizer.tsx
    │   ├── Badges.tsx
    │   └── RankingFiltersBar.tsx
    └── lib/
        ├── api.ts                   # fetch client
        ├── types.ts                 # TS types matching Pydantic schemas
        └── format.ts                # Number/date helpers
```

## Database model overview

Key tables (all in `backend/app/models/`):

- `instruments` — universe of tickers
- `prices_daily` — OHLCV history
- `technical_indicators` — daily snapshots of RSI/MACD/SMA/etc.
- `fundamentals` — TTM snapshot per instrument
- `short_data` — short interest (mostly informational now, not used for longs)
- `news_items` — headlines with sentiment, impact, category
- `macro_events` — RSS-derived macro events with sector tagging
- `short_scores` — DAILY score per instrument (NOTE: misnamed, it's
  the ranking score regardless of long/short bias). Includes setup_type,
  conviction, horizon, entry/stop/target_1/target_2, llm_explanation.
- `alerts` — user alerts (not yet wired to UI)
- `job_runs` — audit log of pipeline executions

The `ShortScore` table name is a legacy from the original short-bias design.
It is now used to store long-bias scores. Renaming would require migration;
acceptable to leave as-is for now.

## What works today

- Full pipeline runs end-to-end: data ingestion + scoring + LLM explanations
- /conservative and /aggressive endpoints return filtered candidates
- Frontend pages render properly
- Daily job triggerable from UI (Settings → Ejecutar job ahora)
- Manual trigger required because Render free tier doesn't allow cron
  - Workaround: UptimeRobot pinging /healthz keeps service warm,
    APScheduler internal scheduler runs the daily job at 22:30 UTC

## What we want to add next: Operations Journal

The user wants a **trading journal** to track real operations and measure
whether the app's recommendations actually work in practice. Without this,
they have no way to know if the system is providing edge or not.

### Required functionality

1. **New trade entry**:
   - From any ticker page or ranking row, "Operar esta idea" button
   - Pre-fills entry from current ticker data
   - Asks for: capital invested, entry price, entry date (default today),
     stop, target_1, target_2, optional notes
   - Saves a Trade record (status="open")

2. **Track open trades**:
   - List view of all open trades with: ticker, days held, entry price,
     current price, P&L %, P&L €, distance to stop, distance to target
   - Daily refresh of current price from PriceDaily

3. **Close trade**:
   - Button "Cerrar operación" on each open trade
   - Asks: exit price, exit date (default today), notes
   - Updates status to "closed", records final P&L

4. **Statistics dashboard**:
   - Total trades / open / closed
   - Win rate (% closed with profit)
   - Average return % per trade
   - Best trade, worst trade
   - Average days held
   - Total P&L €
   - Breakdown by setup_type (which setups work best for me?)
   - Breakdown by profile (conservative vs aggressive)

### Data model proposal

```python
class Trade(Base):
    __tablename__ = "trades"
    id: int
    instrument_id: int (FK)
    setup_type: str             # captured from ShortScore at time of entry
    profile: str                # "conservative" / "aggressive"
    capital_eur: float
    entry_price: float
    entry_date: date
    stop_price: float | None
    target_1: float | None
    target_2: float | None
    exit_price: float | None
    exit_date: date | None
    status: str                 # "open" / "closed_win" / "closed_loss" / "stopped"
    notes: str
    pnl_pct: float | None       # computed on close
    pnl_eur: float | None       # computed on close
    created_at: datetime
    updated_at: datetime
```

### API endpoints needed

- `POST /api/trades` — create
- `GET /api/trades?status=open` — list
- `GET /api/trades/{id}` — detail
- `PATCH /api/trades/{id}/close` — close trade with exit_price + exit_date
- `DELETE /api/trades/{id}` — delete (mistakes happen)
- `GET /api/trades/stats` — dashboard stats

### Frontend pages needed

- `frontend/app/journal/page.tsx` — main journal page with tabs:
  - "Abiertas" (open trades table)
  - "Cerradas" (closed trades history)
  - "Estadísticas" (dashboard with stats)
- Update `frontend/components/Header.tsx` to include "Diario" link
- Add a "Operar esta idea" button to ticker detail page (and optionally
  ranking rows) that opens a modal to record the trade

### Design notes

- Editorial style consistent with rest of app (Fraunces serif headings,
  monospace for numbers, paper background, ink text, bear/bull accents)
- P&L positive shown in `text-bull`, negative in `text-bear-bright`
- Stats should be readable at a glance — large numbers, small labels
- DON'T over-engineer: this is a personal journal, not a CRM. No multi-user,
  no auth (admin token is enough for now).

### Pitfalls to avoid

- Don't break existing endpoints. The `ShortScore` table is named that way
  but used for both long and short scores — leave the name.
- Migration: SQLAlchemy `init_db()` creates tables on startup. New `trades`
  table needs to be added to `app.models.__init__.all_models` list to
  auto-create.
- Don't add fields to `ShortScore` — keep Trade as a separate, independent
  table.

## How to deploy after changes

1. `git add . && git commit -m "..." && git push origin main`
2. Render auto-detects push and rebuilds backend + frontend (~5 min)
3. Verify with health check: `curl https://short-radar-api.onrender.com/healthz`
4. New endpoints visible at `/docs`
5. Frontend changes visible at `https://short-radar-web.onrender.com`

## Conventions and style

- Spanish for all user-facing text in the UI
- English for code, comments, log messages, commit messages
- Honest, no-bullshit communication style. The user appreciates being told
  when something is unrealistic (e.g., "+25% in weeks is aggressive").
- Code style: type hints everywhere, dataclasses for structured returns,
  no over-abstraction, no unnecessary patterns. Match the existing style.

## Things that don't work and why

- **Render cron jobs**: not in free tier. Used internal APScheduler + UptimeRobot
  workaround instead.
- **European fundamentals via Yahoo**: limited data quality. Conservative
  profile works fine; aggressive profile has weaker signals on .MC/.DE/.PA/.L
  tickers because lexicon is English-only.
- **Yahoo without curl_cffi**: anti-bot blocks all requests with empty
  responses. Always use the impersonating session.