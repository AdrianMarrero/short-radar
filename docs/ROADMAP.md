# Roadmap

Lista priorizada de mejoras sobre el MVP, desde lo más útil a lo más opcional.

## Corto plazo (mejoras directas al MVP actual)

### Datos
- [ ] **Mejor short interest**: integrar finra.org o Ortex (de pago) para SI semanal en lugar del bimonthly de yfinance.
- [ ] **Cost-to-borrow real**: scrapeable desde IBKR (con cuenta) o desde plataformas como ChartExchange. Ahora mismo no se calcula.
- [ ] **Earnings calendar**: hoy no sabemos cuándo reporta una compañía. Añadir feed de earnings (Yahoo lo expone parcialmente, Finnhub free lo tiene mejor) para evitar abrir cortos justo antes de un earnings.
- [ ] **Insider transactions** (SEC Form 4): SecAPI o EDGAR raw. Insider selling masivo es señal fuerte.

### Scoring
- [ ] **Sentiment con LLM**: el lexicon actual es ok pero pierde matices. Pasar titulares a Claude Haiku en batches para clasificar mejor (especialmente categoría e impacto).
- [ ] **Detección de patrones**: head-and-shoulders, double-top, etc. Hoy solo detectamos breakdown de soporte y rebote en resistencia.
- [ ] **Calibración de pesos por backtest**: hacer un endpoint que ajuste pesos óptimos vía grid search sobre backtests históricos.
- [ ] **Sector momentum**: penalizar shorts en sectores que están subiendo fuerte (relative strength).

### UX
- [ ] **Watchlists** del usuario (ahora todo es global).
- [ ] **Alertas por email/Telegram**: hay tabla `Alert` modelada pero no hay sender. Añadir SendGrid o Telegram bot.
- [ ] **Histórico del score** por ticker: ahora solo vemos el último. Añadir gráfico de evolución.
- [ ] **Compare**: vista lado a lado de dos tickers.
- [ ] **Internacionalización**: añadir inglés (la UI está en español hardcoded en muchos sitios).

## Medio plazo (cambios de arquitectura)

- [ ] **Auth de usuarios** real (NextAuth o Clerk). Hoy es single-user.
- [ ] **Caching agresivo** con Redis: el cron escribe, el frontend lee de Redis para no estresar Postgres free.
- [ ] **Workers separados**: en lugar del cron HTTP, un worker dedicado tipo Celery o RQ. Necesario si subes a 1000+ tickers.
- [ ] **WebSocket para precios live** durante sesión: hoy todo es daily.
- [ ] **Migrar a Alembic** para gestionar el schema en lugar de `create_all`.

## Largo plazo (features ambiciosas)

- [ ] **Pair trading detector**: para cada short, sugerir un long correlacionado para hacer una operación market-neutral.
- [ ] **Portfolio simulator**: ver cómo iría un portfolio que abriera shorts en cada idea con sizing automático.
- [ ] **Bias detector**: avisar cuando el sistema lleva 5+ ideas seguidas que han fallado en una dirección. Útil contra mercados eufóricos.
- [ ] **Datos de opciones**: put/call ratio, IV, large unusual options. Buena señal anticipada.
- [ ] **Integración con broker** (IBKR, Saxo, Trade Republic) para enviar órdenes con un click. Esto requiere licencias y due diligence regulatoria — gran salto.

## Cosas que **NO** voy a hacer y por qué

- **Day trading intradía con datos tick-level**: requiere otro stack (kdb+, una infraestructura de baja latencia). Out of scope.
- **Crypto**: el modelo de scoring asume fundamentales tipo equity. Crypto necesita métricas distintas.
- **Auto-trading**: tener un sistema que opere solo es 10× más complejo que uno que sugiera ideas. Y mucho más peligroso. La app es y seguirá siendo un screener de ideas.

## Limitaciones conocidas del MVP

- yfinance es no oficial y se rompe a veces. Sin alternativa free al mismo nivel de completitud por ahora.
- El backtest del MVP no modela borrow fees ni comisiones. No te creas los retornos absolutos, solo los relativos entre setups.
- En plan free de Render todo se duerme. Si quieres datos siempre frescos, paga 7$/mes el web service o pásate a un VPS.
