# Backend - AXM Residuos

Backend local del sistema de rastreo, planificacion y seguimiento de la recoleccion de residuos solidos de Armenia. Incluye el modulo ciudadano y el modulo administrativo/operativo. No incluye frontend, PQRS ni telemetria GPS.

## Que resuelve este modulo

- Consulta las rutas de recoleccion activas y devuelve su trazado como GeoJSON.
- Busca rutas cercanas a una coordenada a partir de trazados GeoJSON.
- Consulta los horarios de una fecha concreta en la zona `America/Bogota`.
- Estima la proxima llegada al punto de la ruta mas cercano al ciudadano.
- Identifica de forma explicita la ETA como `scheduled` y `is_live: false`.
- Muestra al ciudadano la placa y el nombre publico del camion asignado.
- Muestra los nombres y roles del personal operativo asignado.
- Refleja retrasos o cancelaciones informados para una fecha concreta.

## Que resuelve el modulo administrativo y operativo

- Crea, consulta, modifica y desactiva personal operativo.
- Crea, consulta, modifica y desactiva camiones.
- Configura horarios recurrentes de salida y su periodo de vigencia.
- Asigna un camion y una cuadrilla a una ruta durante un periodo.
- Exige que cada cuadrilla tenga al menos un conductor activo.
- Evita que una ruta o camion tenga asignaciones incompatibles durante el mismo periodo.
- Registra retrasos, motivos y cancelaciones sin modificar el horario recurrente.

Las eliminaciones de personal, camiones, horarios y asignaciones son logicas: el registro se conserva y se marca como inactivo para no perder la trazabilidad basica.

La ETA actual es determinista: proyecta el punto consultado sobre el `LineString`, obtiene la fraccion recorrida entre 0 y 1 y la multiplica por la duracion prevista de la jornada. Cuando se integre GPS, esta estimacion se podra reemplazar o complementar con velocidad y posicion reales sin cambiar el contrato publico principal.

## Modelo de datos

`collection_routes` guarda el codigo, nombre, sector y trazado GeoJSON `LineString` en una columna `JSONB`. `route_schedules` guarda dia de la semana (lunes = 0), hora de inicio, duracion esperada y periodo de vigencia.

`personnel` y `trucks` guardan el personal y los vehiculos. `route_assignments` relaciona una ruta con un camion y una cuadrilla durante un periodo. `service_adjustments` representa una novedad de una fecha determinada, como un retraso o una cancelacion.

Las rutas siguen siendo elaboradas manualmente como GeoJSON. Este incremento no genera ni optimiza recorridos. Antes de consumir la API, esos datos deben cargarse en `collection_routes` y asociarse con al menos un horario vigente.

## Ejecucion local

Requisitos locales:

- Python 3.12 o superior.
- PostgreSQL 14 o superior.
- Una base de datos llamada `axm_residuos`.

La configuracion predeterminada de ejemplo espera PostgreSQL en `localhost:5432`. El usuario, la contrasena y los demas valores se configuran en el archivo `.env`.

Los endpoints administrativos requieren el encabezado `X-Admin-Key`. Para desarrollo local, cambia `ADMIN_API_KEY` en `.env` antes de iniciar la aplicacion. La clave incluida en `.env.example` es solo un valor de demostracion.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
.venv/bin/python scripts/seed_routes.py
uvicorn app.main:app --reload
```

El cargador de rutas es idempotente: crea o actualiza por codigo las rutas contenidas en `frontend/public/map-data/rutas.geojson`.

La API queda disponible en `http://localhost:8000` y su documentacion interactiva en `http://localhost:8000/docs`.

## Endpoints publicos

- `GET /health`: comprueba que el proceso responde.
- `GET /api/v1/citizen/routes`: lista las rutas activas.
- `GET /api/v1/citizen/routes?latitude=4.5339&longitude=-75.6811&radius_m=750`: busca rutas cercanas.
- `GET /api/v1/citizen/routes/{route_id}`: devuelve detalle y geometria GeoJSON.
- `GET /api/v1/citizen/schedules?service_date=2026-10-26`: consulta jornadas del dia.
- `GET /api/v1/citizen/eta?latitude=4.5339&longitude=-75.6811`: obtiene la siguiente ETA programada.

Los parametros geograficos se validan y la busqueda se limita por defecto a 750 metros. El radio permitido va de 50 a 10.000 metros.

## Endpoints administrativos

Todos los siguientes endpoints usan el prefijo `/api/v1/admin` y requieren `X-Admin-Key`:

- `GET|POST /personnel`
- `PATCH|DELETE /personnel/{personnel_id}`
- `GET|POST /trucks`
- `PATCH|DELETE /trucks/{truck_id}`
- `GET|POST /schedules`
- `PATCH|DELETE /schedules/{schedule_id}`
- `GET|POST /assignments`
- `PATCH|DELETE /assignments/{assignment_id}`
- `GET|PUT /service-adjustments`
- `DELETE /service-adjustments/{schedule_id}/{service_date}`

Ejemplo de autenticacion local:

```bash
curl -H 'X-Admin-Key: la-clave-definida-en-env' \
  http://localhost:8000/api/v1/admin/trucks
```

Un retraso se registra mediante `PUT`, por lo que enviar de nuevo la misma combinacion de horario y fecha actualiza la novedad en lugar de duplicarla.

## Pruebas y calidad

```bash
pytest
ruff check app tests
```

Las pruebas unitarias cubren el calculo temporal, las operaciones geograficas sobre GeoJSON y las validaciones principales del contrato HTTP. Las consultas persistentes deben cubrirse adicionalmente con pruebas de integracion contra el servicio `database`.
