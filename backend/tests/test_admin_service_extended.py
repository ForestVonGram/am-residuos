from datetime import date, time
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.operational import Personnel, RouteAssignment, ServiceAdjustment, Truck
from app.models.route import CollectionRoute, RouteSchedule
from app.schemas.admin import (
    AssignmentUpdate,
    PersonnelCreate,
    PersonnelUpdate,
    ScheduleCreate,
    ScheduleUpdate,
    ServiceAdjustmentWrite,
    TruckCreate,
    TruckUpdate,
)
from app.services.admin import AdminService, InvalidOperation, ResourceConflict, ResourceNotFound

SERVICE_DATE = date(2026, 10, 26)


class FakeAdminRepository:
    def __init__(self) -> None:
        self.route = CollectionRoute(
            id=uuid4(),
            code="AXM-01",
            name="Centro",
            sector="Centro",
            geometry={"type": "LineString", "coordinates": [[-75.69, 4.53]]},
            active=True,
        )
        self.driver = Personnel(
            id=uuid4(), first_name="Ana", last_name="Pérez", role="driver", active=True
        )
        self.truck = Truck(
            id=uuid4(), plate="ABC-123", name="Camión 1", status="available", active=True
        )
        self.schedule = RouteSchedule(
            id=uuid4(),
            route_id=self.route.id,
            weekday=SERVICE_DATE.weekday(),
            start_time=time(6),
            duration_minutes=120,
            effective_from=SERVICE_DATE,
            effective_to=SERVICE_DATE,
            active=True,
        )
        self.assignment = RouteAssignment(
            id=uuid4(),
            route_id=self.route.id,
            truck_id=self.truck.id,
            truck=self.truck,
            personnel=[self.driver],
            effective_from=SERVICE_DATE,
            effective_to=SERVICE_DATE,
            active=True,
        )
        self.people = [self.driver]
        self.trucks = [self.truck]
        self.schedules = [self.schedule]
        self.adjustment = None
        self.fail_save = False
        self.overlap = False

    async def save(self, entity):
        if self.fail_save:
            raise IntegrityError("insert", {}, RuntimeError("duplicate"))
        if getattr(entity, "id", None) is None:
            entity.id = uuid4()
        if isinstance(entity, Personnel) and entity not in self.people:
            self.people.append(entity)
        if isinstance(entity, Truck) and entity not in self.trucks:
            self.trucks.append(entity)
        if isinstance(entity, RouteSchedule) and entity not in self.schedules:
            self.schedules.append(entity)
        if isinstance(entity, RouteAssignment):
            self.assignment = entity
        if isinstance(entity, ServiceAdjustment):
            self.adjustment = entity
        return entity

    async def rollback(self):
        return None

    async def list_personnel(self, include_inactive):
        return self.people

    async def get_personnel(self, entity_id):
        return next((item for item in self.people if item.id == entity_id), None)

    async def list_trucks(self, include_inactive):
        return self.trucks

    async def get_truck(self, entity_id):
        return self.truck if entity_id == self.truck.id else None

    async def get_route(self, entity_id):
        return self.route if entity_id == self.route.id else None

    async def list_schedules(self, route_id):
        return [self.schedule]

    async def get_schedule(self, entity_id):
        return next((item for item in self.schedules if item.id == entity_id), None)

    async def get_personnel_many(self, ids):
        return [person for person in self.people if person.id in ids and person.active]

    async def assignment_overlaps(self, *args, **kwargs):
        return self.overlap

    async def list_assignments(self, route_id):
        return [self.assignment]

    async def get_assignment(self, entity_id):
        return self.assignment if entity_id == self.assignment.id else None

    async def get_adjustment(self, schedule_id, service_date):
        if (
            self.adjustment
            and self.adjustment.schedule_id == schedule_id
            and self.adjustment.service_date == service_date
        ):
            return self.adjustment
        return None

    async def list_adjustments(self, service_date):
        return [self.adjustment] if self.adjustment else []

    async def delete_adjustment(self, adjustment):
        self.adjustment = None


