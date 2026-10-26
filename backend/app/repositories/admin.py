from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.operational import Personnel, RouteAssignment, ServiceAdjustment, Truck
from app.models.route import CollectionRoute, RouteSchedule


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, entity):
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def list_personnel(self, include_inactive: bool) -> list[Personnel]:
        query = select(Personnel).order_by(Personnel.first_name, Personnel.last_name)
        if not include_inactive:
            query = query.where(Personnel.active.is_(True))
        return list((await self.session.scalars(query)).all())

    async def get_personnel(self, personnel_id: UUID) -> Personnel | None:
        return await self.session.get(Personnel, personnel_id)

    async def get_personnel_many(self, ids: list[UUID]) -> list[Personnel]:
        query = select(Personnel).where(Personnel.id.in_(ids), Personnel.active.is_(True))
        return list((await self.session.scalars(query)).all())

    async def list_trucks(self, include_inactive: bool) -> list[Truck]:
        query = select(Truck).order_by(Truck.plate)
        if not include_inactive:
            query = query.where(Truck.active.is_(True))
        return list((await self.session.scalars(query)).all())

    async def get_truck(self, truck_id: UUID) -> Truck | None:
        return await self.session.get(Truck, truck_id)

    async def get_route(self, route_id: UUID) -> CollectionRoute | None:
        return await self.session.get(CollectionRoute, route_id)

    async def list_schedules(self, route_id: UUID | None) -> list[RouteSchedule]:
        query = select(RouteSchedule).order_by(RouteSchedule.weekday, RouteSchedule.start_time)
        if route_id:
            query = query.where(RouteSchedule.route_id == route_id)
        return list((await self.session.scalars(query)).all())

    async def get_schedule(self, schedule_id: UUID) -> RouteSchedule | None:
        return await self.session.get(RouteSchedule, schedule_id)

    async def list_assignments(self, route_id: UUID | None) -> list[RouteAssignment]:
        query = (
            select(RouteAssignment)
            .options(
                selectinload(RouteAssignment.truck),
                selectinload(RouteAssignment.personnel),
            )
            .order_by(RouteAssignment.effective_from.desc())
        )
        if route_id:
            query = query.where(RouteAssignment.route_id == route_id)
        return list((await self.session.scalars(query)).all())

    async def get_assignment(self, assignment_id: UUID) -> RouteAssignment | None:
        query = (
            select(RouteAssignment)
            .options(
                selectinload(RouteAssignment.truck),
                selectinload(RouteAssignment.personnel),
            )
            .where(RouteAssignment.id == assignment_id)
        )
        return (await self.session.scalars(query)).one_or_none()

    async def assignment_overlaps(
        self,
        route_id: UUID,
        truck_id: UUID,
        effective_from: date,
        effective_to: date | None,
        exclude_id: UUID | None = None,
    ) -> bool:
        requested_end = effective_to or date.max
        query = select(RouteAssignment.id).where(
            RouteAssignment.active.is_(True),
            or_(RouteAssignment.route_id == route_id, RouteAssignment.truck_id == truck_id),
            RouteAssignment.effective_from <= requested_end,
            or_(
                RouteAssignment.effective_to.is_(None),
                RouteAssignment.effective_to >= effective_from,
            ),
        )
        if exclude_id:
            query = query.where(RouteAssignment.id != exclude_id)
        return (await self.session.scalar(query.limit(1))) is not None

    async def get_adjustment(
        self, schedule_id: UUID, service_date: date
    ) -> ServiceAdjustment | None:
        query = select(ServiceAdjustment).where(
            ServiceAdjustment.schedule_id == schedule_id,
            ServiceAdjustment.service_date == service_date,
        )
        return (await self.session.scalars(query)).one_or_none()

    async def list_adjustments(self, service_date: date | None) -> list[ServiceAdjustment]:
        query = select(ServiceAdjustment).order_by(ServiceAdjustment.service_date.desc())
        if service_date:
            query = query.where(ServiceAdjustment.service_date == service_date)
        return list((await self.session.scalars(query)).all())

    async def delete_adjustment(self, adjustment: ServiceAdjustment) -> None:
        await self.session.delete(adjustment)
        await self.session.commit()
