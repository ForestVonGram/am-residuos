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

Requisitos: Python 3.12 o superior y PostgreSQL 14 o superior. Copia `backend/.env.example` a `backend/.env` y ajusta las variables según tu PostgreSQL local. Desde la raíz, el camino recomendado es:

```sh
docker compose up --build -d backend
docker compose exec backend python scripts/seed_demo.py
docker compose exec backend python scripts/simulate_gps.py --admin-key "change-me-local-only" --loop
```

Compose proporciona el servicio `database`; el contenedor backend ejecuta `alembic upgrade head` antes de iniciar Uvicorn y contiene `scripts/` y el GeoJSON usado por el seed.

Para ejecutar el backend directamente en el host:

```sh
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload
```

La configuración de ejemplo y `change-me-local-only` son exclusivamente para desarrollo. La clave admin enviada desde `frontend/public/app-config.js` queda visible para cualquier usuario del navegador y no constituye una frontera de seguridad de producción.

Los comandos de ejemplo usan la clave demo predeterminada; sustitúyela por el valor local de `ADMIN_API_KEY` si lo cambias. El login Angular también es solo una simulación del MVP y no reemplaza autenticación real del servidor.

## Endpoints principales

### Públicos

- `GET /health`
- `GET /api/v1/citizen/routes`
- `GET /api/v1/citizen/routes/{route_id}`
- `GET /api/v1/citizen/schedules?service_date=YYYY-MM-DD`
- `GET /api/v1/citizen/vehicles/live`
- `GET /api/v1/citizen/eta?latitude=4.5339&longitude=-75.6811`

### Administración

Usan `X-Admin-Key` bajo `/api/v1/admin`: personal, camiones, horarios, asignaciones, ajustes de servicio y `/gps-devices`. Al crear o regenerar un dispositivo, el token en claro se devuelve una sola vez.

### Ingesta GPS

`POST /api/v1/gps/positions` acepta una posición o un lote de hasta 50 con `X-Device-Token`. Rechaza tokens inactivos, coordenadas fuera de rango y fechas más de un minuto en el futuro. Las repeticiones de `(device_id, recorded_at)` se reportan como duplicados.

## Simulación y seed

`scripts/seed_demo.py` carga de forma idempotente las rutas GeoJSON, dos camiones, cuadrillas, horarios recurrentes y dispositivos. Imprime los tokens demo; volver a sembrar rota esos tokens.

`scripts/simulate_gps.py --admin-key <clave>` lee asignaciones activas, crea o regenera dispositivos vía API y envía posiciones con ruido de 3–5 m. Opciones: `--speed-kmh`, `--interval`, `--speedup`, `--dropout-prob`, `--pause-at`, `--pause-seconds`, `--offline-after` y `--loop`. `scripts/validate_eta.py` recorre una ruta acelerada y reporta el error medio absoluto entre las ETA observadas y la llegada simulada.

## Pruebas

```sh
python -m pytest
python -m ruff check app tests scripts
```

Las pruebas de integración están marcadas `integration` y requieren `TEST_DATABASE_URL` apuntando a una base PostgreSQL **dedicada y vacía**. El fixture actualiza sus migraciones y trunca sus tablas antes de cada prueba; no apuntes esa variable a una base con datos que debas conservar. Instrucciones y casos manuales: `docs/PLAN_PRUEBAS.md`.

La configuración CORS proviene de `ALLOWED_ORIGINS`; métodos permitidos: GET, POST, PATCH, PUT, DELETE y OPTIONS. La conexión de base de datos no necesita extensiones espaciales: las geometrías son GeoJSON en JSONB.
