# Scoring

El score final es un número 0-100 donde **mayor = mejor candidato a corto**. Pero no es solo eso: el sistema también clasifica el setup, asigna una convicción y construye un plan de trade. Todo es explicable y trazable a los datos.

## Componentes y pesos

| Componente | Peso por defecto | Variable de entorno |
|---|---|---|
| Técnico | 30% | `WEIGHT_TECHNICAL` |
| Noticias | 25% | `WEIGHT_NEWS` |
| Fundamental | 20% | `WEIGHT_FUNDAMENTAL` |
| Macro | 15% | `WEIGHT_MACRO` |
| Liquidez | 10% | `WEIGHT_LIQUIDITY` |
| **Squeeze risk** | **No es un peso, es una penalización** | — |

Para todos: 0 = nada bajista, 100 = muy bajista. Excepto **squeeze risk**, donde 100 = peligro extremo de squeeze.

## Cada subscore

### Técnico

Empieza en 50 y se ajusta con reglas (`backend/app/scoring/technical_score.py`):

| Señal | Ajuste |
|---|---|
| Precio < SMA 50 | +8 |
| Precio < SMA 200 | +6 |
| MACD bajista (< signal y < 0) | +7 |
| RSI 35-50 (debilidad) | +5 |
| Pérdida de soporte reciente | +10 |
| Rebote fallido en resistencia | +8 |
| Volumen alto en venta | +6 |
| Caída -10%+ en el último mes | +4 |
| Precio > SMA 50 + 5% | -10 |
| MACD alcista | -6 |
| RSI < 35 (sobreventa, riesgo rebote) | -4 |
| Volumen alto en compra | -6 |
| Cerca de máximos 52w | -12 |
| Subida +15% en el mes | -8 |

### Noticias

Combina sentiment y impacto de cada titular reciente, con peso por antigüedad (algoritmo en `news_score.py`):

```
weight = recency * (0.3 + 0.7 * impact)
score += -sentiment * weight * 30
```

El **sentiment** sale de `collectors/sentiment.py`: lexicon de palabras financieras adaptado de Loughran-McDonald. Categorías reconocidas: earnings, guidance, regulatory, lawsuit, downgrade, upgrade, dilution, m_a, product, insider.

### Fundamental

Penaliza deterioro real (`other_scores.py`):

| Señal | Ajuste |
|---|---|
| Revenue YoY < -5% | +12 (`deteriorating=True`) |
| Operating margin < 0 | +10 (`deteriorating=True`) |
| FCF negativo | +8 (`deteriorating=True`) |
| Debt/Cash > 5 | +6 |
| EPS < 0 | +4 |
| PE > 50 con crecimiento débil | +6 |

### Macro

Cruza el sector del ticker con los eventos macro recientes. Si hay un `macro_event` con `affected_sectors` que incluye palabras del sector del ticker, suma según el `impact_score` del evento.

### Liquidez

Calculada como volumen medio × precio (dollar volume diario). Se invierte para que **mayor liquidez sea bueno**:

| $/día medio | Score |
|---|---|
| > 100M | 95 |
| 25M - 100M | 80 |
| 5M - 25M | 60 |
| 1M - 5M | 35 |
| < 1M | 15 |

Si el score de liquidez < 40, se aplica una penalización -30 al score final (no operable).

### Squeeze risk

Combinación de short interest, days-to-cover, float y catalizador:

| Señal | Ajuste |
|---|---|
| SI > 30% del float | +50 (extremo) |
| SI 20-30% | +35 |
| SI 10-20% | +15 |
| Days to cover > 8 | +15 |
| Float < 50M | +10 |
| SI alto sin catalizador negativo | +10 (extra) |

Clasificación: <25 low, 25-50 medium, 50-75 high, >75 extreme.

## Combinación final

```python
raw = (
    tech_score * 0.30 + 
    news_score * 0.25 + 
    fund_score * 0.20 + 
    macro_score * 0.15 + 
    liq_score * 0.10
)

# Penalizaciones
if squeeze.score >= 80: raw -= 20
elif squeeze.score >= 60: raw -= 10

if technical.momentum_strongly_bullish and not news.has_negative_catalyst:
    raw -= 25

if liquidity.score < 40: raw -= 30

final = clip(raw, 0, 100)
```

## Clasificación del setup

`engine.py::_classify_setup`:

1. Squeeze extremo → `avoid_squeeze` (no importa el resto, marca como evitar).
2. Hay catalizador de noticia negativo → `event`.
3. Fundamentales se deterioran y técnico ≥55 → `deterioration`.
4. RSI sobrecomprado y rebote fallido → `overextension`.
5. Por defecto → `technical`.

## Convicción

- **Alta**: score ≥ 75 y squeeze low/medium.
- **Media**: score ≥ 60.
- **Baja**: resto, o squeeze extremo.

## Horizonte

| Setup | Horizonte |
|---|---|
| event | swing (2-10 días) |
| technical | swing (5-15 días) |
| deterioration | positional (semanas) |
| overextension | intraday |
| avoid_squeeze | swing (si decides operar a pesar de todo) |

## Plan de trade

`engine.py::_build_trade_plan`:

- **Entry**: cerca de la resistencia si rebote fallido, en la zona del soporte roto si breakdown, o al precio actual.
- **Stop**: encima de la resistencia o a 2× ATR sobre el último cierre.
- **Target 1**: 1.5× la distancia hasta el stop, hacia abajo. Si hay un soporte intermedio, se usa.
- **Target 2**: 3× la distancia hasta el stop.
- **Risk:Reward**: ratio (entry − target_2) / (stop − entry).

## Calibración

Los pesos por defecto son razonables pero no óptimos. Para ajustarlos:

1. Ejecuta el job durante varias semanas (acumula scores históricos).
2. Lanza el backtest desde la página `/backtest`.
3. Si un setup tiene win rate alto pero retorno bajo, sube su peso. Si tiene retorno alto pero pocas señales, no toques nada.
4. Para producción real necesitarías un *walk-forward optimization* — fuera del alcance del MVP.

## Limitaciones

- **El sentiment es lexicon-based**, no LLM. Detecta términos financieros comunes pero falla con sarcasmo, noticias sin contexto, o titulares ambiguos. Mejora futura: usar Claude para clasificar.
- **El short interest viene de yfinance**, que tira del Form 13F y SI bimonthly del NYSE. Se actualiza con retraso de hasta 2 semanas. Para datos en tiempo real necesitarías Ortex o S3 Partners ($$$).
- **No hay datos de cost-to-borrow ni shares-available**. Sin pasarela a IBKR/Saxo. Esto es importante para shorts reales pero queda fuera del MVP.
- **El backtest es ingenuo**. No modela slippage, comisiones, ni borrow fees. Solo sirve como sanity check.

## Cómo ajustar sin redeploy

Para cambiar los pesos en Render: ve al servicio `short-radar-api`, pestaña **Environment**, edita `WEIGHT_TECHNICAL` etc. y haz **Save**. Render reinicia el servicio (~30s). El próximo job usa los nuevos pesos. Los scores antiguos no se recalculan automáticamente; si quieres recalcular, lanza el job manualmente desde Ajustes.
