"""Load the frontend GeoJSON routes into PostgreSQL.

Run from ``backend`` with ``.venv/bin/python scripts/seed_routes.py``.
The operation is idempotent: existing routes are updated by code.
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.database.session import AsyncSessionFactory, engine
from app.models.route import CollectionRoute

GEOJSON_PATH = Path(__file__).parents[2] / "frontend/public/map-data/rutas.geojson"


async def seed_routes() -> None:
    collection = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    async with AsyncSessionFactory() as session:
        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            if geometry.get("type") != "LineString" or not geometry.get("coordinates"):
                raise ValueError("Cada ruta debe tener una geometria GeoJSON LineString")
            code = properties["code"]
            statement = insert(CollectionRoute).values(
                code=code,
                name=properties.get("name", code),
                description=properties.get("description"),
                sector=properties.get("sector", "Armenia"),
                geometry=geometry,
                active=True,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[CollectionRoute.code],
                set_={
                    "name": statement.excluded.name,
                    "description": statement.excluded.description,
                    "sector": statement.excluded.sector,
                    "geometry": statement.excluded.geometry,
                    "active": True,
                },
            )
            await session.execute(statement)
        await session.commit()
    await engine.dispose()
    print(f"Rutas cargadas: {len(features)}")


if __name__ == "__main__":
    asyncio.run(seed_routes())
