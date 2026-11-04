# AXM Residuos

MVP universitario para consultar rutas y horarios de recolección en Armenia, Quindío, ver vehículos y estimar su llegada. Las dos rutas son trazados de ejemplo; **toda la telemetría GPS es simulada** y no representa recorridos reales ni conexión con la empresa de aseo.

## Inicio rápido

Requisito: Docker Compose.

1. Copia `.env.example` como `.env` si todavía no existe (si ya tienes `.env`, agrega las variables nuevas desde el ejemplo). `DATABASE_URL` se construye automáticamente desde `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST` y `POSTGRES_CONTAINER_PORT`; para Compose el host es `database`. Reemplaza los valores `replace-with-*` por secretos únicos; genera cada valor aleatorio con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Usa una `ADMIN_PASSWORD` de al menos 12 caracteres y secretos separados de al menos 32 caracteres para `ADMIN_API_KEY` y `ADMIN_SESSION_SECRET`. No publiques `.env`.
2. Ejecuta `docker compose up --build -d` desde la raíz. Se inician PostgreSQL, backend y frontend; el backend aplica las migraciones al arrancar.
3. Carga rutas, camiones, asignaciones y dispositivos demo:

   ```sh
   docker compose exec backend python scripts/seed_demo.py --start-in-minutes 2
   ```

4. Abre el puerto definido por `FRONTEND_HOST_PORT` (por defecto `http://localhost:4200`). La interfaz reenvía las llamadas `/api` al backend; la API y su documentación están disponibles en `BACKEND_HOST_PORT` (por defecto `http://localhost:8000`).
5. Para iniciar la simulación continua de GPS sobre las rutas con asignaciones activas:

   ```sh
   docker compose --profile gps-simulation up -d gps-simulator
   ```

   Detenla con `docker compose stop gps-simulator`. El estado de conexión aparece en **Administración → Dispositivos GPS**; usa **Actualizar** para consultar el último estado.

El simulador aprovisiona o regenera las credenciales de dispositivo vía API admin y envía posiciones a la misma ruta de ingesta que usaría un dispositivo físico (`POST /api/v1/gps/positions`). Consulta el guion en [docs/DEMO.md](./docs/DEMO.md).

En el panel se pueden crear camiones desde **Gestionar camiones**, asociarlos a rutas desde **Gestionar asignaciones** y consultar los dispositivos simulados en **Dispositivos GPS**. El simulador requiere asignaciones activas; para camiones nuevos, asígnalos primero a una ruta vigente.

El panel valida `ADMIN_USERNAME` y `ADMIN_PASSWORD` en el backend y usa una cookie de sesión `HttpOnly`; `ADMIN_API_KEY` no se envía al navegador y se reserva para scripts internos. Los puertos publicados, el origen CORS y la URL interna de API se configuran en `.env`. En producción habilita HTTPS y `ADMIN_COOKIE_SECURE=true`; usa un gestor de secretos en lugar de un archivo `.env`.

Si una clave real se usó con versiones anteriores, rótala: quedó expuesta en bundles del navegador y puede permanecer en cachés o historial de Git.

## Pruebas

```sh
cd backend
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check app tests scripts
```

El frontend también puede ejecutarse fuera de Docker con `cd frontend`, `npm ci` y `npm start`; en ese caso se usa el proxy local de `frontend/proxy.conf.js`, que lee `API_LOCAL_URL` desde el `.env` raíz.

Las pruebas PostgreSQL se ejecutan por separado y requieren una base de pruebas dedicada; consulta [docs/PLAN_PRUEBAS.md](./docs/PLAN_PRUEBAS.md). La guía de incidencias está en [docs/INCIDENCIAS.md](./docs/INCIDENCIAS.md).
