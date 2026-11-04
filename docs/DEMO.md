# Guion de demostración

## Preparación

1. Copia `.env.example` a `.env` si aún no existe y reemplaza todos los valores `replace-with-*` por secretos aleatorios. Las variables de acceso se quedan en Compose/backend; ninguna clave se compila en Angular.
2. Inicia base de datos, backend y frontend:

   ```sh
   docker compose up --build -d
   ```

   Compose espera a que PostgreSQL esté saludable; el backend aplica `alembic upgrade head` al arrancar. La interfaz queda disponible en el puerto `FRONTEND_HOST_PORT` (4200 por defecto) y la API en `BACKEND_HOST_PORT` (8000 por defecto).
3. Carga el dataset de demostración:

   ```sh
   docker compose exec backend python scripts/seed_demo.py --start-in-minutes 2
   ```

   El seed reutiliza las dos rutas del GeoJSON, crea o actualiza camiones, conductor y recolector por ruta, horarios de todos los días y dispositivos GPS. Imprime los tokens; el simulador podrá regenerarlos a través de la API admin.
4. En el panel admin puedes crear camiones en **Gestionar camiones** y asociarlos a una ruta junto con una cuadrilla desde **Gestionar asignaciones**. Las asignaciones deben estar vigentes para que el simulador las recorra.
5. Inicia los recorridos simulados como servicio Compose:

   ```sh
   docker compose --profile gps-simulation up -d gps-simulator
   ```

   Detén el servicio con `docker compose stop gps-simulator`. Para ajustar velocidad, intervalo o fallas simuladas, usa directamente `docker compose exec backend python scripts/simulate_gps.py --help`.

## Recorrido

1. Abre `http://localhost:4200/rutas` (o el puerto `FRONTEND_HOST_PORT`); confirma el badge **Simulación** y revisa los dos trazados.
2. Espera al polling (cada 5 segundos) y verifica que el marcador del camión se actualice.
3. Haz clic sobre el mapa o usa la geolocalización del navegador. La tarjeta debe presentar ETA, distancia, estado y fuente en vivo/programada.
4. Si el navegador deniega ubicación, selecciona manualmente un punto en el mapa.
5. Entra al módulo admin con `ADMIN_USERNAME` y `ADMIN_PASSWORD`, configurados en `.env`, y registra un retraso para una jornada. La contraseña se valida en el backend y la sesión se guarda en una cookie `HttpOnly`.
6. Abre **Dispositivos GPS** y pulsa **Actualizar**: confirma el camión asociado, estado en línea, activación/desactivación y que el token se revela solo al crearlo o regenerarlo.
7. Para evaluar la estimación ejecuta `docker compose exec backend python scripts/validate_eta.py --speedup 10`. El proceso imprime el número de observaciones y el error medio absoluto en minutos.

## Supuestos

- Los únicos trazados disponibles son `RUTA-1` y `RUTA-2` del GeoJSON del repositorio; son ejemplos y no se presentan como recorridos reales.
- Los datos del vehículo, posición y velocidad son simulados. No hay GPS físico, integración empresarial ni notificaciones.
- Los horarios del seed son recurrentes; para el día actual comienzan `--start-in-minutes` después del seed, en `America/Bogota`.
- Las credenciales de ejemplo son solo para desarrollo. Usa secretos distintos para `ADMIN_API_KEY` y `ADMIN_SESSION_SECRET`, HTTPS con `ADMIN_COOKIE_SECURE=true` en producción y un gestor de secretos; no publiques `.env`.
- El script de validación mide contra la llegada del recorrido acelerado de pared; un `--speedup` alto reduce el tiempo real de recorrido y forma parte del error reportado.
