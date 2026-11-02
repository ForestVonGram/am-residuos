from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gps import VehiclePosition
from app.models.operational import RouteAssignment, ServiceAdjustment
from app.models.route import CollectionRoute, RouteSchedule
from app.services.geo import distance_and_fraction, haversine_m


@dataclass(frozen=True)
class LocatedRoute:
    route: CollectionRoute
    distance_m: float
    progress_fraction: float


@dataclass(frozen=True)
class PublicOperation:
    assignment: RouteAssignment | None
    adjustment: ServiceAdjustment | None


OperationKey = tuple[UUID, UUID, date]


class CitizenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _distance_and_fraction(
        geometry: dict, latitude: float, longitude: float
    ) -> tuple[float, float]:
        return distance_and_fraction(geometry, latitude, longitude)

    @staticmethod
    def _haversine(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
        return haversine_m(lat_a, lon_a, lat_b, lon_b)

    async def list_routes(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_m: int = 750,
    ) -> list[tuple[CollectionRoute, float | None]]:
        query = select(CollectionRoute).where(CollectionRoute.active.is_(True))
        routes = list((await self.session.scalars(query)).all())
        if latitude is None or longitude is None:
            return [(route, None) for route in sorted(routes, key=lambda item: item.name)]
        located = []
        for route in routes:
            distance, _ = self._distance_and_fraction(route.geometry, latitude, longitude)
            if distance <= radius_m:
                located.append((route, distance))
        return sorted(located, key=lambda item: (item[1], item[0].name))

    async def get_route(self, route_id: UUID) -> tuple[CollectionRoute, dict] | None:
        query = select(CollectionRoute).where(
            CollectionRoute.id == route_id, CollectionRoute.active.is_(True)
        )
        route = (await self.session.scalars(query)).one_or_none()
        return (route, route.geometry) if route else None

    async def list_schedules(
        self, service_date: date, route_id: UUID | None = None
    ) -> list[tuple[RouteSchedule, CollectionRoute]]:
        query = (
            select(RouteSchedule, CollectionRoute)
            .join(CollectionRoute)
            .where(
                RouteSchedule.active.is_(True),
                CollectionRoute.active.is_(True),
                RouteSchedule.weekday == service_date.weekday(),
                RouteSchedule.effective_from <= service_date,
                or_(
                    RouteSchedule.effective_to.is_(None),
                    RouteSchedule.effective_to >= service_date,
                ),
            )
            .order_by(RouteSchedule.start_time, CollectionRoute.name)
        )
        if route_id:
            query = query.where(CollectionRoute.id == route_id)
        return list((await self.session.execute(query)).all())

    async def list_schedules_for_dates(
        self, service_dates: list[date], route_ids: list[UUID]
    ) -> list[tuple[RouteSchedule, CollectionRoute, date]]:
        if not service_dates or not route_ids:
            return []
        first_date, last_date = min(service_dates), max(service_dates)
        query = (
            select(RouteSchedule, CollectionRoute)
            .join(CollectionRoute)
            .where(
                RouteSchedule.active.is_(True),
                CollectionRoute.active.is_(True),
                CollectionRoute.id.in_(route_ids),
                RouteSchedule.weekday.in_([item.weekday() for item in service_dates]),
                RouteSchedule.effective_from <= last_date,
                or_(
                    RouteSchedule.effective_to.is_(None),
                    RouteSchedule.effective_to >= first_date,
                ),
            )
            .order_by(RouteSchedule.start_time, CollectionRoute.name)
        )
        schedules = list((await self.session.execute(query)).all())
        return [
            (schedule, route, service_date)
            for schedule, route in schedules
            for service_date in service_dates
            if service_date.weekday() == schedule.weekday
            and schedule.effective_from <= service_date
            and (schedule.effective_to is None or schedule.effective_to >= service_date)
        ]

    async def locate_routes(
        self,
        latitude: float,
        longitude: float,
        radius_m: int,
        route_id: UUID | None,
    ) -> list[LocatedRoute]:
        query = select(CollectionRoute).where(CollectionRoute.active.is_(True))
        if route_id:
            query = query.where(CollectionRoute.id == route_id)
        routes = list((await self.session.scalars(query)).all())
        located = []
        for route in routes:
            distance, fraction = self._distance_and_fraction(
                route.geometry, latitude, longitude
            )
            if distance <= radius_m:
                located.append(LocatedRoute(route, distance, fraction))
        return sorted(located, key=lambda item: item.distance_m)

    async def get_public_operation(
        self, route_id: UUID, schedule_id: UUID, service_date: date
    ) -> PublicOperation:
        assignment_query = (
            select(RouteAssignment)
            .options(
                selectinload(RouteAssignment.truck),
                selectinload(RouteAssignment.personnel),
            )
            .where(
                RouteAssignment.route_id == route_id,
                RouteAssignment.active.is_(True),
                RouteAssignment.effective_from <= service_date,
                or_(
                    RouteAssignment.effective_to.is_(None),
                    RouteAssignment.effective_to >= service_date,
                ),
            )
            .order_by(RouteAssignment.effective_from.desc())
            .limit(1)
        )
        adjustment_query = select(ServiceAdjustment).where(
            ServiceAdjustment.schedule_id == schedule_id,
            ServiceAdjustment.service_date == service_date,
        )
        assignment = (await self.session.scalars(assignment_query)).one_or_none()
        adjustment = (await self.session.scalars(adjustment_query)).one_or_none()
        return PublicOperation(assignment=assignment, adjustment=adjustment)

    async def get_public_operations(
        self,
        schedule_rows: list[tuple[RouteSchedule, CollectionRoute, date]],
    ) -> dict[OperationKey, PublicOperation]:
        if not schedule_rows:
            return {}
        route_ids = list({route.id for _, route, _ in schedule_rows})
        schedule_ids = list({schedule.id for schedule, _, _ in schedule_rows})
        service_dates = list({service_date for _, _, service_date in schedule_rows})
        assignments_query = (
            select(RouteAssignment)
            .options(
                selectinload(RouteAssignment.truck),
                selectinload(RouteAssignment.personnel),
            )
            .where(
                RouteAssignment.route_id.in_(route_ids),
                RouteAssignment.active.is_(True),
                RouteAssignment.effective_from <= max(service_dates),
                or_(
                    RouteAssignment.effective_to.is_(None),
                    RouteAssignment.effective_to >= min(service_dates),
                ),
            )
            .order_by(RouteAssignment.effective_from.desc())
        )
        assignments = list((await self.session.scalars(assignments_query)).all())
        adjustments_query = select(ServiceAdjustment).where(
            ServiceAdjustment.schedule_id.in_(schedule_ids),
            ServiceAdjustment.service_date.in_(service_dates),
        )
        adjustments = list((await self.session.scalars(adjustments_query)).all())
        result = {}
        for schedule, route, service_date in schedule_rows:
            assignment = next(
                (
                    row
                    for row in assignments
                    if row.route_id == route.id
                    and row.effective_from <= service_date
                    and (row.effective_to is None or row.effective_to >= service_date)
                ),
                None,
            )
            adjustment = next(
                (
                    row
                    for row in adjustments
                    if row.schedule_id == schedule.id and row.service_date == service_date
                ),
                None,
            )
            result[(route.id, schedule.id, service_date)] = PublicOperation(
                assignment=assignment, adjustment=adjustment
            )
        return result

    async def get_tracking_positions(
        self, truck_ids: list[UUID], since: datetime
    ) -> dict[UUID, list[VehiclePosition]]:
        if not truck_ids:
            return {}
        recent_query = (
            select(VehiclePosition)
            .where(
                VehiclePosition.truck_id.in_(truck_ids),
                VehiclePosition.recorded_at >= since,
            )
            .order_by(VehiclePosition.truck_id, VehiclePosition.recorded_at)
        )
        latest_query = (
            select(VehiclePosition)
            .where(VehiclePosition.truck_id.in_(truck_ids))
            .distinct(VehiclePosition.truck_id)
            .order_by(VehiclePosition.truck_id, VehiclePosition.recorded_at.desc())
        )
        recent = list((await self.session.scalars(recent_query)).all())
        latest = list((await self.session.scalars(latest_query)).all())
        positions: dict[UUID, list[VehiclePosition]] = {}
        for position in recent:
            positions.setdefault(position.truck_id, []).append(position)
        for position in latest:
            track = positions.setdefault(position.truck_id, [])
            if all(item.id != position.id for item in track):
                track.insert(0, position)
        return positions
