# AXM Residuos

MVP universitario para consultar rutas y horarios de recolección en Armenia, Quindío, ver vehículos y estimar su llegada. Las dos rutas son trazados de ejemplo; **toda la telemetría GPS es simulada** y no representa recorridos reales ni conexión con la empresa de aseo.

## Inicio rápido

Requisito: Docker Compose.

1. Copia `.env.example` como `.env` si todavía no existe y configura `ADMIN_API_KEY` para tu demo.
2. Ejecuta `docker compose up --build -d` desde la raíz. Se inician PostgreSQL, backend y frontend; el backend aplica las migraciones al arrancar.
3. Carga rutas, camiones, asignaciones y dispositivos demo:

   ```sh
   docker compose exec backend python scripts/seed_demo.py --start-in-minutes 2
   ```

4. Abre `http://localhost:4200`. La interfaz reenvía las llamadas `/api` al backend; la API y su documentación están en `http://localhost:8000` y `http://localhost:8000/docs`.
5. Para iniciar la simulación continua de GPS sobre las rutas con asignaciones activas:

   ```sh
   docker compose --profile gps-simulation up -d gps-simulator
   ```

   Detenla con `docker compose stop gps-simulator`. El estado de conexión aparece en **Administración → Dispositivos GPS**; usa **Actualizar** para consultar el último estado.

El simulador aprovisiona o regenera las credenciales de dispositivo vía API admin y envía posiciones a la misma ruta de ingesta que usaría un dispositivo físico (`POST /api/v1/gps/positions`). Consulta el guion en [docs/DEMO.md](./docs/DEMO.md).

En el panel se pueden crear camiones desde **Gestionar camiones**, asociarlos a rutas desde **Gestionar asignaciones** y consultar los dispositivos simulados en **Dispositivos GPS**. El simulador requiere asignaciones activas; para camiones nuevos, asígnalos primero a una ruta vigente.

La clave admin se inyecta en el bundle del frontend durante la construcción y queda visible para cualquier usuario del navegador. La clave demo y el login simulado son solo para desarrollo; no los uses como mecanismo de autenticación de producción.

## Pruebas

```sh
cd backend
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check app tests scripts
```

El frontend también puede ejecutarse fuera de Docker con `cd frontend`, `npm ci` y `npm start`; en ese caso se usa el proxy local y `frontend/public/app-config.js`.

Las pruebas PostgreSQL se ejecutan por separado y requieren una base de pruebas dedicada; consulta [docs/PLAN_PRUEBAS.md](./docs/PLAN_PRUEBAS.md). La guía de incidencias está en [docs/INCIDENCIAS.md](./docs/INCIDENCIAS.md).
