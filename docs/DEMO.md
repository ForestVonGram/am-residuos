# Guion de demostración

## Preparación

1. Copia `.env.example` a `.env` y define `ADMIN_API_KEY`. El valor debe coincidir con `adminApiKey` en `frontend/public/app-config.js` para administrar desde el navegador. Esa configuración es pública en el bundle y solo se usa localmente.
2. Inicia base de datos y backend:

   ```sh
   docker compose up --build -d backend
   ```

   Compose espera a que PostgreSQL esté saludable; el backend aplica `alembic upgrade head` al arrancar.
3. Carga el dataset de demostración:

   ```sh
   docker compose exec backend python scripts/seed_demo.py --start-in-minutes 2
   ```

   El seed reutiliza las dos rutas del GeoJSON, crea o actualiza camiones, conductor y recolector por ruta, horarios de todos los días y dispositivos GPS. Imprime los tokens; el simulador podrá regenerarlos a través de la API admin.
4. En otra terminal inicia la interfaz:

   ```sh
   cd frontend
   npm ci
   npm start
   ```

5. Inicia los recorridos simulados:

   ```sh
   docker compose exec backend python scripts/simulate_gps.py --admin-key "change-me-local-only" --speed-kmh 25 --interval 3 --speedup 1 --loop
   ```

   Sustituye `change-me-local-only` por el valor configurado en `.env` si cambiaste la clave.
   Para una demostración rápida usa `--speedup 10`; `--dropout-prob 0.2`, `--pause-at 0.5 --pause-seconds 60` y `--offline-after 20` permiten ilustrar pérdida de señal, detención y desconexión.

## Recorrido

1. Abre `http://localhost:4200/rutas`; confirma el badge **Simulación** y revisa los dos trazados.
2. Espera al polling (cada 5 segundos) y verifica que el marcador del camión se actualice.
3. Haz clic sobre el mapa o usa la geolocalización del navegador. La tarjeta debe presentar ETA, distancia, estado y fuente en vivo/programada.
4. Si el navegador deniega ubicación, selecciona manualmente un punto en el mapa.
5. Entra al módulo admin con las credenciales demo del login y registra un retraso para una jornada. Regresa a la consulta ciudadana y verifica el ajuste de la llegada. El login frontend es simulado y no debe considerarse autenticación real.
6. Abre **Dispositivos GPS**: confirma el camión asociado, estado en línea, activación/desactivación y que el token se revela solo al crearlo o regenerarlo.
7. Para evaluar la estimación ejecuta `docker compose exec backend python scripts/validate_eta.py --admin-key "change-me-local-only" --speedup 10`. El proceso imprime el número de observaciones y el error medio absoluto en minutos.

## Supuestos

- Los únicos trazados disponibles son `RUTA-1` y `RUTA-2` del GeoJSON del repositorio; son ejemplos y no se presentan como recorridos reales.
- Los datos del vehículo, posición y velocidad son simulados. No hay GPS físico, integración empresarial ni notificaciones.
- Los horarios del seed son recurrentes; para el día actual comienzan `--start-in-minutes` después del seed, en `America/Bogota`.
- Las credenciales y contraseñas demo son para una demostración local, no para producción. No publiques el `ADMIN_API_KEY` ni uses la clave runtime del frontend para proteger datos sensibles.
- El script de validación mide contra la llegada del recorrido acelerado de pared; un `--speedup` alto reduce el tiempo real de recorrido y forma parte del error reportado.
