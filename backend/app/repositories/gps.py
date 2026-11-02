from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gps import GPSDevice, VehiclePosition
from app.models.operational import RouteAssignment, ServiceAdjustment, Truck
from app.models.route import CollectionRoute, RouteSchedule


class GPSRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_device_by_hash(self, token_hash: str) -> GPSDevice | None:
        return await self.session.scalar(
            select(GPSDevice).where(GPSDevice.api_token_hash == token_hash)
        )

    async def insert_position(self, device: GPSDevice, values: dict) -> bool:
        statement = (
            insert(VehiclePosition)
            .values(device_id=device.id, truck_id=device.truck_id, **values)
            .on_conflict_do_nothing(constraint="uq_vehicle_positions_device_recorded_at")
            .returning(VehiclePosition.id)
        )
        return (await self.session.scalar(statement)) is not None

    async def touch_device(self, device: GPSDevice, seen_at: datetime) -> None:
        device.last_seen_at = seen_at
        await self.session.commit()

    async def list_devices(self) -> list[tuple[GPSDevice, Truck]]:
        result = await self.session.execute(
            select(GPSDevice, Truck).join(Truck).order_by(GPSDevice.device_code)
        )
        return list(result.all())

    async def get_device(self, device_id: UUID) -> GPSDevice | None:
        return await self.session.get(GPSDevice, device_id)

    async def get_truck(self, truck_id: UUID) -> Truck | None:
        return await self.session.get(Truck, truck_id)

    async def save(self, device: GPSDevice) -> GPSDevice:
        self.session.add(device)
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def rollback(self) -> None:
        await self.session.rollback()

    async def active_operations(
        self, service_date: date, weekday: int, current_time: time
    ) -> list[tuple[RouteSchedule, CollectionRoute, RouteAssignment, Truck]]:
        result = await self.session.execute(
            select(RouteSchedule, CollectionRoute, RouteAssignment, Truck)
            .join(CollectionRoute, RouteSchedule.route_id == CollectionRoute.id)
            .join(RouteAssignment, RouteAssignment.route_id == CollectionRoute.id)
            .join(Truck, Truck.id == RouteAssignment.truck_id)
            .where(
                RouteSchedule.active.is_(True),
                CollectionRoute.active.is_(True),
                RouteAssignment.active.is_(True),
                Truck.active.is_(True),
                RouteSchedule.weekday == weekday,
                RouteSchedule.effective_from <= service_date,
                (RouteSchedule.effective_to.is_(None))
                | (RouteSchedule.effective_to >= service_date),
                RouteAssignment.effective_from <= service_date,
                (RouteAssignment.effective_to.is_(None))
                | (RouteAssignment.effective_to >= service_date),
            )
        )
        active = []
        for schedule, route, assignment, truck in result.all():
            end_minutes = (
                schedule.start_time.hour * 60
                + schedule.start_time.minute
                + schedule.duration_minutes
            )
            now_minutes = current_time.hour * 60 + current_time.minute
            start_minutes = schedule.start_time.hour * 60 + schedule.start_time.minute
            if start_minutes <= now_minutes <= end_minutes:
                active.append((schedule, route, assignment, truck))
        return active

    async def cancelled_schedule_ids(
        self, schedule_ids: list[UUID], service_date: date
    ) -> set[UUID]:
        if not schedule_ids:
            return set()
        rows = await self.session.execute(
            select(ServiceAdjustment.schedule_id).where(
                ServiceAdjustment.schedule_id.in_(schedule_ids),
                ServiceAdjustment.service_date == service_date,
                ServiceAdjustment.cancelled.is_(True),
            )
        )
        return set(rows.scalars().all())

    async def latest_positions(
        self, truck_ids: list[UUID]
    ) -> dict[UUID, VehiclePosition]:
        if not truck_ids:
            return {}
        statement = (
            select(VehiclePosition)
            .where(VehiclePosition.truck_id.in_(truck_ids))
            .distinct(VehiclePosition.truck_id)
            .order_by(VehiclePosition.truck_id, VehiclePosition.recorded_at.desc())
        )
        rows = (await self.session.scalars(statement)).all()
        return {position.truck_id: position for position in rows}

