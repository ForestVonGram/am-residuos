# AXM Residuos

MVP universitario para consultar rutas y horarios de recolección en Armenia, Quindío, ver vehículos y estimar su llegada. Las dos rutas son trazados de ejemplo; **toda la telemetría GPS es simulada** y no representa recorridos reales ni conexión con la empresa de aseo.

## Inicio rápido

Requisitos: Docker Compose, Node.js 22.22.3 o superior y npm.

1. Copia `.env.example` como `.env` y ajusta `ADMIN_API_KEY` para tu demo.
2. Ejecuta `docker compose up --build -d backend` desde la raíz. Se inicia PostgreSQL y el backend aplica las migraciones al arrancar.
3. Carga rutas, camiones, asignaciones y dispositivos demo:

   ```sh
   docker compose exec backend python scripts/seed_demo.py --start-in-minutes 2
   ```

4. En `frontend/public/app-config.js`, configura `adminApiKey` con el valor local de `ADMIN_API_KEY`. Es configuración de demostración visible en el navegador; nunca la uses como secreto de producción.
5. En otra terminal:

   ```sh
   cd frontend
   npm ci
   npm start
   ```

6. Inicia los dos vehículos simulados:

   ```sh
   docker compose exec backend python scripts/simulate_gps.py --admin-key "change-me-local-only" --loop
   ```

7. Abre `http://localhost:4200/rutas`; la API y su documentación están en `http://localhost:8000` y `http://localhost:8000/docs`.

El simulador aprovisiona o regenera las credenciales de dispositivo vía API admin y envía posiciones a la misma ruta de ingesta que usaría un dispositivo físico (`POST /api/v1/gps/positions`). Consulta el guion en [docs/DEMO.md](./docs/DEMO.md).

Los comandos de ejemplo usan `change-me-local-only`; reemplázalo por el valor configurado en `.env` si cambias la clave.

## Pruebas

```sh
cd backend
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check app tests scripts
```

Las pruebas PostgreSQL se ejecutan por separado y requieren una base de pruebas dedicada; consulta [docs/PLAN_PRUEBAS.md](./docs/PLAN_PRUEBAS.md). La guía de incidencias está en [docs/INCIDENCIAS.md](./docs/INCIDENCIAS.md).
