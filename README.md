# Short Radar

Aplicación de screening para detectar candidatos a operar en corto en mercados US y europeos. Combina señales técnicas, fundamentales, noticias, macro y riesgo de squeeze para generar un ranking diario explicable.

> ⚠️ **Esto NO es asesoramiento financiero.** La app genera ideas y análisis. Las decisiones y operaciones son responsabilidad del usuario. Operar en corto tiene riesgo elevado y las pérdidas pueden superar el capital invertido.

## Stack

- **Backend**: FastAPI + SQLAlchemy + APScheduler (Python 3.11)
- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- **BD**: PostgreSQL (con fallback a SQLite en local)
- **Datos**: yfinance, feedparser RSS, FRED (todo gratis)
- **LLM**: Anthropic Claude (opcional, con fallback a explicación plantilla)
- **Hosting**: Render (free tier) — un solo `render.yaml`

## Estructura

```
short-radar/
├── backend/         # FastAPI + scoring + jobs
│   └── app/
│       ├── api/         # Endpoints REST
│       ├── collectors/  # yfinance, news, macro
│       ├── scoring/     # Motor de scoring
│       ├── jobs/        # Job diario
│       ├── models/      # SQLAlchemy
│       ├── services/    # LLM, backtest
│       └── core/        # Config, DB
├── frontend/        # Next.js dashboard
└── docs/            # Documentación adicional
```

## Quick start local

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Frontend (otra terminal)
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Abre http://localhost:3000.

Primera vez: ejecuta el job para poblar el ranking.

```bash
curl -X POST http://localhost:8000/api/jobs/run-daily
```

## Despliegue en Render

Hay un `render.yaml` en la raíz. Conecta el repo en Render y se despliega solo (BD + backend + frontend + cron diario). Detalles en `docs/DEPLOY.md`.

## Documentación

- `docs/ARCHITECTURE.md` — Decisiones de diseño
- `docs/SCORING.md` — Cómo se calcula el score
- `docs/DEPLOY.md` — Despliegue paso a paso
- `docs/ROADMAP.md` — Qué falta y qué hay que mejorar

## Disclaimer

Esta herramienta es para análisis y screening. No ejecuta operaciones, no se conecta a ningún broker, y no es asesoramiento financiero. Úsala como input adicional, nunca como decisión única.
