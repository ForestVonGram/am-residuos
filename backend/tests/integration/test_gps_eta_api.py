from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import ADMIN_KEY, DEVICE_TOKEN, seed_operation
from sqlalchemy import inspect, select

from app.models.gps import GPSDevice, VehiclePosition

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_migrations_create_gps_tables(integration_client) -> None:
    _, factory = integration_client
    async with factory() as session:
        names = await session.run_sync(
            lambda sync_session: inspect(sync_session.get_bind()).get_table_names()
        )
    assert {"gps_devices", "vehicle_positions"} <= set(names)


@pytest.mark.asyncio
async def test_ingestion_auth_batch_duplicate_and_public_privacy(integration_client) -> None:
    client, factory = integration_client
    route_id, _, _, _, _ = await seed_operation(factory)
    payload = {
        "latitude": 4.53,
        "longitude": -75.69,
        "speed_kmh": 12,
        "heading": 90,
        "recorded_at": datetime.now(UTC).isoformat(),
    }

    invalid = await client.post(
        "/api/v1/gps/positions", headers={"X-Device-Token": "wrong"}, json=payload
    )
    assert invalid.status_code == 401
    admin_as_device = await client.post(
        "/api/v1/gps/positions", headers={"X-Device-Token": ADMIN_KEY}, json=payload
    )
    assert admin_as_device.status_code == 401
    device_as_admin = await client.get(
        "/api/v1/admin/gps-devices", headers={"X-Admin-Key": DEVICE_TOKEN}
    )
    assert device_as_admin.status_code == 401

    headers = {"X-Device-Token": DEVICE_TOKEN}
    accepted = await client.post("/api/v1/gps/positions", headers=headers, json=payload)
    duplicate = await client.post("/api/v1/gps/positions", headers=headers, json=payload)
    batch = await client.post(
        "/api/v1/gps/positions",
        headers=headers,
        json=[
            {**payload, "recorded_at": datetime.now(UTC).isoformat()},
            {
                **payload,
                "longitude": -75.688,
                "recorded_at": datetime.now(UTC).isoformat(),
            },
        ],
    )
    assert accepted.json() == {"accepted": 1, "duplicates": 0}
    assert duplicate.json() == {"accepted": 0, "duplicates": 1}
    assert batch.json() == {"accepted": 2, "duplicates": 0}

    live = await client.get("/api/v1/citizen/vehicles/live")
    assert live.status_code == 200
    assert live.json()
    assert live.json()[0]["route_id"] == str(route_id)
    serialized = live.text
    assert "api_token_hash" not in serialized
    assert DEVICE_TOKEN not in serialized
    assert "personnel" not in serialized

    async with factory() as session:
        assert await session.scalar(select(GPSDevice.api_token_hash)) != DEVICE_TOKEN
        assert await session.scalar(select(VehiclePosition.id))


@pytest.mark.asyncio
async def test_admin_device_crud_and_inactive_ingestion(integration_client) -> None:
    client, factory = integration_client
    _, truck_id, _, device_id, _ = await seed_operation(factory)
    headers = {"X-Admin-Key": ADMIN_KEY}
    listed = await client.get("/api/v1/admin/gps-devices", headers=headers)
    assert listed.status_code == 200
    assert "api_token_hash" not in listed.text

    deactivated = await client.delete(
        f"/api/v1/admin/gps-devices/{device_id}", headers=headers
    )
    assert deactivated.status_code == 204
    body = {
        "latitude": 4.53,
        "longitude": -75.69,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    response = await client.post(
        "/api/v1/gps/positions",
        headers={"X-Device-Token": DEVICE_TOKEN},
        json=body,
    )
    assert response.status_code == 401

    created = await client.post(
        "/api/v1/admin/gps-devices",
        headers=headers,
        json={"device_code": "SIM-SECOND", "truck_id": str(truck_id)},
    )
    assert created.status_code == 409


@pytest.mark.asyncio
async def test_eta_scheduled_live_delay_cancel_and_assignment_conflict(integration_client) -> None:
    client, factory = integration_client
    route_id, truck_id, schedule_id, _, driver_id = await seed_operation(factory)
    service_date = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
    eta_url = "/api/v1/citizen/eta"
    params = {"latitude": 4.53, "longitude": -75.685, "route_id": str(route_id)}
    scheduled = await client.get(eta_url, params=params)
    assert scheduled.status_code == 200
    assert scheduled.json()["source"] == "scheduled"

    position = {
        "latitude": 4.53,
        "longitude": -75.69,
        "speed_kmh": 15,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    ingested = await client.post(
        "/api/v1/gps/positions",
        headers={"X-Device-Token": DEVICE_TOKEN},
        json=position,
    )
    assert ingested.status_code == 200
    live = await client.get(eta_url, params=params)
    assert live.status_code == 200
    assert live.json()["source"] == "live"
    assert live.json()["simulated"] is True

    headers = {"X-Admin-Key": ADMIN_KEY}
    adjustment = await client.put(
        "/api/v1/admin/service-adjustments",
        headers=headers,
        json={
            "schedule_id": str(schedule_id),
            "service_date": service_date,
            "delay_minutes": 15,
            "cancelled": False,
            "reason": "Prueba de retraso",
        },
    )
    assert adjustment.status_code == 200
    delayed = await client.get(eta_url, params=params)
    assert delayed.status_code == 200

    adjustment = await client.put(
        "/api/v1/admin/service-adjustments",
        headers=headers,
        json={
            "schedule_id": str(schedule_id),
            "service_date": service_date,
            "delay_minutes": 0,
            "cancelled": True,
            "reason": "Prueba de cancelación",
        },
    )
    assert adjustment.status_code == 200
    cancelled = await client.get(eta_url, params=params)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    conflict = await client.post(
        "/api/v1/admin/assignments",
        headers=headers,
        json={
            "route_id": str(route_id),
            "truck_id": str(truck_id),
            "personnel_ids": [str(driver_id)],
            "effective_from": service_date,
            "effective_to": None,
        },
    )
    assert conflict.status_code in {409, 422}


@pytest.mark.asyncio
async def test_simulated_positions_make_eta_decrease_monotonically(integration_client) -> None:
    client, factory = integration_client
    route_id, _, _, _, _ = await seed_operation(factory)
    expected_times = []
    for fraction in (0.1, 0.3, 0.5):
        response = await client.post(
            "/api/v1/gps/positions",
            headers={"X-Device-Token": DEVICE_TOKEN},
            json={
                "latitude": 4.53,
                "longitude": -75.69 + 0.01 * fraction,
                "speed_kmh": 20,
                "recorded_at": datetime.now(UTC).isoformat(),
            },
        )
        assert response.status_code == 200
        eta = await client.get(
            "/api/v1/citizen/eta",
            params={
                "latitude": 4.53,
                "longitude": -75.681,
                "route_id": str(route_id),
            },
        )
        assert eta.status_code == 200
        expected_times.append(eta.json()["estimated_arrival"])

    assert expected_times[0] > expected_times[1] > expected_times[2]
