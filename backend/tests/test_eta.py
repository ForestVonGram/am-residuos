from datetime import date, datetime, time
from uuid import uuid4

import pytest

from app.models.route import CollectionRoute, RouteSchedule
from app.repositories.citizen import LocatedRoute, PublicOperation
from app.services.citizen import CitizenService
from app.services.eta import expected_arrival


def test_expected_arrival_uses_progress_over_scheduled_duration() -> None:
    schedule = RouteSchedule(
        weekday=0,
        start_time=time(6, 0),
        duration_minutes=120,
        effective_from=date(2026, 1, 1),
    )

    start, arrival = expected_arrival(date(2026, 10, 26), schedule, 0.25, "America/Bogota")

    assert start.isoformat() == "2026-10-26T06:00:00-05:00"
    assert arrival.isoformat() == "2026-10-26T06:30:00-05:00"


def test_expected_arrival_bounds_invalid_progress() -> None:
    schedule = RouteSchedule(
        weekday=0,
        start_time=time(20, 0),
        duration_minutes=90,
        effective_from=date(2026, 1, 1),
    )

    _, before_start = expected_arrival(date(2026, 10, 26), schedule, -1, "America/Bogota")
    _, after_end = expected_arrival(date(2026, 10, 26), schedule, 2, "America/Bogota")

    assert before_start.isoformat() == "2026-10-26T20:00:00-05:00"
    assert after_end.isoformat() == "2026-10-26T21:30:00-05:00"


class FakeETARepository:
    def __init__(self, route: CollectionRoute, schedule: RouteSchedule) -> None:
        self.route = route
        self.schedule = schedule

    async def locate_routes(self, latitude, longitude, radius_m, route_id):
        return [LocatedRoute(self.route, distance_m=42.25, progress_fraction=0.5)]

    async def list_schedules(self, service_date, route_id=None):
        if service_date.weekday() == self.schedule.weekday:
            return [(self.schedule, self.route)]
        return []

    async def get_public_operation(self, route_id, schedule_id, service_date):
        return PublicOperation(assignment=None, adjustment=None)


@pytest.mark.asyncio
async def test_service_selects_next_scheduled_arrival() -> None:
    route = CollectionRoute(
        id=uuid4(), code="AXM-01", name="Centro", sector="Centro", geometry="unused"
    )
    schedule = RouteSchedule(
        id=uuid4(),
        route_id=route.id,
        weekday=0,
        start_time=time(6, 0),
        duration_minutes=120,
        effective_from=date(2026, 1, 1),
    )
    service = CitizenService(FakeETARepository(route, schedule))

    result = await service.estimate_arrival(
        latitude=4.5339,
        longitude=-75.6811,
        route_id=None,
        at=datetime.fromisoformat("2026-10-25T21:00:00-05:00"),
        radius_m=750,
    )

    assert result.scheduled_start.isoformat() == "2026-10-26T06:00:00-05:00"
    assert result.estimated_arrival.isoformat() == "2026-10-26T07:00:00-05:00"
    assert result.distance_to_route_m == 42.2
    assert result.source == "scheduled"
    assert result.is_live is False
