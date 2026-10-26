from datetime import date
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.operational import Personnel, RouteAssignment, ServiceAdjustment, Truck
from app.models.route import RouteSchedule
from app.repositories.admin import AdminRepository
from app.schemas.admin import (
    AssignmentCreate,
    AssignmentUpdate,
    PersonnelCreate,
    PersonnelUpdate,
    ScheduleCreate,
    ScheduleUpdate,
    ServiceAdjustmentWrite,
    TruckCreate,
    TruckUpdate,
)


class AdminError(Exception):
    status_code = 400


class ResourceNotFound(AdminError):
    status_code = 404


class ResourceConflict(AdminError):
    status_code = 409


class InvalidOperation(AdminError):
    status_code = 422


class AdminService:
    def __init__(self, repository: AdminRepository) -> None:
        self.repository = repository

    async def _save(self, entity):
        try:
            return await self.repository.save(entity)
        except IntegrityError as error:
            await self.repository.rollback()
            raise ResourceConflict("Ya existe un registro con esos datos unicos") from error

    async def list_personnel(self, include_inactive: bool) -> list[Personnel]:
        return await self.repository.list_personnel(include_inactive)

    async def create_personnel(self, data: PersonnelCreate) -> Personnel:
        return await self._save(Personnel(**data.model_dump()))

    async def update_personnel(self, personnel_id: UUID, data: PersonnelUpdate) -> Personnel:
        person = await self.repository.get_personnel(personnel_id)
        if not person:
            raise ResourceNotFound("Personal no encontrado")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(person, field, value)
        return await self._save(person)

    async def deactivate_personnel(self, personnel_id: UUID) -> None:
        await self.update_personnel(personnel_id, PersonnelUpdate(active=False))

    async def list_trucks(self, include_inactive: bool) -> list[Truck]:
        return await self.repository.list_trucks(include_inactive)

    async def create_truck(self, data: TruckCreate) -> Truck:
        return await self._save(Truck(**data.model_dump()))

    async def update_truck(self, truck_id: UUID, data: TruckUpdate) -> Truck:
        truck = await self.repository.get_truck(truck_id)
        if not truck:
            raise ResourceNotFound("Camion no encontrado")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(truck, field, value)
        return await self._save(truck)

    async def deactivate_truck(self, truck_id: UUID) -> None:
        await self.update_truck(truck_id, TruckUpdate(active=False))

    async def list_schedules(self, route_id: UUID | None) -> list[RouteSchedule]:
        return await self.repository.list_schedules(route_id)

    async def create_schedule(self, data: ScheduleCreate) -> RouteSchedule:
        route = await self.repository.get_route(data.route_id)
        if not route or not route.active:
            raise ResourceNotFound("Ruta activa no encontrada")
        return await self._save(RouteSchedule(**data.model_dump()))

    async def update_schedule(self, schedule_id: UUID, data: ScheduleUpdate) -> RouteSchedule:
        schedule = await self.repository.get_schedule(schedule_id)
        if not schedule:
            raise ResourceNotFound("Horario no encontrado")
        values = data.model_dump(exclude_unset=True)
        effective_from = values.get("effective_from", schedule.effective_from)
        effective_to = values.get("effective_to", schedule.effective_to)
        if effective_to and effective_to < effective_from:
            raise InvalidOperation("effective_to no puede ser anterior a effective_from")
        for field, value in values.items():
            setattr(schedule, field, value)
        return await self._save(schedule)

    async def deactivate_schedule(self, schedule_id: UUID) -> None:
        await self.update_schedule(schedule_id, ScheduleUpdate(active=False))

    async def list_assignments(self, route_id: UUID | None) -> list[RouteAssignment]:
        return await self.repository.list_assignments(route_id)

    async def _validate_assignment_entities(
        self, route_id: UUID, truck_id: UUID, personnel_ids: list[UUID]
    ) -> tuple[Truck, list[Personnel]]:
        route = await self.repository.get_route(route_id)
        if not route or not route.active:
            raise ResourceNotFound("Ruta activa no encontrada")
        truck = await self.repository.get_truck(truck_id)
        if not truck or not truck.active:
            raise ResourceNotFound("Camion activo no encontrado")
        if truck.status != "available":
            raise InvalidOperation("El camion no esta disponible")
        personnel = await self.repository.get_personnel_many(personnel_ids)
        if len(personnel) != len(personnel_ids):
            raise ResourceNotFound("Uno o mas integrantes del personal no estan activos")
        if not any(person.role == "driver" for person in personnel):
            raise InvalidOperation("La cuadrilla debe incluir al menos un conductor")
        return truck, personnel

    async def create_assignment(self, data: AssignmentCreate) -> RouteAssignment:
        truck, personnel = await self._validate_assignment_entities(
            data.route_id, data.truck_id, data.personnel_ids
        )
        if await self.repository.assignment_overlaps(
            data.route_id,
            data.truck_id,
            data.effective_from,
            data.effective_to,
        ):
            raise ResourceConflict(
                "La ruta o el camion ya tiene una asignacion durante ese periodo"
            )
        assignment = RouteAssignment(
            route_id=data.route_id,
            truck=truck,
            personnel=personnel,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        await self._save(assignment)
        return await self._required_assignment(assignment.id)

    async def _required_assignment(self, assignment_id: UUID) -> RouteAssignment:
        assignment = await self.repository.get_assignment(assignment_id)
        if not assignment:
            raise ResourceNotFound("Asignacion no encontrada")
        return assignment

    async def update_assignment(
        self, assignment_id: UUID, data: AssignmentUpdate
    ) -> RouteAssignment:
        assignment = await self._required_assignment(assignment_id)
        values = data.model_dump(exclude_unset=True)
        truck_id = values.get("truck_id", assignment.truck_id)
        personnel_ids = values.pop("personnel_ids", [person.id for person in assignment.personnel])
        effective_from = values.get("effective_from", assignment.effective_from)
        effective_to = values.get("effective_to", assignment.effective_to)
        if effective_to and effective_to < effective_from:
            raise InvalidOperation("effective_to no puede ser anterior a effective_from")
        truck, personnel = await self._validate_assignment_entities(
            assignment.route_id, truck_id, personnel_ids
        )
        if await self.repository.assignment_overlaps(
            assignment.route_id,
            truck_id,
            effective_from,
            effective_to,
            exclude_id=assignment.id,
        ):
            raise ResourceConflict(
                "La ruta o el camion ya tiene una asignacion durante ese periodo"
            )
        for field, value in values.items():
            setattr(assignment, field, value)
        assignment.truck = truck
        assignment.personnel = personnel
        await self._save(assignment)
        return await self._required_assignment(assignment.id)

    async def deactivate_assignment(self, assignment_id: UUID) -> None:
        assignment = await self._required_assignment(assignment_id)
        assignment.active = False
        await self._save(assignment)

    async def list_adjustments(self, service_date: date | None) -> list[ServiceAdjustment]:
        return await self.repository.list_adjustments(service_date)

    async def set_adjustment(self, data: ServiceAdjustmentWrite) -> ServiceAdjustment:
        schedule = await self.repository.get_schedule(data.schedule_id)
        if not schedule or not schedule.active:
            raise ResourceNotFound("Horario activo no encontrado")
        if data.service_date.weekday() != schedule.weekday:
            raise InvalidOperation("La fecha no corresponde al dia semanal del horario")
        if data.service_date < schedule.effective_from or (
            schedule.effective_to and data.service_date > schedule.effective_to
        ):
            raise InvalidOperation("La fecha esta fuera de la vigencia del horario")
        adjustment = await self.repository.get_adjustment(data.schedule_id, data.service_date)
        if adjustment is None:
            adjustment = ServiceAdjustment(**data.model_dump())
        else:
            for field, value in data.model_dump().items():
                setattr(adjustment, field, value)
        return await self._save(adjustment)

    async def delete_adjustment(self, schedule_id: UUID, service_date: date) -> None:
        adjustment = await self.repository.get_adjustment(schedule_id, service_date)
        if not adjustment:
            raise ResourceNotFound("Novedad de servicio no encontrada")
        await self.repository.delete_adjustment(adjustment)
