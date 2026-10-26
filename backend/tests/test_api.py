from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_admin_service, get_citizen_service
from app.main import app
from app.schemas.citizen import RouteSummary


class FakeCitizenService:
    async def list_routes(self, latitude, longitude, radius_m):
        return [
            RouteSummary(
                id=uuid4(),
                code="AXM-01",
                name="Ruta de prueba",
                sector="Centro",
                distance_m=125.4 if latitude is not None else None,
            )
        ]


class FakeAdminService:
    async def list_trucks(self, include_inactive):
        return []


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_routes_rejects_incomplete_coordinate() -> None:
    app.dependency_overrides[get_citizen_service] = lambda: FakeCitizenService()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/citizen/routes?latitude=4.53")
        assert response.status_code == 422
        assert response.json()["detail"] == "latitude y longitude deben enviarse juntas"
    finally:
        app.dependency_overrides.clear()


def test_routes_returns_public_information() -> None:
    app.dependency_overrides[get_citizen_service] = lambda: FakeCitizenService()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/citizen/routes?latitude=4.53&longitude=-75.68&radius_m=1000"
            )
        assert response.status_code == 200
        assert response.json()[0]["code"] == "AXM-01"
        assert response.json()[0]["distance_m"] == 125.4
    finally:
        app.dependency_overrides.clear()


def test_admin_routes_require_key() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/trucks")

    assert response.status_code == 401
    assert response.json()["detail"] == "Credencial administrativa invalida"


def test_admin_routes_accept_configured_key() -> None:
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/admin/trucks",
                headers={"X-Admin-Key": "change-me-local-only"},
            )
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()
