"""Simula dispositivos GPS y envía posiciones a la API de ingesta."""

import argparse
import asyncio
import math
import os
import random
from datetime import UTC, datetime
from typing import Any

import httpx

EARTH_RADIUS_M = 6_371_008.8


def _default_api_url() -> str:
    return os.getenv("API_INTERNAL_URL") or (
        f"http://127.0.0.1:{os.getenv('APP_PORT', '8000')}"
    )


def haversine_m(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, start)
    lat2, lon2 = map(math.radians, end)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(
        delta_lon / 2
    ) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(value))


def interpolate_route(
    coordinates: list[list[float]], fraction: float
) -> tuple[float, float, float]:
    """Interpolate [longitude, latitude] coordinates by distance fraction."""
    if not coordinates:
        raise ValueError("La ruta no tiene coordenadas")
    points = [(float(point[1]), float(point[0])) for point in coordinates]
    if len(points) == 1:
        return points[0][0], points[0][1], 0.0
    lengths = [haversine_m(a, b) for a, b in zip(points, points[1:], strict=False)]
    total = sum(lengths)
    if total == 0:
        return points[0][0], points[0][1], 0.0
    remaining = max(0.0, min(1.0, fraction)) * total
    for index, ((lat_a, lon_a), (lat_b, lon_b), length) in enumerate(
        zip(points, points[1:], lengths, strict=False)
    ):
        if remaining <= length or index == len(lengths) - 1:
            ratio = remaining / length if length else 0.0
            heading = (
                math.degrees(
                    math.atan2(
                        math.sin(math.radians(lon_b - lon_a)) * math.cos(math.radians(lat_b)),
                        math.cos(math.radians(lat_a)) * math.sin(math.radians(lat_b))
                        - math.sin(math.radians(lat_a))
                        * math.cos(math.radians(lat_b))
                        * math.cos(math.radians(lon_b - lon_a)),
                    )
                )
                + 360
            ) % 360
            return lat_a + (lat_b - lat_a) * ratio, lon_a + (lon_b - lon_a) * ratio, heading
        remaining -= length
    return points[-1][0], points[-1][1], 0.0


def add_gps_noise(latitude: float, longitude: float) -> tuple[float, float]:
    distance_m = random.uniform(3, 5)
    angle = random.uniform(0, 2 * math.pi)
    delta_lat = distance_m * math.cos(angle) / 111_320
    delta_lon = distance_m * math.sin(angle) / (
        111_320 * max(0.01, math.cos(math.radians(latitude)))
    )
    return latitude + delta_lat, longitude + delta_lon


async def load_assignments(
    client: httpx.AsyncClient, admin_key: str, selected_route_id: str | None
) -> list[dict[str, Any]]:
    response = await client.get(
        "/api/v1/admin/assignments", headers={"X-Admin-Key": admin_key}
    )
    response.raise_for_status()
    from zoneinfo import ZoneInfo

    today = datetime.now(
        ZoneInfo(os.getenv("TIMEZONE", "America/Bogota"))
    ).date().isoformat()
    assignments = [
        row
        for row in response.json()
        if row["active"]
        and row["effective_from"] <= today
        and (row["effective_to"] is None or row["effective_to"] >= today)
        and row["truck"]["active"]
        and (selected_route_id is None or row["route_id"] == selected_route_id)
    ]
    by_route = {row["route_id"]: row for row in assignments}
    if not by_route:
        raise RuntimeError("No hay asignaciones activas para simular")
    return list(by_route.values())


async def get_device_token(
    client: httpx.AsyncClient,
    admin_key: str,
    truck: dict[str, Any],
    devices: list[dict[str, Any]],
) -> str:
    headers = {"X-Admin-Key": admin_key}
    device_code = f"SIM-{truck['plate']}"
    existing = next((item for item in devices if item["device_code"] == device_code), None)
    if existing:
        response = await client.post(
            f"/api/v1/admin/gps-devices/{existing['id']}/regenerate-token",
            headers=headers,
        )
    else:
        response = await client.post(
            "/api/v1/admin/gps-devices",
            headers=headers,
            json={"device_code": device_code, "truck_id": truck["id"]},
        )
    response.raise_for_status()
    return response.json()["token"]