@pytest.mark.asyncio
async def test_personnel_and_truck_crud_and_conflict_translation() -> None:
    repository = FakeAdminRepository()
    service = AdminService(repository)
    created = await service.create_personnel(
        PersonnelCreate(first_name="Luis", last_name="Rojas", role="collector")
    )
    updated = await service.update_personnel(created.id, PersonnelUpdate(active=False))
    assert updated.active is False
    await service.deactivate_personnel(repository.driver.id)
    assert repository.driver.active is False

    with pytest.raises(ResourceNotFound):
        await service.update_personnel(uuid4(), PersonnelUpdate(active=False))

    truck = await service.create_truck(TruckCreate(plate="XYZ-999", name="Camión 2"))
    assert truck.plate == "XYZ-999"
    await service.update_truck(repository.truck.id, TruckUpdate(active=False))
    await service.deactivate_truck(repository.truck.id)
    with pytest.raises(ResourceNotFound):
        await service.update_truck(uuid4(), TruckUpdate(active=False))

    repository.fail_save = True
    with pytest.raises(ResourceConflict):
        await service.create_personnel(
            PersonnelCreate(first_name="Ana", last_name="Rojas", role="collector")
        )


@pytest.mark.asyncio
async def test_schedule_crud_validates_route_and_date_range() -> None:
    repository = FakeAdminRepository()
    service = AdminService(repository)
    created = await service.create_schedule(
        ScheduleCreate(
            route_id=repository.route.id,
            weekday=0,
            start_time=time(7),
            duration_minutes=90,
            effective_from=SERVICE_DATE,
        )
    )
    assert created.start_time == time(7)
    await service.update_schedule(created.id, ScheduleUpdate(active=False))
    await service.deactivate_schedule(repository.schedule.id)

    with pytest.raises(ResourceNotFound):
        await service.create_schedule(
            ScheduleCreate(
                route_id=uuid4(),
                weekday=0,
                start_time=time(7),
                duration_minutes=90,
                effective_from=SERVICE_DATE,
            )
        )
    with pytest.raises(InvalidOperation):
        await service.update_schedule(
            repository.schedule.id,
            ScheduleUpdate(effective_from=date(2026, 10, 27), effective_to=SERVICE_DATE),
        )


@pytest.mark.asyncio
async def test_assignment_update_validates_overlap_and_deactivation() -> None:
    repository = FakeAdminRepository()
    service = AdminService(repository)
    updated = await service.update_assignment(
        repository.assignment.id,
        AssignmentUpdate(effective_from=SERVICE_DATE, active=True),
    )
    assert updated.active is True
    await service.deactivate_assignment(repository.assignment.id)
    assert repository.assignment.active is False

    repository.overlap = True
    with pytest.raises(ResourceConflict):
        await service.update_assignment(
            repository.assignment.id,
            AssignmentUpdate(truck_id=repository.truck.id),
        )
    with pytest.raises(ResourceNotFound):
        await service.deactivate_assignment(uuid4())


@pytest.mark.asyncio
async def test_adjustment_upsert_validation_and_delete() -> None:
    repository = FakeAdminRepository()
    service = AdminService(repository)
    write = ServiceAdjustmentWrite(
        schedule_id=repository.schedule.id,
        service_date=SERVICE_DATE,
        delay_minutes=10,
        reason="Tráfico",
    )
    created = await service.set_adjustment(write)
    assert created.delay_minutes == 10
    updated = await service.set_adjustment(
        ServiceAdjustmentWrite(
            schedule_id=repository.schedule.id,
            service_date=SERVICE_DATE,
            delay_minutes=20,
            cancelled=True,
        )
    )
    assert updated.cancelled is True

    with pytest.raises(InvalidOperation):
        await service.set_adjustment(
            ServiceAdjustmentWrite(
                schedule_id=repository.schedule.id,
                service_date=date(2026, 10, 27),
            )
        )
    await service.delete_adjustment(repository.schedule.id, SERVICE_DATE)
    with pytest.raises(ResourceNotFound):
        await service.delete_adjustment(repository.schedule.id, SERVICE_DATE)
