# Despliegue en Render

## Paso 0: Crear cuenta y conectar GitHub

1. Crea cuenta gratis en [render.com](https://render.com).
2. Sube este proyecto a un repositorio de GitHub (público o privado, da igual).
3. En Render, en el dashboard, conecta tu cuenta de GitHub si no lo has hecho ya.

## Paso 1: Lanzar el blueprint

1. En Render, click en **New** → **Blueprint**.
2. Selecciona el repo de Short Radar.
3. Render detectará automáticamente el fichero `render.yaml` en la raíz.
4. Te pedirá darle un nombre al blueprint y confirmar. Click en **Apply**.

Render ahora empezará a crear cuatro recursos:

| Recurso | Tipo | Plan | Para qué sirve |
|---|---|---|---|
| `short-radar-db` | PostgreSQL | Free | Base de datos |
| `short-radar-api` | Web service (Python) | Free | Backend FastAPI |
| `short-radar-web` | Web service (Node) | Free | Frontend Next.js |
| `short-radar-daily` | Cron job (Python) | Free | Ejecuta el job cada día |

El primer build tarda ~5-10 minutos.

## Paso 2: Rellenar variables manuales

Render te pedirá rellenar estas variables (todas opcionales excepto `CORS_ORIGINS`):

### En `short-radar-api`:

- **`CORS_ORIGINS`** — Pon la URL del frontend cuando esté creada. Ejemplo: `https://short-radar-web.onrender.com`. **Esto es obligatorio** o el frontend no podrá hablar con el backend.
- **`ANTHROPIC_API_KEY`** *(opcional)* — Si la pones, las explicaciones de cada candidato las escribirá Claude Haiku. Sin ella, se usan plantillas deterministas en español.
- **`FRED_API_KEY`** *(opcional)* — Mejora los datos macro. Gratis en [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).

El resto se generan o conectan solas (DATABASE_URL, ADMIN_TOKEN, NEXT_PUBLIC_API_URL...).

## Paso 3: Primer arranque

1. Espera a que los tres servicios pongan estado **Live** en verde.
2. Abre la URL del frontend (la verás en `short-radar-web` → Settings).
3. Verás el dashboard pero sin datos. Es normal: aún no se ha ejecutado el job.
4. Ve a **Ajustes** y pulsa **Ejecutar job ahora**. Tardará ~3-5 minutos.
5. Refresca la página principal: ya verás el ranking.

A partir de ahí, el cron se ejecuta solo cada día a las 22:30 UTC.

## Por qué Render se duerme y cómo afecta

El plan free de Render **duerme los web services tras 15 minutos sin tráfico**. La primera petición tras dormir tarda ~30 segundos en responder mientras el contenedor arranca. Cosas a tener en cuenta:

- El cron diario **siempre se ejecuta**, esté el web dormido o no, porque el cron es un servicio independiente.
- Si entras al frontend y la primera carga es lenta, es porque el backend se estaba despertando.
- Si quieres mantenerlo siempre despierto, una opción gratis es usar un servicio externo tipo [UptimeRobot](https://uptimerobot.com) que haga ping a `/healthz` cada 5 minutos.

## Coste

**0 €/mes** mientras estés en plan free.

Lo que pierdes vs un plan de pago:
- 750 horas/mes de cómputo (suficiente para uno o dos servicios siempre activos, o varios durmiendo)
- BD se elimina tras 90 días de inactividad (no preocuparse, los precios y scores se vuelven a generar el siguiente job)
- 100 GB de transferencia (más que suficiente)

## Logs y debugging

Cada servicio tiene su pestaña **Logs** en Render. Cosas útiles:

- Si el job falla en `short-radar-api`, busca lines `[ERROR]`.
- Si yfinance da rate-limits puntualmente, aparecerán warnings y el job continuará con el resto.
- Si el frontend no conecta, comprueba que `CORS_ORIGINS` en el backend incluye la URL exacta del frontend (con `https://` y sin slash final).

## Alternativas si Render no te convence

El proyecto está construido sin lock-in:

| Opción | Notas |
|---|---|
| **Vercel + Railway** | Vercel para el frontend (free, mejor que Render para Next.js). Railway para backend + Postgres (free $5/mes de crédito). Necesitarás duplicar la config a mano. |
| **Fly.io** | Free tier generoso. Hay que escribir un `fly.toml` por servicio. |
| **VPS Hetzner** | 4-5€/mes y todo en una sola máquina con Docker Compose. Mejor relación rendimiento/precio. |

Si decides migrar, el código no cambia: solo el sistema de orquestación.
