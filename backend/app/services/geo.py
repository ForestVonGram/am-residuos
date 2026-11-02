from math import asin, cos, radians, sin, sqrt
from typing import Any

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    delta_lat = radians(lat_b - lat_a)
    delta_lon = radians(lon_b - lon_a)
    value = sin(delta_lat / 2) ** 2 + (
        cos(radians(lat_a)) * cos(radians(lat_b)) * sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * asin(sqrt(value))


def route_length_m(geometry: dict[str, Any]) -> float:
    coordinates = geometry.get("coordinates", [])
    if not coordinates:
        return 0.0
    return sum(
        haversine_m(float(start[1]), float(start[0]), float(end[1]), float(end[0]))
        for start, end in zip(coordinates, coordinates[1:], strict=False)
    )


def distance_and_fraction(
    geometry: dict[str, Any], latitude: float, longitude: float
) -> tuple[float, float]:
    """Project a coordinate onto a GeoJSON LineString and return distance and progress."""
    coordinates = geometry.get("coordinates", [])
    if not coordinates:
        return float("inf"), 0.0
    if len(coordinates) == 1:
        point_lon, point_lat = coordinates[0]
        return haversine_m(latitude, longitude, float(point_lat), float(point_lon)), 0.0

    reference_lat = radians(latitude)

    def project(lon: float, lat: float) -> tuple[float, float]:
        return (
            EARTH_RADIUS_M * radians(float(lon) - longitude) * cos(reference_lat),
            EARTH_RADIUS_M * radians(float(lat) - latitude),
        )

    projected = [project(lon, lat) for lon, lat in coordinates]
    lengths = [
        sqrt((bx - ax) ** 2 + (by - ay) ** 2)
        for (ax, ay), (bx, by) in zip(projected, projected[1:], strict=False)
    ]
    total_length = sum(lengths)
    best_distance = float("inf")
    best_progress = 0.0
    traversed = 0.0
    for (ax, ay), (bx, by), segment_length in zip(
        projected, projected[1:], lengths, strict=False
    ):
        dx, dy = bx - ax, by - ay
        denominator = dx * dx + dy * dy
        fraction = (
            0.0
            if denominator == 0
            else max(0.0, min(1.0, -(ax * dx + ay * dy) / denominator))
        )
        nearest_x, nearest_y = ax + fraction * dx, ay + fraction * dy
        distance = sqrt(nearest_x * nearest_x + nearest_y * nearest_y)
        if distance < best_distance:
            best_distance = distance
            best_progress = (
                (traversed + fraction * segment_length) / total_length if total_length else 0.0
            )
        traversed += segment_length
    return best_distance, best_progress
