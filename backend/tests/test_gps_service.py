import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.gps import GPSDevice, VehiclePosition
from app.models.operational import RouteAssignment, Truck
from app.models.route import CollectionRoute, RouteSchedule
from app.schemas.gps import GPSDeviceCreate, GPSDeviceUpdate, PositionInput
from app.services.gps import (
    GPSService,
    InvalidDeviceToken,
    InvalidPosition,
    ResourceNotFound,
)

TOKEN = "device-test-token"


class FakeGPSRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.truck = Truck(
            id=uuid4(),
            plate="TST-001",
            name="Camión de prueba",
            active=True,
        )
        self.device = GPSDevice(
            id=uuid4(),
            device_code="GPS-TEST",
            truck_id=self.truck.id,
            api_token_hash=hashlib.sha256(TOKEN.encode()).hexdigest(),
            active=True,
            created_at=now,
            updated_at=now,
        )
        self.device_rows = [(self.device, self.truck)]
        self.seen: set[datetime] = set()
        self.positions = []
        self.operations = []
        self.cancelled = set()
        self.positions_by_truck = {}

    async def find_device_by_hash(self, token_hash):
        if token_hash == self.device.api_token_hash:
            return self.device
        return None

    async def insert_position(self, device, values):
        recorded_at = values["recorded_at"]
        if recorded_at in self.seen:
            return False
        self.seen.add(recorded_at)
        self.positions.append(values)
        return True

    async def touch_device(self, device, seen_at):
        device.last_seen_at = seen_at

    async def get_truck(self, truck_id):
        return self.truck if truck_id == self.truck.id else None

    async def get_device(self, device_id):
        return self.device if device_id == self.device.id else None

    async def save(self, device):
        device.updated_at = datetime.now(UTC)
        return device

    async def rollback(self):
        return None

    async def list_devices(self):
        return self.device_rows

    async def active_operations(self, service_date, weekday, current_time):
        return self.operations

    async def cancelled_schedule_ids(self, schedule_ids, service_date):
        return self.cancelled

    async def latest_positions(self, truck_ids):
        return self.positions_by_truck


def valid_position(recorded_at: datetime | None = None) -> PositionInput:
    return PositionInput(
        latitude=4.53,
        longitude=-75.68,
        speed_kmh=12,
        heading=90,
        recorded_at=recorded_at or datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_ingestion_accepts_positions_and_deduplicates_timestamp() -> None:
    repository = FakeGPSRepository()
    service = GPSService(repository)
    position = valid_position()

    assert await service.ingest(TOKEN, [position, position]) == (1, 1)
    assert repository.device.last_seen_at is not None


@pytest.mark.asyncio
async def test_ingestion_rejects_invalid_or_inactive_device_tokens() -> None:
    repository = FakeGPSRepository()
    service = GPSService(repository)

    with pytest.raises(InvalidDeviceToken):
        await service.ingest("wrong-token", [valid_position()])

    repository.device.active = False
    with pytest.raises(InvalidDeviceToken, match="inactivo"):
        await service.ingest(TOKEN, [valid_position()])


@pytest.mark.asyncio
async def test_ingestion_rejects_timestamp_more_than_one_minute_ahead() -> None:
    repository = FakeGPSRepository()
    service = GPSService(repository)

    with pytest.raises(InvalidPosition, match="1 minuto"):
        await service.ingest(TOKEN, [valid_position(datetime.now(UTC) + timedelta(minutes=2))])

    assert repository.positions == []


@pytest.mark.asyncio
async def test_device_creation_returns_plaintext_token_once_and_listing_hides_hash() -> None:
    repository = FakeGPSRepository()

    async def save(device):
        device.id = uuid4()
        device.active = True
        device.created_at = datetime.now(UTC)
        device.updated_at = device.created_at
        repository.device_rows.append((device, repository.truck))
        return device

    repository.save = save
    service = GPSService(repository)
    device, token = await service.create_device(
        GPSDeviceCreate(device_code="GPS-NEW", truck_id=repository.truck.id)
    )

    assert token
    assert token != device.model_dump().get("api_token_hash")
    assert "api_token_hash" not in device.model_dump()
    assert (await service.list_devices())[-1].device_code == "GPS-NEW"


@pytest.mark.asyncio
async def test_device_update_deactivate_and_token_regeneration() -> None:
    repository = FakeGPSRepository()
    service = GPSService(repository)
    device = await service.update_device(
        repository.device.id, GPSDeviceUpdate(active=False)
    )
    assert device.active is False
    await service.deactivate_device(repository.device.id)

    read, replacement = await service.regenerate_token(repository.device.id)
    assert read.device_code == "GPS-TEST"
    assert replacement != TOKEN
    assert repository.device.api_token_hash == hashlib.sha256(replacement.encode()).hexdigest()

    with pytest.raises(ResourceNotFound):
        await service.regenerate_token(uuid4())


@pytest.mark.asyncio
async def test_device_update_rejects_missing_device_or_truck() -> None:
    repository = FakeGPSRepository()
    service = GPSService(repository)

    with pytest.raises(ResourceNotFound):
        await service.update_device(uuid4(), GPSDeviceUpdate(active=False))

    with pytest.raises(ResourceNotFound, match="Camión"):
        await service.update_device(
            repository.device.id,
            GPSDeviceUpdate(truck_id=uuid4()),
        )


@pytest.mark.asyncio
async def test_live_vehicle_listing_uses_active_operation_and_latest_position() -> None:
    from zoneinfo import ZoneInfo

    repository = FakeGPSRepository()
    service = GPSService(repository)
    timezone = ZoneInfo("America/Bogota")
    now = datetime.now(timezone)
    route = CollectionRoute(
        id=uuid4(),
        code="TEST",
        name="Ruta test",
        sector="Centro",
        geometry={"type": "LineString", "coordinates": [[-75.69, 4.53], [-75.68, 4.53]]},
    )
    schedule = RouteSchedule(
        id=uuid4(),
        route_id=route.id,
        weekday=now.weekday(),
        start_time=(now - timedelta(minutes=5)).time().replace(tzinfo=None),
        duration_minutes=120,
        effective_from=now.date(),
    )
    assignment = RouteAssignment(
        route_id=route.id, truck_id=repository.truck.id, effective_from=now.date()
    )
    position = VehiclePosition(
        id=uuid4(),
        device_id=repository.device.id,
        truck_id=repository.truck.id,
        latitude=4.53,
        longitude=-75.685,
        recorded_at=datetime.now(UTC),
        speed_kmh=10,
        heading=90,
    )
    repository.operations = [(schedule, route, assignment, repository.truck)]
    repository.positions_by_truck = {repository.truck.id: position}

    live = await service.live_vehicles()

    assert len(live) == 1
    assert live[0].truck_plate == "TST-001"
    assert live[0].simulated is True
    assert live[0].stale is False
