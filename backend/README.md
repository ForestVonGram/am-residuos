# Backend - modulo ciudadano de AXM Residuos

Primer incremento del sistema de rastreo, planificacion y seguimiento de la recoleccion de residuos solidos de Armenia. En esta fase solo se implementa la API publica para rutas, horarios y tiempos estimados; no se incluye frontend, administracion, PQRS ni telemetria GPS.

## Que resuelve este modulo

- Consulta las rutas de recoleccion activas y devuelve su trazado como GeoJSON.
- Busca rutas cercanas a una coordenada usando PostGIS.
- Consulta los horarios de una fecha concreta en la zona `America/Bogota`.
- Estima la proxima llegada al punto de la ruta mas cercano al ciudadano.
- Identifica de forma explicita la ETA como `scheduled` y `is_live: false`.

La ETA actual es determinista: proyecta el punto consultado sobre el `LineString`, obtiene la fraccion recorrida entre 0 y 1 y la multiplica por la duracion prevista de la jornada. Cuando se integre GPS, esta estimacion se podra reemplazar o complementar con velocidad y posicion reales sin cambiar el contrato publico principal.

## Modelo de datos

`collection_routes` guarda el codigo, nombre, sector y trazado `LineString` con SRID 4326. `route_schedules` guarda dia de la semana (lunes = 0), hora de inicio, duracion esperada y periodo de vigencia.

Las rutas siguen siendo elaboradas manualmente como GeoJSON. Este incremento no genera ni optimiza recorridos. Antes de consumir la API, esos datos deben cargarse en `collection_routes` y asociarse con al menos un horario vigente.

## Ejecucion local

Requisitos locales:

- Python 3.12 o superior.
- PostgreSQL con la extension PostGIS disponible.
- Una base de datos llamada `axm_residuos`.

La configuracion predeterminada espera PostgreSQL en `localhost:5432`, con usuario y contrasena `postgres`. Estos valores se pueden cambiar en el archivo `.env`.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

La API queda disponible en `http://localhost:8000` y su documentacion interactiva en `http://localhost:8000/docs`.

## Endpoints publicos

- `GET /health`: comprueba que el proceso responde.
- `GET /api/v1/citizen/routes`: lista las rutas activas.
- `GET /api/v1/citizen/routes?latitude=4.5339&longitude=-75.6811&radius_m=750`: busca rutas cercanas.
- `GET /api/v1/citizen/routes/{route_id}`: devuelve detalle y geometria GeoJSON.
- `GET /api/v1/citizen/schedules?service_date=2026-10-26`: consulta jornadas del dia.
- `GET /api/v1/citizen/eta?latitude=4.5339&longitude=-75.6811`: obtiene la siguiente ETA programada.

Los parametros geograficos se validan y la busqueda se limita por defecto a 750 metros. El radio permitido va de 50 a 10.000 metros.

## Pruebas y calidad

```bash
pytest
ruff check app tests
```

Las pruebas unitarias cubren el calculo temporal y las validaciones principales del contrato HTTP. Las consultas espaciales requieren PostgreSQL con PostGIS y deben cubrirse adicionalmente con pruebas de integracion contra el servicio `database`.
