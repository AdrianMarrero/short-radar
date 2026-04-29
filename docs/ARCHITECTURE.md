# Arquitectura

Vista de águila del proyecto. Para detalles de scoring ver `SCORING.md`. Para despliegue, `DEPLOY.md`.

## Componentes

```
┌─────────────────┐         ┌──────────────────┐
│   Next.js 14    │ ──HTTP─▶│   FastAPI 0.115  │
│   (frontend)    │         │   (backend)      │
└─────────────────┘         └────────┬─────────┘
                                     │
                            ┌────────┴─────────┐
                            │                  │
                  ┌─────────▼──────┐  ┌────────▼─────────┐
                  │  PostgreSQL    │  │ External: yfinance│
                  │  (datos+scores)│  │  feedparser, FRED │
                  └────────────────┘  │  Anthropic (LLM)  │
                                      └───────────────────┘
```

El cron diario es un servicio separado que llama vía HTTP al endpoint `run-daily-batch` del backend. Esto permite usar el plan free de Render sin tener que mantener un worker permanente.

## Por qué FastAPI

- Tipado fuerte vía Pydantic, lo que genera schemas y docs OpenAPI gratis.
- Async-friendly, suficiente para nuestro perfil (la mayoría del tiempo se gasta en yfinance, no en CPU).
- Extremadamente sencillo de testear y desplegar.

## Por qué Next.js 14 App Router

- Server Components para cargar datos en el server al renderizar páginas (ranking inicial, detalle del ticker).
- Client Components donde hace falta interactividad (filtros del ranking, sizer de posición).
- Buen build out-of-the-box para Render (npm run build → npm run start).

## Decisiones clave del scoring

1. **Pesos configurables vía env**, no hardcoded. Permite ajustar sin redeploy.
2. **Squeeze risk siempre se evalúa**, incluso si el resto da score alto. Si pasa de 80, el setup se marca `avoid_squeeze` y el score baja drásticamente.
3. **El LLM no decide el score**. Solo escribe la tesis a partir del breakdown estructurado. Esto evita que Claude alucine factores que no están en los datos.
4. **Cada ticker se procesa en su propia transacción** (`session_scope`). Si yfinance falla en uno, el resto continúa.

## Modelo de datos

Tablas principales (ver `backend/app/models/`):

| Tabla | Qué guarda |
|---|---|
| `instruments` | Universo de tickers y metadata (sector, market cap…). |
| `prices_daily` | OHLCV diario, últimos 60 días por instrumento. |
| `technical_indicators` | RSI, MACD, ATR, soportes/resistencias del día. |
| `fundamentals` | Snapshot TTM (revenue, márgenes, FCF, deuda…). |
| `short_data` | Short interest, days-to-cover, float. |
| `news_items` | Titulares con sentiment, impacto y categoría asignados. |
| `macro_events` | Eventos macro detectados de RSS, con sectores afectados. |
| `short_scores` | El score del día por instrumento + plan de trade + explicación. |
| `job_runs` | Auditoría de ejecuciones del job. |

## Pipeline diario

```
Job inicia
  ↓
Ensure instruments (idempotent)
  ↓
Recoger noticias macro (RSS) y persistir
  ↓
Para cada instrumento (transacción independiente):
  ├─ Fetch precios (yfinance)
  ├─ Calcular indicadores técnicos
  ├─ Fetch info (fundamentales + short interest)
  ├─ Fetch noticias del ticker (Yahoo)
  ├─ Analizar sentimiento + categorizar
  ├─ Calcular sub-scores (técnico, news, fund, macro, liq, squeeze)
  ├─ Combinar con pesos → score final
  ├─ Construir trade plan (entry/stop/targets vía ATR)
  ├─ Si score >= 55: invocar LLM para explicación
  └─ Persistir todo
  ↓
Job termina, escribe resumen en job_runs
```

Tiempo total esperado: ~5-10 minutos para 250 tickers en plan free.

## Tests

`backend/tests/test_scoring.py` cubre el motor de scoring con datos sintéticos. No requiere internet. Ejecuta `pytest backend/tests` desde la raíz del backend.

## Qué falta (ver ROADMAP.md)

El MVP es funcional pero hay áreas claras de mejora: caching, webhooks de alertas, autenticación de usuarios, fuentes de datos premium, etc.
