from datetime import date, datetime, timedelta
from uuid import UUID

from app.core.config import get_settings
from app.models.route import CollectionRoute, RouteSchedule
from app.repositories.citizen import CitizenRepository, LocatedRoute
from app.schemas.citizen import ETAResponse, RouteDetail, RouteSummary, ScheduleItem
from app.services.eta import ensure_local_datetime, expected_arrival


class RouteNotFoundError(LookupError):
    pass


class CitizenService:
    def __init__(self, repository: CitizenRepository) -> None:
        self.repository = repository
        self.timezone = get_settings().timezone

    @staticmethod
    def _summary(route: CollectionRoute, distance_m: float | None = None) -> RouteSummary:
        return RouteSummary(
            id=route.id,
            code=route.code,
            name=route.name,
            description=route.description,
            sector=route.sector,
            distance_m=round(distance_m, 1) if distance_m is not None else None,
        )

    async def list_routes(
        self, latitude: float | None, longitude: float | None, radius_m: int
    ) -> list[RouteSummary]:
        rows = await self.repository.list_routes(latitude, longitude, radius_m)
        return [self._summary(route, distance) for route, distance in rows]

    async def get_route(self, route_id: UUID) -> RouteDetail:
        row = await self.repository.get_route(route_id)
        if row is None:
            raise RouteNotFoundError("Ruta activa no encontrada")
        route, geometry = row
        return RouteDetail(**self._summary(route).model_dump(), geometry=geometry)

    async def list_schedules(
        self, service_date: date | None, route_id: UUID | None
    ) -> list[ScheduleItem]:
        query_date = service_date or ensure_local_datetime(None, self.timezone).date()
        rows = await self.repository.list_schedules(query_date, route_id)
        return [self._schedule_item(schedule, route, query_date) for schedule, route in rows]

    def _schedule_item(
        self, schedule: RouteSchedule, route: CollectionRoute, service_date: date
    ) -> ScheduleItem:
        start, end = expected_arrival(service_date, schedule, 1, self.timezone)
        return ScheduleItem(
            id=schedule.id,
            route_id=route.id,
            route_code=route.code,
            route_name=route.name,
            sector=route.sector,
            service_date=service_date,
            start_time=start.time().replace(tzinfo=None),
            expected_end_time=end.time().replace(tzinfo=None),
            duration_minutes=schedule.duration_minutes,
        )

    async def estimate_arrival(
        self,
        latitude: float,
        longitude: float,
        route_id: UUID | None,
        at: datetime | None,
        radius_m: int,
    ) -> ETAResponse:
        requested_at = ensure_local_datetime(at, self.timezone)
        located = await self.repository.locate_routes(latitude, longitude, radius_m, route_id)
        if not located:
            raise RouteNotFoundError("No hay una ruta activa cercana al punto indicado")

        best: tuple[datetime, datetime, LocatedRoute] | None = None
        for day_offset in range(8):
            service_date = requested_at.date() + timedelta(days=day_offset)
            for candidate in located:
                schedules = await self.repository.list_schedules(service_date, candidate.route.id)
                for schedule, _ in schedules:
                    start, arrival = expected_arrival(
                        service_date,
                        schedule,
                        candidate.progress_fraction,
                        self.timezone,
                    )
                    if arrival >= requested_at and (best is None or arrival < best[1]):
                        best = (start, arrival, candidate)
            if best is not None:
                break

        if best is None:
            raise RouteNotFoundError("No hay jornadas programadas para los proximos siete dias")

        start, arrival, candidate = best
        return ETAResponse(
            route=self._summary(candidate.route, candidate.distance_m),
            requested_at=requested_at,
            scheduled_start=start,
            estimated_arrival=arrival,
            distance_to_route_m=round(candidate.distance_m, 1),
            progress_fraction=round(candidate.progress_fraction, 6),
        )
