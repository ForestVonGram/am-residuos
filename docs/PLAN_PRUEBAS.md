# Plan de pruebas funcionales

## Ejecución automatizada

Desde `backend/`: `python -m pytest` y `python -m ruff check app tests scripts`. La suite frontend se ejecuta en `frontend/` con `npm test` y `npx ng build`.

Las pruebas PostgreSQL están marcadas `integration` y se omiten si no existe `TEST_DATABASE_URL`. Para evitar truncar datos del proyecto, prepara una base de pruebas dedicada:

```sh
docker compose up -d database
docker compose exec database psql -U axm_demo -d postgres -c "CREATE DATABASE axm_residuos_test"
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://axm_demo:axm_demo@localhost:5432/axm_residuos_test"
python -m pytest -m integration
```

El fixture aplica `alembic upgrade head` antes de las pruebas y trunca tablas únicamente en la base indicada. No uses la base de desarrollo como `TEST_DATABASE_URL`.

## Casos funcionales/manuales

Registrar el resultado real de cada ejecución antes de presentar la demo; no se marca como aprobado un caso manual que no se haya ejecutado.

| ID | Módulo | Precondición | Pasos | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|---|---|
| MF-01 | Rutas y horarios | API y seed disponibles | Abrir rutas y consultar horarios de hoy | Se muestran las dos rutas y jornadas en hora de `America/Bogota` | Pendiente de ejecución manual | Pendiente |
| MF-02 | Mapa | Frontend disponible | Abrir `/rutas`, seleccionar cada ruta | Se dibuja su geometría GeoJSON y el encuadre es válido | Pendiente de ejecución manual | Pendiente |
| MF-03 | Seguimiento | Seed y simulador activos | Esperar dos ciclos de polling | Marcador visible con badge “Simulación” y posición actualizada | Pendiente de ejecución manual | Pendiente |
| MF-04 | ETA | Camión simulado activo | Seleccionar punto sobre ruta | ETA en vivo muestra hora, minutos, distancia y estado | Pendiente de ejecución manual | Pendiente |
| MF-05 | Geolocalización | Navegador permite ubicación | Solicitar ubicación desde la tarjeta ETA | Se consulta ubicación actual y presenta la ETA | Pendiente de ejecución manual | Pendiente |
| MF-06 | Permisos | Navegador bloquea ubicación | Denegar permiso y seleccionar punto manualmente | Mensaje claro y alternativa de clic en el mapa | Pendiente de ejecución manual | Pendiente |
| MF-07 | Sin señal | Simulador detenido o `--offline-after` | Consultar vehículo después de 60 s | Posición se marca obsoleta y ETA vuelve a programada | Pendiente de ejecución manual | Pendiente |
| MF-08 | Retraso | Sesión admin y horario de hoy | Crear retraso desde admin y consultar ETA | Ajuste se refleja sin cambiar el horario recurrente | Pendiente de ejecución manual | Pendiente |
| MF-09 | Cancelación | Sesión admin y horario de hoy | Cancelar la jornada y consultar ETA | API/UI informa cancelación y no promete llegada | Pendiente de ejecución manual | Pendiente |
| MF-10 | Administración | Clave admin configurada localmente | Crear/editar camión, horario y asignación | Cambios persisten; conflictos se rechazan con mensaje claro | Pendiente de ejecución manual | Pendiente |
| MF-11 | Dispositivos GPS | Camión existente y sesión admin | Crear dispositivo, activar/desactivar y regenerar token | Token claro solo al crearlo/regenerarlo; estado en línea <30 s | Pendiente de ejecución manual | Pendiente |
| MF-12 | Seguridad | API local disponible | Omitir clave admin; usar credencial admin como token GPS y viceversa | Respuestas 401 y API pública sin secretos ni personal | Cubierto por pruebas automatizadas; integración pendiente de BD | Parcial |
| MF-13 | Validación ETA | Seed y base operativa disponibles | Ejecutar `python scripts/validate_eta.py --admin-key <ADMIN_API_KEY> --speedup 10` | Reporta cantidad de observaciones, llegada simulada y MAE en minutos | No ejecutado: PostgreSQL no disponible en este entorno | Pendiente |

## Validación de tiempos estimados

`backend/scripts/validate_eta.py` publica posiciones del simulador al endpoint GPS, consulta la ETA hacia el final del trazado y contrasta cada predicción con la hora de llegada del recorrido simulado. Ejecútalo con `--speedup 10` para reducir la duración de la demo. El script informa el error medio absoluto (MAE) en minutos; guarda la salida obtenida aquí al ejecutar la validación. El acelerador acorta el tiempo real de llegada y debe tenerse en cuenta al interpretar el MAE.

**Resultado registrado:** no ejecutado en esta sesión; el daemon de Docker/PostgreSQL no estaba disponible.