async def run_route(
    client: httpx.AsyncClient,
    assignment: dict[str, Any],
    token: str,
    args: argparse.Namespace,
) -> None:
    route_response = await client.get(f"/api/v1/citizen/routes/{assignment['route_id']}")
    route_response.raise_for_status()
    coordinates = route_response.json()["geometry"].get("coordinates", [])
    if not coordinates:
        raise RuntimeError(f"La ruta {assignment['route_id']} no tiene geometría")
    points = [(float(point[1]), float(point[0])) for point in coordinates]
    route_length = sum(haversine_m(a, b) for a, b in zip(points, points[1:], strict=False))
    progress_m = 0.0
    ticks = 0
    pause_done = False
    headers = {"X-Device-Token": token}

    while True:
        fraction = min(1.0, progress_m / route_length) if route_length else 1.0
        if args.pause_at is not None and fraction >= args.pause_at and not pause_done:
            await asyncio.sleep(args.pause_seconds)
            pause_done = True
        latitude, longitude, heading = interpolate_route(coordinates, fraction)
        latitude, longitude = add_gps_noise(latitude, longitude)
        if random.random() >= args.dropout_prob:
            response = await client.post(
                "/api/v1/gps/positions",
                headers=headers,
                json={
                    "latitude": latitude,
                    "longitude": longitude,
                    "speed_kmh": args.speed_kmh,
                    "heading": heading,
                    "recorded_at": datetime.now(UTC).isoformat(),
                },
            )
            response.raise_for_status()
            print(
                f"{assignment['truck']['plate']}: {fraction:.0%} "
                f"({latitude:.6f}, {longitude:.6f})"
            )
        ticks += 1
        if args.offline_after is not None and ticks >= args.offline_after:
            break
        if fraction >= 1:
            if not args.loop:
                break
            progress_m = 0.0
        else:
            progress_m += args.speed_kmh * 1000 / 3600 * args.interval * args.speedup
        await asyncio.sleep(args.interval)


async def simulate(args: argparse.Namespace) -> None:
    if args.device_token and not args.route_id:
        raise ValueError("--device-token requiere --route-id para identificar su ruta")
    async with httpx.AsyncClient(base_url=args.api_url.rstrip("/"), timeout=15) as client:
        assignments = await load_assignments(client, args.admin_key, args.route_id)
        devices_response = await client.get(
            "/api/v1/admin/gps-devices",
            headers={"X-Admin-Key": args.admin_key},
        )
        devices_response.raise_for_status()
        devices = devices_response.json()
        tasks = []
        for index, assignment in enumerate(assignments):
            token = (
                args.device_token
                if index == 0 and args.device_token
                else await get_device_token(
                    client, args.admin_key, assignment["truck"], devices
                )
            )
            tasks.append(run_route(client, assignment, token, args))
        await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula vehículos sobre las rutas demo.")
    parser.add_argument("--api-url", default=_default_api_url())
    parser.add_argument("--admin-key", default=os.getenv("ADMIN_API_KEY"))
    parser.add_argument("--device-token")
    parser.add_argument("--route-id")
    parser.add_argument("--speed-kmh", type=float, default=25)
    parser.add_argument("--interval", type=float, default=3)
    parser.add_argument("--speedup", type=float, default=1)
    parser.add_argument("--dropout-prob", type=float, default=0.0)
    parser.add_argument("--pause-at", type=float)
    parser.add_argument("--pause-seconds", type=float, default=60)
    parser.add_argument("--offline-after", type=int)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if not args.admin_key:
        parser.error("configura ADMIN_API_KEY o proporciona --admin-key")
    if args.speed_kmh <= 0 or args.interval <= 0 or args.speedup <= 0:
        parser.error("velocidad, intervalo y speedup deben ser positivos")
    if not 0 <= args.dropout_prob <= 1:
        parser.error("--dropout-prob debe estar entre 0 y 1")
    if args.pause_at is not None and not 0 <= args.pause_at <= 1:
        parser.error("--pause-at debe estar entre 0 y 1")
    if args.pause_seconds < 0 or (args.offline_after is not None and args.offline_after < 1):
        parser.error("--pause-seconds debe ser positivo y --offline-after debe ser >= 1")
    asyncio.run(simulate(args))


if __name__ == "__main__":
    main()
