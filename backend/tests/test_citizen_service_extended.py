from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models.gps import VehiclePosition
from app.models.operational import Personnel, RouteAssignment, ServiceAdjustment, Truck
from app.models.route import CollectionRoute, RouteSchedule
from app.repositories.citizen import LocatedRoute, PublicOperation
from app.services.citizen import CitizenService, RouteNotFoundError


class FakeCitizenRepository:
    def __init__(self) -> None:
        self.zone = ZoneInfo("America/Bogota")
        self.now = datetime.now(self.zone)
        self.route = CollectionRoute(
            id=uuid4(),
            code="AXM-01",
            name="Ruta Centro",
            description="Ruta de prueba",
            sector="Centro",
            geometry={"type": "LineString", "coordinates": [[-75.69, 4.53], [-75.68, 4.53]]},
            active=True,
        )
        self.schedule = RouteSchedule(
            id=uuid4(),
            route_id=self.route.id,
            weekday=self.now.weekday(),
            start_time=(self.now - timedelta(minutes=10)).time().replace(tzinfo=None),
            duration_minutes=120,
            effective_from=self.now.date(),
            effective_to=self.now.date(),
            active=True,
        )
        self.operation = PublicOperation(assignment=None, adjustment=None)
        self.positions = {}

    async def list_routes(self, latitude=None, longitude=None, radius_m=750):
        return [(self.route, 10.0)]

    async def get_route(self, route_id):
        if route_id != self.route.id:
            return None
        return self.route, self.route.geometry

    async def list_schedules(self, service_date, route_id=None):
        if service_date.weekday() == self.schedule.weekday:
            return [(self.schedule, self.route)]
        return []

    async def list_schedules_for_dates(self, service_dates, route_ids):
        return [
            (self.schedule, self.route, service_date)
            for service_date in service_dates
            if service_date.weekday() == self.schedule.weekday
            and service_date == self.now.date()
        ]

    async def get_public_operation(self, route_id, schedule_id, service_date):
        return self.operation

    async def get_public_operations(self, rows):
        return {
            (route.id, schedule.id, service_date): self.operation
            for schedule, route, service_date in rows
        }

    async def locate_routes(self, latitude, longitude, radius_m, route_id):
        if route_id and route_id != self.route.id:
            return []
        return [LocatedRoute(self.route, 42.25, 0.5)]

    async def get_tracking_positions(self, truck_ids, since):
        return self.positions


@pytest.mark.asyncio
async def test_routes_and_schedules_are_mapped_to_public_schemas() -> None:
    repository = FakeCitizenRepository()
    service = CitizenService(repository)

    routes = await service.list_routes(None, None, 750)
    detail = await service.get_route(repository.route.id)
    schedules = await service.list_schedules(repository.now.date(), repository.route.id)

    assert routes[0].distance_m == 10.0
    assert detail.geometry == repository.route.geometry
    assert schedules[0].truck is None
    assert schedules[0].delay_minutes == 0


@pytest.mark.asyncio
async def test_missing_route_and_no_nearby_eta_are_not_found() -> None:
    repository = FakeCitizenRepository()
    service = CitizenService(repository)

    with pytest.raises(RouteNotFoundError):
        await service.get_route(uuid4())
    with pytest.raises(RouteNotFoundError):
        await service.estimate_arrival(0, 0, uuid4(), repository.now, 50)


@pytest.mark.asyncio
async def test_estimate_returns_cancelled_status_for_cancelled_journey() -> None:
    repository = FakeCitizenRepository()
    repository.operation = PublicOperation(
        assignment=None,
        adjustment=ServiceAdjustment(
            schedule_id=repository.schedule.id,
            service_date=repository.now.date(),
            delay_minutes=0,
            cancelled=True,
        ),
    )
    service = CitizenService(repository)

    response = await service.estimate_arrival(
        4.53, -75.685, repository.route.id, repository.now, 750
    )

    assert response.status == "cancelled"
    assert response.source == "scheduled"
    assert "cancelada" in response.message


@pytest.mark.asyncio
async def test_estimate_uses_recent_live_position_and_public_assignment() -> None:
    repository = FakeCitizenRepository()
    truck = Truck(id=uuid4(), plate="ABC-123", name="Camión AXM")
    driver = Personnel(
        id=uuid4(), first_name="Ana", last_name="Pérez", role="driver", active=True
    )
    assignment = RouteAssignment(
        id=uuid4(),
        route_id=repository.route.id,
        truck_id=truck.id,
        truck=truck,
        personnel=[driver],
        effective_from=repository.now.date(),
        effective_to=repository.now.date(),
    )
    repository.operation = PublicOperation(assignment=assignment, adjustment=None)
    position = VehiclePosition(
        id=uuid4(),
        device_id=uuid4(),
        truck_id=truck.id,
        latitude=4.53,
        longitude=-75.69,
        speed_kmh=20,
        heading=90,
        recorded_at=datetime.now(ZoneInfo("UTC")),
    )
    repository.positions = {truck.id: [position]}
    service = CitizenService(repository)

    response = await service.estimate_arrival(
        4.53, -75.685, repository.route.id, repository.now, 750
    )

    assert response.source == "live"
    assert response.is_live is True
    assert response.vehicle_position is not None
    assert response.simulated is True
    assert response.truck is not None and response.truck.plate == "ABC-123"
    assert response.personnel[0].name == "Ana Pérez"


@pytest.mark.asyncio
async def test_stale_live_position_falls_back_to_schedule_with_message() -> None:
    repository = FakeCitizenRepository()
    truck = Truck(id=uuid4(), plate="ABC-123", name="Camión AXM")
    assignment = RouteAssignment(
        id=uuid4(),
        route_id=repository.route.id,
        truck_id=truck.id,
        truck=truck,
        personnel=[],
        effective_from=repository.now.date(),
        effective_to=repository.now.date(),
    )
    repository.operation = PublicOperation(assignment=assignment, adjustment=None)
    repository.positions = {
        truck.id: [
            VehiclePosition(
                id=uuid4(),
                device_id=uuid4(),
                truck_id=truck.id,
                latitude=4.53,
                longitude=-75.69,
                recorded_at=datetime.now(ZoneInfo("UTC")) - timedelta(seconds=90),
            )
        ]
    }
    service = CitizenService(repository)

    response = await service.estimate_arrival(
        4.53, -75.685, repository.route.id, repository.now, 750
    )

    assert response.source == "scheduled"
    assert response.is_live is False
    assert response.vehicle_position is not None and response.vehicle_position.stale
    assert "desactualizada" in response.message
