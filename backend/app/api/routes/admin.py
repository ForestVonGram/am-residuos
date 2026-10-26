from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import AdminServiceDependency
from app.schemas.admin import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    PersonnelCreate,
    PersonnelRead,
    PersonnelUpdate,
    ScheduleCreate,
    ScheduleRead,
    ScheduleUpdate,
    ServiceAdjustmentRead,
    ServiceAdjustmentWrite,
    TruckCreate,
    TruckRead,
    TruckUpdate,
)

router = APIRouter()


@router.get("/personnel", response_model=list[PersonnelRead])
async def list_personnel(
    service: AdminServiceDependency,
    include_inactive: bool = False,
) -> list[PersonnelRead]:
    return await service.list_personnel(include_inactive)


@router.post("/personnel", response_model=PersonnelRead, status_code=status.HTTP_201_CREATED)
async def create_personnel(data: PersonnelCreate, service: AdminServiceDependency) -> PersonnelRead:
    return await service.create_personnel(data)


@router.patch("/personnel/{personnel_id}", response_model=PersonnelRead)
async def update_personnel(
    personnel_id: UUID, data: PersonnelUpdate, service: AdminServiceDependency
) -> PersonnelRead:
    return await service.update_personnel(personnel_id, data)


@router.delete("/personnel/{personnel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_personnel(personnel_id: UUID, service: AdminServiceDependency) -> Response:
    await service.deactivate_personnel(personnel_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/trucks", response_model=list[TruckRead])
async def list_trucks(
    service: AdminServiceDependency,
    include_inactive: bool = False,
) -> list[TruckRead]:
    return await service.list_trucks(include_inactive)


@router.post("/trucks", response_model=TruckRead, status_code=status.HTTP_201_CREATED)
async def create_truck(data: TruckCreate, service: AdminServiceDependency) -> TruckRead:
    return await service.create_truck(data)


@router.patch("/trucks/{truck_id}", response_model=TruckRead)
async def update_truck(
    truck_id: UUID, data: TruckUpdate, service: AdminServiceDependency
) -> TruckRead:
    return await service.update_truck(truck_id, data)


@router.delete("/trucks/{truck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_truck(truck_id: UUID, service: AdminServiceDependency) -> Response:
    await service.deactivate_truck(truck_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/schedules", response_model=list[ScheduleRead])
async def list_schedules(
    service: AdminServiceDependency, route_id: UUID | None = None
) -> list[ScheduleRead]:
    return await service.list_schedules(route_id)


@router.post("/schedules", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(data: ScheduleCreate, service: AdminServiceDependency) -> ScheduleRead:
    return await service.create_schedule(data)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleRead)
async def update_schedule(
    schedule_id: UUID, data: ScheduleUpdate, service: AdminServiceDependency
) -> ScheduleRead:
    return await service.update_schedule(schedule_id, data)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_schedule(schedule_id: UUID, service: AdminServiceDependency) -> Response:
    await service.deactivate_schedule(schedule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assignments", response_model=list[AssignmentRead])
async def list_assignments(
    service: AdminServiceDependency, route_id: UUID | None = None
) -> list[AssignmentRead]:
    return await service.list_assignments(route_id)


@router.post("/assignments", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    data: AssignmentCreate, service: AdminServiceDependency
) -> AssignmentRead:
    return await service.create_assignment(data)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentRead)
async def update_assignment(
    assignment_id: UUID, data: AssignmentUpdate, service: AdminServiceDependency
) -> AssignmentRead:
    return await service.update_assignment(assignment_id, data)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_assignment(assignment_id: UUID, service: AdminServiceDependency) -> Response:
    await service.deactivate_assignment(assignment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/service-adjustments", response_model=list[ServiceAdjustmentRead])
async def list_service_adjustments(
    service: AdminServiceDependency,
    service_date: Annotated[date | None, Query()] = None,
) -> list[ServiceAdjustmentRead]:
    return await service.list_adjustments(service_date)


@router.put("/service-adjustments", response_model=ServiceAdjustmentRead)
async def set_service_adjustment(
    data: ServiceAdjustmentWrite, service: AdminServiceDependency
) -> ServiceAdjustmentRead:
    return await service.set_adjustment(data)


@router.delete(
    "/service-adjustments/{schedule_id}/{service_date}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_service_adjustment(
    schedule_id: UUID, service_date: date, service: AdminServiceDependency
) -> Response:
    await service.delete_adjustment(schedule_id, service_date)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
