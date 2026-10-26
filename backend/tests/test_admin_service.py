from datetime import date
from uuid import uuid4

import pytest

from app.models.operational import Personnel, Truck
from app.models.route import CollectionRoute
from app.schemas.admin import AssignmentCreate
from app.services.admin import AdminService, InvalidOperation, ResourceConflict


class FakeAssignmentRepository:
    def __init__(self, personnel, truck, overlap=False):
        self.personnel = personnel
        self.truck = truck
        self.overlap = overlap
        self.route = CollectionRoute(
            id=uuid4(),
            code="AXM-01",
            name="Centro",
            sector="Centro",
            geometry="unused",
            active=True,
        )

    async def get_route(self, route_id):
        return self.route

    async def get_truck(self, truck_id):
        return self.truck

    async def get_personnel_many(self, ids):
        return self.personnel

    async def assignment_overlaps(self, *args, **kwargs):
        return self.overlap


def assignment_data(repository: FakeAssignmentRepository) -> AssignmentCreate:
    return AssignmentCreate(
        route_id=repository.route.id,
        truck_id=repository.truck.id,
        personnel_ids=[person.id for person in repository.personnel],
        effective_from=date(2026, 10, 26),
    )


@pytest.mark.asyncio
async def test_assignment_requires_driver() -> None:
    collector = Personnel(
        id=uuid4(), first_name="Ana", last_name="Lopez", role="collector", active=True
    )
    truck = Truck(id=uuid4(), plate="ABC123", name="Camion 1", status="available", active=True)
    repository = FakeAssignmentRepository([collector], truck)
    service = AdminService(repository)

    with pytest.raises(InvalidOperation, match="conductor"):
        await service.create_assignment(assignment_data(repository))


@pytest.mark.asyncio
async def test_assignment_rejects_busy_truck_or_route() -> None:
    driver = Personnel(id=uuid4(), first_name="Luis", last_name="Perez", role="driver", active=True)
    truck = Truck(id=uuid4(), plate="ABC123", name="Camion 1", status="available", active=True)
    repository = FakeAssignmentRepository([driver], truck, overlap=True)
    service = AdminService(repository)

    with pytest.raises(ResourceConflict, match="periodo"):
        await service.create_assignment(assignment_data(repository))
