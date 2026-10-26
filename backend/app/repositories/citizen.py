from dataclasses import dataclass
from datetime import date
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.route import CollectionRoute, RouteSchedule


@dataclass(frozen=True)
class LocatedRoute:
    route: CollectionRoute
    distance_m: float
    progress_fraction: float


class CitizenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _point(latitude: float, longitude: float):
        return func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)

    async def list_routes(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_m: int = 750,
    ) -> list[tuple[CollectionRoute, float | None]]:
        if latitude is not None and longitude is not None:
            point = self._point(latitude, longitude)
            distance = func.ST_Distance(
                cast(CollectionRoute.geometry, Geography(geometry_type="LINESTRING", srid=4326)),
                cast(point, Geography(geometry_type="POINT", srid=4326)),
            )
            query = (
                select(CollectionRoute, distance.label("distance_m"))
                .where(CollectionRoute.active.is_(True), distance <= radius_m)
                .order_by(distance, CollectionRoute.name)
            )
        else:
            query = (
                select(CollectionRoute, func.nullif(0, 0))
                .where(CollectionRoute.active.is_(True))
                .order_by(CollectionRoute.name)
            )
        rows = (await self.session.execute(query)).all()
        return [(row[0], float(row[1]) if row[1] is not None else None) for row in rows]

    async def get_route(self, route_id: UUID) -> tuple[CollectionRoute, dict] | None:
        query = select(
            CollectionRoute,
            cast(func.ST_AsGeoJSON(CollectionRoute.geometry), JSONB).label("geometry"),
        ).where(CollectionRoute.id == route_id, CollectionRoute.active.is_(True))
        row = (await self.session.execute(query)).one_or_none()
        return (row[0], row[1]) if row else None

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
        point = self._point(latitude, longitude)
        route_geography = cast(
            CollectionRoute.geometry, Geography(geometry_type="LINESTRING", srid=4326)
        )
        point_geography = cast(point, Geography(geometry_type="POINT", srid=4326))
        distance = func.ST_Distance(route_geography, point_geography)
        fraction = func.ST_LineLocatePoint(CollectionRoute.geometry, point)
        query = (
            select(CollectionRoute, distance.label("distance_m"), fraction.label("fraction"))
            .where(CollectionRoute.active.is_(True), distance <= radius_m)
            .order_by(distance)
        )
        if route_id:
            query = query.where(CollectionRoute.id == route_id)
        rows = (await self.session.execute(query)).all()
        return [LocatedRoute(row[0], float(row[1]), float(row[2])) for row in rows]
