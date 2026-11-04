FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
RUN pip install --no-cache-dir ./backend

COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/migrations ./backend/migrations
COPY backend/scripts ./backend/scripts
COPY frontend/public/map-data/rutas.geojson ./frontend/public/map-data/rutas.geojson
WORKDIR /app/backend

ARG APP_PORT=8000
EXPOSE ${APP_PORT}

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port \"${APP_PORT}\""]
