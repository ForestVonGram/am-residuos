import os
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_db_session
from app.core.config import get_settings
from app.main import app
from app.models.gps import GPSDevice
from app.models.operational import Personnel, RouteAssignment, Truck
from app.models.route import CollectionRoute, RouteSchedule

BACKEND_DIR = Path(__file__).resolve().parents[2]
ADMIN_KEY = get_settings().admin_api_key.get_secret_value()
DEVICE_TOKEN = "integration-device-token"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Configura TEST_DATABASE_URL para ejecutar integración con PostgreSQL.")
    environment = os.environ.copy()
    environment["DATABASE_URL"] = value
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=environment,
        check=True,
    )
    return value


@pytest.fixture
async def integration_client(test_database_url: str) -> AsyncIterator[tuple[AsyncClient, object]]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE TABLE assignment_personnel, service_adjustments, "
                "vehicle_positions, gps_devices, route_assignments, route_schedules, "
                "personnel, trucks, collection_routes CASCADE"
            )
        )

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()


async def seed_operation(factory, *, with_device: bool = True):
    timezone = ZoneInfo("${TIMEZONE:?Set TIMEZONE in .env}")
    now = datetime.now(timezone)
    service_date = now.date()
    async with factory() as session:
        route = CollectionRoute(
            code="TEST-01",
            name="Ruta de integración",
            sector="Centro",
            geometry={
                "type": "LineString",
                "coordinates": [[-75.69, 4.53], [-75.68, 4.53]],
            },
        )
        truck = Truck(plate="TST-001", name="Camión de prueba", status="available")
        driver = Personnel(
            first_name="Conductor",
            last_name="Prueba",
            employee_code="TST-DRIVER",
            role="driver",
        )
        session.add_all([route, truck, driver])
        await session.flush()
        start = (now - timedelta(minutes=10)).time().replace(tzinfo=None, second=0, microsecond=0)
        schedule = RouteSchedule(
            route_id=route.id,
            weekday=service_date.weekday(),
            start_time=start,
            duration_minutes=120,
            effective_from=service_date,
            effective_to=service_date,
        )
        assignment = RouteAssignment(
            route_id=route.id,
            truck_id=truck.id,
            effective_from=service_date,
            effective_to=service_date,
            personnel=[driver],
        )
        session.add_all([schedule, assignment])
        device = None
        if with_device:
            import hashlib

            device = GPSDevice(
                device_code="SIM-TEST-001",
                truck_id=truck.id,
                api_token_hash=hashlib.sha256(DEVICE_TOKEN.encode()).hexdigest(),
            )
            session.add(device)
        await session.commit()
        return route.id, truck.id, schedule.id, device.id if device else None, driver.id
