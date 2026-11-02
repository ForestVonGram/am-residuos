# Registro de incidencias

Hallazgos identificados durante pruebas y correcciones, vinculados con los commits que los resuelven.

| ID | Descripción | Severidad | Módulo | Estado | Commit/PR de corrección |
|---|---|---|---|---|---|
| INC-01 | FastAPI referenciaba una constante de HTTP 422 inexistente y podía fallar al validar una solicitud. | Alta | API | Corregida | `f315988` |
| INC-02 | Conversión de la velocidad de respaldo programada de ETA usaba unidades incorrectas. | Alta | ETA | Corregida | `6927c2f` |
| INC-03 | Bundle inicial superaba el presupuesto existente al importar mapas en la carga principal. | Media | Frontend | Corregida con carga diferida | `97fbd5d` |
| INC-04 | La clave demo admin estaba hardcodeada en el servicio Angular y se incorporaba al bundle. | Alta | Frontend/seguridad | Movida a configuración runtime; sigue siendo visible en el navegador y solo sirve para demo local. | `97fbd5d` |
| INC-05 | Handler de validación devolvía errores Pydantic sin codificar tipos como `datetime`/`UUID`. | Media | API | Corregida con `jsonable_encoder` | `a36f1e9` |
| INC-06 | Ruff detectó imports desordenados en el handler de validación. | Baja | Calidad | Corregida | `a36f1e9` |
| INC-07 | Integración PostgreSQL no pudo ejecutarse porque Docker Engine no estaba disponible en el entorno. | Media | Integración | Pendiente de ejecución en entorno con PostgreSQL | N/A |
| INC-08 | El enlace `#pqrs` no tenía destino y existían dos carpetas frontend huérfanas. | Baja | Frontend | PQRS marcado “próximamente”; componentes huérfanos eliminados | `ec6648f` |
| INC-09 | No había Compose con servicio `database`, ni imagen con `scripts/`/GeoJSON para seed y simulación. | Media | Infraestructura | Compose y Dockerfile actualizados; migraciones corren al inicio | `ec6648f` |
| INC-10 | Se mantenían dependencias divergentes en `backend/requirements`; el simulador requiere `httpx`. | Media | Dependencias | Archivo redundante eliminado y `httpx` declarado en `pyproject.toml` | `2ae0caa`, `ec6648f` |

## Validación de la sesión

- Backend: 42 pruebas aprobadas, 5 de integración omitidas por falta de `TEST_DATABASE_URL`; cobertura de `app.services`: 92,37%.
- Ruff: pasó tras corregir el orden de imports.
- Frontend: 9 pruebas Vitest aprobadas y build Angular completado sin warnings.
- Compose: `docker compose config` válido. No se pudo levantar PostgreSQL para ejecutar integración.
