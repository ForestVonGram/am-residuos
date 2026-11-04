"""Compara las ETA calculadas con la llegada de un recorrido GPS acelerado."""

import argparse
import asyncio
import os
from datetime import UTC, datetime
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from simulate_gps import add_gps_noise, get_device_token, haversine_m, interpolate_route


async def validate(args: argparse.Namespace) -> None:
    async with httpx.AsyncClient(base_url=args.api_url.rstrip("/"), timeout=15) as client:
        admin_headers = {"X-Admin-Key": args.admin_key}
        assignments_response = await client.get(
            "/api/v1/admin/assignments", headers=admin_headers
        )
        assignments_response.raise_for_status()
        today = datetime.now(ZoneInfo(os.getenv("TIMEZONE", "America/Bogota"))).date().isoformat()
        assignments = [
            item
            for item in assignments_response.json()
            if item["active"]
            and item["effective_from"] <= today
            and (item["effective_to"] is None or item["effective_to"] >= today)
            and item["truck"]["active"]
            and (args.route_id is None or item["route_id"] == args.route_id)
        ]
        if not assignments:
            raise RuntimeError("No hay asignaciones activas para validar")
        assignment = assignments[0]

        devices_response = await client.get(
            "/api/v1/admin/gps-devices", headers=admin_headers
        )
        devices_response.raise_for_status()
        token = await get_device_token(
            client,
            args.admin_key,
            assignment["truck"],
            devices_response.json(),
        )

        route_response = await client.get(
            f"/api/v1/citizen/routes/{assignment['route_id']}"
        )
        route_response.raise_for_status()
        coordinates: list[list[float]] = route_response.json()["geometry"].get(
            "coordinates", []
        )
        if not coordinates:
            raise RuntimeError("La ruta no tiene geometría para validar")

        route_points = [(point[1], point[0]) for point in coordinates]
        route_length = sum(
            haversine_m(start, end)
            for start, end in zip(route_points, route_points[1:], strict=False)
        )
        if route_length <= 0:
            raise RuntimeError("La ruta debe tener una longitud mayor que cero")

        target_latitude, target_longitude = coordinates[-1][1], coordinates[-1][0]
        start_time = datetime.now(UTC)
        progress_m = 0.0
        predictions: list[datetime] = []
        headers = {"X-Device-Token": token}

        while True:
            fraction = min(1.0, progress_m / route_length)
            latitude, longitude, heading = interpolate_route(coordinates, fraction)
            latitude, longitude = add_gps_noise(latitude, longitude)
            position_response = await client.post(
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
            position_response.raise_for_status()

            eta_response = await client.get(
                "/api/v1/citizen/eta",
                params={
                    "latitude": target_latitude,
                    "longitude": target_longitude,
                    "route_id": assignment["route_id"],
                },
            )
            eta_response.raise_for_status()
            prediction: Any = eta_response.json().get("estimated_arrival")
            if prediction:
                predictions.append(datetime.fromisoformat(prediction.replace("Z", "+00:00")))

            if fraction >= 1:
                break
            progress_m += args.speed_kmh * 1000 / 3600 * args.interval * args.speedup
            await asyncio.sleep(args.interval)

        actual_arrival = datetime.now(UTC)
        if not predictions:
            raise RuntimeError("La API no devolvió estimaciones de llegada")
        errors = [
            abs((prediction - actual_arrival).total_seconds()) / 60
            for prediction in predictions
        ]
        print(f"Ruta: {assignment['route_id']} ({assignment['truck']['plate']})")
        print(f"Posiciones/ETA comparadas: {len(errors)}")
        print(f"Duración simulada: {(actual_arrival - start_time).total_seconds():.1f} s")
        print(f"Error medio absoluto: {mean(errors):.2f} min")


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida ETA con llegada simulada.")
    parser.add_argument(
        "--api-url", default=os.getenv("API_INTERNAL_URL", "http://127.0.0.1:8000")
    )
    parser.add_argument("--admin-key", default=os.getenv("ADMIN_API_KEY"))
    parser.add_argument("--route-id")
    parser.add_argument("--speed-kmh", type=float, default=25)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--speedup", type=float, default=10)
    args = parser.parse_args()
    if not args.admin_key:
        parser.error("configura ADMIN_API_KEY o proporciona --admin-key")
    if args.speed_kmh <= 0 or args.interval <= 0 or args.speedup <= 0:
        parser.error("--speed-kmh, --interval y --speedup deben ser positivos")
    asyncio.run(validate(args))


if __name__ == "__main__":
    main()
