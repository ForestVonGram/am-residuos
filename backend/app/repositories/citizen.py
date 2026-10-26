from dataclasses import dataclass
from datetime import date
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.operational import RouteAssignment, ServiceAdjustment
from app.models.route import CollectionRoute, RouteSchedule


@dataclass(frozen=True)
class LocatedRoute:
    route: CollectionRoute
    distance_m: float
    progress_fraction: float


@dataclass(frozen=True)
class PublicOperation:
    assignment: RouteAssignment | None
    adjustment: ServiceAdjustment | None


class CitizenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _distance_and_fraction(
        geometry: dict, latitude: float, longitude: float
    ) -> tuple[float, float]:
        """Return distance in metres and progress along a GeoJSON LineString.

        The local equirectangular projection is accurate enough for municipal
        routes and keeps PostgreSQL free of geospatial extensions.
        """
        coordinates = geometry.get("coordinates", [])
        if not coordinates:
            return float("inf"), 0.0
        if len(coordinates) == 1:
            point_lon, point_lat = coordinates[0]
            return CitizenRepository._haversine(latitude, longitude, point_lat, point_lon), 0.0

        earth_radius = 6_371_008.8
        reference_lat = radians(latitude)

        def project(lon: float, lat: float) -> tuple[float, float]:
            return (
                earth_radius * radians(lon - longitude) * cos(reference_lat),
                earth_radius * radians(lat - latitude),
            )

        projected = [project(float(lon), float(lat)) for lon, lat in coordinates]
        lengths = [
            sqrt((bx - ax) ** 2 + (by - ay) ** 2)
            for (ax, ay), (bx, by) in zip(projected, projected[1:], strict=False)
        ]
        total_length = sum(lengths)
        best_distance = float("inf")
        best_progress = 0.0
        traversed = 0.0
        for (ax, ay), (bx, by), segment_length in zip(
            projected, projected[1:], lengths, strict=False
        ):
            dx, dy = bx - ax, by - ay
            denominator = dx * dx + dy * dy
            fraction = (
                0.0
                if denominator == 0
                else max(0.0, min(1.0, -(ax * dx + ay * dy) / denominator))
            )
            nearest_x, nearest_y = ax + fraction * dx, ay + fraction * dy
            distance = sqrt(nearest_x * nearest_x + nearest_y * nearest_y)
            if distance < best_distance:
                best_distance = distance
                best_progress = (
                    (traversed + fraction * segment_length) / total_length
                    if total_length
                    else 0.0
                )
            traversed += segment_length
        return best_distance, best_progress

    @staticmethod
    def _haversine(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
        earth_radius = 6_371_008.8
        delta_lat = radians(lat_b - lat_a)
        delta_lon = radians(lon_b - lon_a)
        value = sin(delta_lat / 2) ** 2 + (
            cos(radians(lat_a)) * cos(radians(lat_b)) * sin(delta_lon / 2) ** 2
        )
        return 2 * earth_radius * asin(sqrt(value))

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
