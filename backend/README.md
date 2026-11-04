# Backend de AXM Residuos

API FastAPI con PostgreSQL, SQLAlchemy asíncrono y Alembic. Proporciona consultas ciudadanas, administración operativa y telemetría GPS **simulada**. No tiene conexión con vehículos físicos ni con la empresa de aseo; las rutas corresponden a los dos trazados de ejemplo del repositorio.

## Funcionalidad

- Consulta rutas GeoJSON, horarios y ETA programada o en vivo.
- Registra retrasos y cancelaciones para jornadas específicas.
- Administra camiones, personal, horarios, asignaciones y dispositivos GPS.
- Recibe posiciones con `X-Device-Token`, guarda solo hashes de tokens y descarta duplicados.
- Expone posiciones recientes de camiones sin revelar tokens ni personal.

La telemetría se marca como simulada en la respuesta pública (`simulated: true`) y en la interfaz. El simulador usa `POST /api/v1/gps/positions`, que también es el endpoint preparado para dispositivos reales.

## Desarrollo local

Requisitos: Python 3.12 o superior y PostgreSQL 14 o superior. En Docker Compose, configura el `.env` raíz con `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_HOST=database`; `DATABASE_URL` se arma automáticamente con esos valores. Para ejecutar el backend directamente en el host, copia `backend/.env.example` a `backend/.env` y usa `POSTGRES_HOST=localhost`. En ambos casos configura las credenciales administrativas y reemplaza los valores de ejemplo por secretos aleatorios. El camino recomendado es:

```sh
docker compose up --build -d backend
docker compose exec backend python scripts/seed_demo.py
docker compose --profile gps-simulation up --build -d gps-simulator
docker compose logs -f gps-simulator
```

Compose proporciona el servicio `database`; el contenedor backend ejecuta `alembic upgrade head` antes de iniciar Uvicorn y contiene `scripts/` y el GeoJSON usado por el seed.

Para ejecutar el backend directamente en el host:

```sh
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload --port "${APP_PORT:-8000}"
```

El login administrativo compara `ADMIN_USERNAME` y `ADMIN_PASSWORD` en el backend y crea una cookie firmada, `HttpOnly`, `SameSite=Strict` y con expiración configurable mediante `ADMIN_SESSION_TTL_SECONDS`. La contraseña debe tener al menos 12 caracteres y `ADMIN_SESSION_SECRET` al menos 32. `ADMIN_API_KEY` (mínimo 32 caracteres) permanece solo en backend y se usa para scripts de confianza; nunca se incorpora al bundle Angular. En producción configura `APP_ENV=production` y `ADMIN_COOKIE_SECURE=true`, sirve la aplicación por HTTPS y usa un gestor de secretos.

## Endpoints principales

### Públicos

- `GET /health`
- `GET /api/v1/citizen/routes`
- `GET /api/v1/citizen/routes/{route_id}`
- `GET /api/v1/citizen/schedules?service_date=YYYY-MM-DD`
- `GET /api/v1/citizen/vehicles/live`
- `GET /api/v1/citizen/eta?latitude=4.5339&longitude=-75.6811`

### Administración

`POST /api/v1/admin/auth/login` recibe usuario y contraseña configurados en el backend; la sesión se conserva en una cookie `HttpOnly`. `/api/v1/admin/auth/session` comprueba la sesión y `/api/v1/admin/auth/logout` la cierra. Los endpoints administrativos aceptan la cookie web o `X-Admin-Key` para scripts de confianza. Al crear o regenerar un dispositivo, el token en claro se devuelve una sola vez.

### Ingesta GPS

`POST /api/v1/gps/positions` acepta una posición o un lote de hasta 50 con `X-Device-Token`. Rechaza tokens inactivos, coordenadas fuera de rango y fechas más de un minuto en el futuro. Las repeticiones de `(device_id, recorded_at)` se reportan como duplicados.

## Simulación y seed

`scripts/seed_demo.py` carga de forma idempotente las rutas GeoJSON, dos camiones, cuadrillas, horarios recurrentes y dispositivos. Imprime los tokens demo; volver a sembrar rota esos tokens.

`scripts/simulate_gps.py --admin-key <clave>` lee asignaciones activas, crea o regenera dispositivos vía API y envía posiciones con ruido de 3–5 m. Usa `API_INTERNAL_URL` si está configurada; si no, se conecta a `127.0.0.1` usando `APP_PORT` (o el puerto `8000` por defecto). La zona horaria usa `TIMEZONE` o `America/Bogota`. Opciones: `--speed-kmh`, `--interval`, `--speedup`, `--dropout-prob`, `--pause-at`, `--pause-seconds`, `--offline-after` y `--loop`. `scripts/validate_eta.py` recorre una ruta acelerada y reporta el error medio absoluto entre las ETA observadas y la llegada simulada.

## Pruebas

```sh
python -m pytest
python -m ruff check app tests scripts
```

Las pruebas de integración están marcadas `integration` y requieren `TEST_DATABASE_URL` apuntando a una base PostgreSQL **dedicada y vacía**. El fixture actualiza sus migraciones y trunca sus tablas antes de cada prueba; no apuntes esa variable a una base con datos que debas conservar. Instrucciones y casos manuales: `docs/PLAN_PRUEBAS.md`.

La configuración CORS proviene de `ALLOWED_ORIGINS`; métodos permitidos: GET, POST, PATCH, PUT, DELETE y OPTIONS. La conexión de base de datos no necesita extensiones espaciales: las geometrías son GeoJSON en JSONB.
