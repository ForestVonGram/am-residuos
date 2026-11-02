from datetime import date, datetime, timedelta
from uuid import UUID

from app.core.config import get_settings
from app.models.route import CollectionRoute, RouteSchedule
from app.repositories.citizen import CitizenRepository, LocatedRoute, PublicOperation
from app.schemas.citizen import (
    ETAResponse,
    PublicPersonnel,
    PublicTruck,
    RouteDetail,
    RouteSummary,
    ScheduleItem,
    VehiclePositionRead,
)
from app.services.eta import ensure_local_datetime, expected_arrival
from app.services.live_eta import calculate_live_eta


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
        operation_rows = [
            (schedule, route, query_date) for schedule, route in rows
        ]
        if hasattr(self.repository, "get_public_operations"):
            operations = await self.repository.get_public_operations(operation_rows)
        else:
            operations = {
                (route.id, schedule.id, query_date): await self.repository.get_public_operation(
                    route.id, schedule.id, query_date
                )
                for schedule, route in rows
            }
        items = []
        for schedule, route in rows:
            operation = operations[(route.id, schedule.id, query_date)]
            items.append(self._schedule_item(schedule, route, query_date, operation))
        return items

    def _schedule_item(
        self,
        schedule: RouteSchedule,
        route: CollectionRoute,
        service_date: date,
        operation: PublicOperation,
    ) -> ScheduleItem:
        start, end = expected_arrival(service_date, schedule, 1, self.timezone)
        delay = operation.adjustment.delay_minutes if operation.adjustment else 0
        estimated_start = start + timedelta(minutes=delay)
        estimated_end = end + timedelta(minutes=delay)
        truck, personnel = self._public_assignment(operation)
        return ScheduleItem(
            id=schedule.id,
            route_id=route.id,
            route_code=route.code,
            route_name=route.name,
            sector=route.sector,
            service_date=service_date,
            start_time=start.time().replace(tzinfo=None),
            estimated_start_time=estimated_start.time().replace(tzinfo=None),
            expected_end_time=estimated_end.time().replace(tzinfo=None),
            duration_minutes=schedule.duration_minutes,
            delay_minutes=delay,
            cancelled=operation.adjustment.cancelled if operation.adjustment else False,
            delay_reason=operation.adjustment.reason if operation.adjustment else None,
            truck=truck,
            personnel=personnel,
        )

    @staticmethod
    def _public_assignment(
        operation: PublicOperation,
    ) -> tuple[PublicTruck | None, list[PublicPersonnel]]:
        if not operation.assignment:
            return None, []
        assignment = operation.assignment
        truck = PublicTruck(plate=assignment.truck.plate, name=assignment.truck.name)
        personnel = [
            PublicPersonnel(name=f"{person.first_name} {person.last_name}", role=person.role)
            for person in assignment.personnel
            if person.active
        ]
        return truck, personnel

    async def estimate_arrival(
        self,
        latitude: float,
        longitude: float,
        route_id: UUID | None,
        at: datetime | None,
        radius_m: int,
    ) -> ETAResponse:
        requested_at = ensure_local_datetime(at, self.timezone)
        now = ensure_local_datetime(None, self.timezone)
        located = await self.repository.locate_routes(latitude, longitude, radius_m, route_id)
        if not located:
            raise RouteNotFoundError("No hay una ruta activa cercana al punto indicado")

        service_dates = [requested_at.date() + timedelta(days=offset) for offset in range(8)]
        if hasattr(self.repository, "list_schedules_for_dates"):
            schedule_rows = await self.repository.list_schedules_for_dates(
                service_dates, [item.route.id for item in located]
            )
        else:
            schedule_rows = []
            for service_date in service_dates:
                for candidate in located:
                    rows = await self.repository.list_schedules(
                        service_date, candidate.route.id
                    )
                    schedule_rows.extend(
                        (schedule, route, service_date) for schedule, route in rows
                    )
        if hasattr(self.repository, "get_public_operations"):
            operations = await self.repository.get_public_operations(schedule_rows)
        else:
            operations = {}
            for schedule, route, service_date in schedule_rows:
                operations[(route.id, schedule.id, service_date)] = (
                    await self.repository.get_public_operation(
                        route.id, schedule.id, service_date
                    )
                )

        best: tuple[
            datetime, datetime, LocatedRoute, PublicOperation, RouteSchedule, date
        ] | None = None
        cancelled: list[
            tuple[datetime, datetime, LocatedRoute, PublicOperation, RouteSchedule, date]
        ] = []
        candidates_by_route = {candidate.route.id: candidate for candidate in located}
        for schedule, route, service_date in schedule_rows:
            candidate = candidates_by_route[route.id]
            operation = operations[(route.id, schedule.id, service_date)]
            start, arrival = expected_arrival(
                service_date,
                schedule,
                candidate.progress_fraction,
                self.timezone,
            )
            delay = operation.adjustment.delay_minutes if operation.adjustment else 0
            start += timedelta(minutes=delay)
            arrival += timedelta(minutes=delay)
            row = (start, arrival, candidate, operation, schedule, service_date)
            if operation.adjustment and operation.adjustment.cancelled:
                if arrival >= requested_at:
                    cancelled.append(row)
                continue
            if arrival >= requested_at and (best is None or arrival < best[1]):
                best = row

        if best is None:
            if cancelled:
                start, arrival, candidate, operation, _, _ = min(
                    cancelled, key=lambda row: row[1]
                )
                truck, personnel = self._public_assignment(operation)
                return ETAResponse(
                    route=self._summary(candidate.route, candidate.distance_m),
                    requested_at=requested_at,
                    scheduled_start=start,
                    estimated_arrival=arrival,
                    distance_to_route_m=round(candidate.distance_m, 1),
                    progress_fraction=round(candidate.progress_fraction, 6),
                    delay_minutes=(
                        operation.adjustment.delay_minutes if operation.adjustment else 0
                    ),
                    truck=truck,
                    personnel=personnel,
                    status="cancelled",
                    message="La jornada programada para esta ruta fue cancelada.",
                )
            raise RouteNotFoundError("No hay jornadas programadas para los próximos siete días")

        start, arrival, candidate, operation, schedule, service_date = best
        truck, personnel = self._public_assignment(operation)
        values = dict(
            route=self._summary(candidate.route, candidate.distance_m),
            requested_at=requested_at,
            scheduled_start=start,
            estimated_arrival=arrival,
            distance_to_route_m=round(candidate.distance_m, 1),
            progress_fraction=round(candidate.progress_fraction, 6),
            delay_minutes=(operation.adjustment.delay_minutes if operation.adjustment else 0),
            truck=truck,
            personnel=personnel,
        )
        position_result = None
        if (
            service_date == now.date()
            and operation.assignment is not None
            and hasattr(self.repository, "get_tracking_positions")
            and now >= start
            and now <= start + timedelta(minutes=schedule.duration_minutes)
        ):
            truck_id = operation.assignment.truck_id
            tracks = await self.repository.get_tracking_positions(
                [truck_id], now - timedelta(minutes=3)
            )
            position_result = calculate_live_eta(
                candidate.route.geometry,
                candidate.progress_fraction,
                tracks.get(truck_id, []),
                schedule.duration_minutes,
                now,
            )

        if position_result and not position_result.stale and position_result.eta:
            values.update(
                estimated_arrival=position_result.eta,
                source="live",
                is_live=True,
                vehicle_position=VehiclePositionRead(
                    latitude=position_result.position.latitude,
                    longitude=position_result.position.longitude,
                    speed_kmh=position_result.position.speed_kmh,
                    heading=position_result.position.heading,
                    recorded_at=position_result.position.recorded_at,
                    stale=False,
                ),
                distance_remaining_m=round(position_result.distance_remaining_m or 0, 1),
                minutes_remaining=round(position_result.minutes_remaining or 0, 1),
                status=position_result.status,
                confidence=position_result.confidence,
                simulated=True,
                message=position_result.message,
            )
        else:
            values.update(
                status="not_started" if now < start else "scheduled",
                message=(
                    position_result.message
                    if position_result and position_result.stale
                    else "Estimación basada en el horario y la duración programada."
                ),
            )
            if position_result:
                values.update(
                    vehicle_position=VehiclePositionRead(
                        latitude=position_result.position.latitude,
                        longitude=position_result.position.longitude,
                        speed_kmh=position_result.position.speed_kmh,
                        heading=position_result.position.heading,
                        recorded_at=position_result.position.recorded_at,
                        stale=position_result.stale,
                    ),
                    simulated=True,
                )
        return ETAResponse(**values)
