from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_admin_service, get_citizen_service, get_gps_service
from app.core.config import Settings
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

class FakeGPSService:
    def __init__(self) -> None:
        self.ingest_calls = 0

    async def ingest(self, token, positions):
        self.ingest_calls += 1
        return len(positions), 0


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


def test_admin_routes_accept_configured_key(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        admin_api_key=SecretStr("test-api-key-with-at-least-thirty-two-characters"),
        admin_username="admin",
        admin_password=SecretStr("test-password"),
        admin_session_secret=SecretStr("test-session-secret-with-at-least-thirty-two-chars"),
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/admin/trucks",
                headers={
                    "X-Admin-Key": "test-api-key-with-at-least-thirty-two-characters"
                },
            )
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


def test_admin_login_issues_http_only_session_cookie(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        admin_api_key=SecretStr("test-api-key-with-at-least-thirty-two-characters"),
        admin_username="admin",
        admin_password=SecretStr("test-password-with-sufficient-length"),
        admin_session_secret=SecretStr("test-session-secret-with-at-least-thirty-two-chars"),
    )
    monkeypatch.setattr("app.api.routes.admin_auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/admin/auth/login",
                json={
                    "username": "admin",
                    "password": "test-password-with-sufficient-length",
                },
            )
            response = client.get("/api/v1/admin/trucks")
            logout = client.post("/api/v1/admin/auth/logout")
            rejected_after_logout = client.get("/api/v1/admin/trucks")

        assert login.status_code == 200
        assert login.json() == {"username": "admin"}
        cookie = login.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=strict" in cookie
        assert response.status_code == 200
        assert response.json() == []
        assert logout.status_code == 204
        assert rejected_after_logout.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_admin_login_rejects_invalid_password(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        admin_username="admin",
        admin_password=SecretStr("test-password-with-sufficient-length"),
        admin_session_secret=SecretStr("test-session-secret-with-at-least-thirty-two-chars"),
    )
    monkeypatch.setattr("app.api.routes.admin_auth.get_settings", lambda: settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
    assert response.status_code == 401


def test_admin_login_reports_missing_auth_configuration(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        admin_api_key=SecretStr(""),
        admin_username="",
        admin_password=SecretStr(""),
        admin_session_secret=SecretStr(""),
    )
    monkeypatch.setattr("app.api.routes.admin_auth.get_settings", lambda: settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": "password"},
        )
    assert response.status_code == 503


def test_admin_login_rejects_example_placeholders(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        admin_username="admin",
        admin_password=SecretStr("replace-with-a-strong-password"),
        admin_session_secret=SecretStr(
            "replace-with-a-separate-64-character-random-secret"
        ),
    )
    monkeypatch.setattr("app.api.routes.admin_auth.get_settings", lambda: settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/auth/login",
            json={
                "username": "admin",
                "password": "replace-with-a-strong-password",
            },
        )
    assert response.status_code == 503


def test_gps_ingestion_requires_device_token() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/gps/positions",
            json={
                "latitude": 4.53,
                "longitude": -75.68,
                "recorded_at": "2026-10-26T10:00:00-05:00",
            },
        )

    assert response.status_code == 401


def test_gps_batch_rejects_more_than_fifty_positions() -> None:
    service = FakeGPSService()
    app.dependency_overrides[get_gps_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/gps/positions",
                headers={"X-Device-Token": "token"},
                json=[
                    {
                        "latitude": 4.53,
                        "longitude": -75.68,
                        "recorded_at": "2026-10-26T10:00:00-05:00",
                    }
                    for _ in range(51)
                ],
            )
        assert response.status_code == 422
        assert response.json()["detail"] == "El lote admite máximo 50 posiciones"
        assert service.ingest_calls == 0
    finally:
        app.dependency_overrides.clear()


def test_eta_rejects_malformed_at_with_spanish_message() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/citizen/eta",
            params={"latitude": 4.53, "longitude": -75.68, "at": "no-es-una-fecha"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "El parámetro 'at' debe ser una fecha y hora válida."
