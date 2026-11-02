from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from app.services.geo import distance_and_fraction, route_length_m


@dataclass(frozen=True)
class PositionSample:
    latitude: float
    longitude: float
    recorded_at: datetime
    speed_kmh: float | None = None
    heading: float | None = None


@dataclass(frozen=True)
class LiveETAResult:
    eta: datetime | None
    position: PositionSample
    stale: bool
    distance_remaining_m: float | None
    minutes_remaining: float | None
    status: str
    confidence: str
    message: str


def _sample(position: Any) -> PositionSample:
    if isinstance(position, PositionSample):
        return position
    return PositionSample(
        latitude=position.latitude,
        longitude=position.longitude,
        recorded_at=position.recorded_at,
        speed_kmh=position.speed_kmh,
        heading=position.heading,
    )


def calculate_live_eta(
    geometry: dict[str, Any],
    citizen_fraction: float,
    positions: Sequence[Any],
    duration_minutes: int,
    now: datetime,
    *,
    stale_after_seconds: int = 60,
    speed_window_seconds: int = 180,
    passed_tolerance: float = 0.005,
) -> LiveETAResult | None:
    if not positions:
        return None
    samples = sorted((_sample(item) for item in positions), key=lambda item: item.recorded_at)
    latest = samples[-1]
    age_seconds = max(0.0, (now - latest.recorded_at).total_seconds())
    if age_seconds > stale_after_seconds:
        return LiveETAResult(
            eta=None,
            position=latest,
            stale=True,
            distance_remaining_m=None,
            minutes_remaining=None,
            status="scheduled",
            confidence="low",
            message="La señal GPS está desactualizada; se usa el horario programado.",
        )

    route_distance = route_length_m(geometry)
    _, vehicle_fraction = distance_and_fraction(
        geometry, latest.latitude, latest.longitude
    )
    vehicle_fraction = max(0.0, min(1.0, vehicle_fraction))
    citizen_fraction = max(0.0, min(1.0, citizen_fraction))
    if vehicle_fraction > citizen_fraction + passed_tolerance:
        return LiveETAResult(
            eta=now,
            position=latest,
            stale=False,
            distance_remaining_m=0.0,
            minutes_remaining=0.0,
            status="passed",
            confidence="high" if age_seconds <= 15 else "medium",
            message="El camión ya pasó por el punto consultado.",
        )

    distance_remaining = max(0.0, citizen_fraction - vehicle_fraction) * route_distance
    window_start = now - timedelta(seconds=speed_window_seconds)
    window = [sample for sample in samples if sample.recorded_at >= window_start]
    speed_values = [
        sample.speed_kmh
        for sample in window
        if sample.speed_kmh is not None and sample.speed_kmh >= 0
    ]
    if latest.speed_kmh == 0:
        speed = route_distance / duration_minutes * 60 if duration_minutes > 0 else 0
    elif speed_values:
        speed = mean(speed_values)
    else:
        speed = 0.0
        if len(window) > 1:
            elapsed = (window[-1].recorded_at - window[0].recorded_at).total_seconds()
            travelled = abs(
                distance_and_fraction(
                    geometry, window[-1].latitude, window[-1].longitude
                )[1]
                - distance_and_fraction(
                    geometry, window[0].latitude, window[0].longitude
                )[1]
            ) * route_distance
            if elapsed > 0:
                speed = travelled / elapsed * 3.6

    if speed <= 0:
        speed = route_distance / duration_minutes * 60 if duration_minutes > 0 else 5.0
    speed = max(5.0, min(40.0, speed))
    minutes = distance_remaining / (speed * 1000 / 60)
    status = "arriving" if minutes <= 5 else "approaching"
    confidence = (
        "high"
        if len(window) >= 3 and age_seconds <= 15
        else "medium"
        if age_seconds <= 30
        else "low"
    )
    return LiveETAResult(
        eta=now + timedelta(minutes=minutes),
        position=latest,
        stale=False,
        distance_remaining_m=distance_remaining,
        minutes_remaining=minutes,
        status=status,
        confidence=confidence,
        message="Estimación en vivo basada en posiciones GPS simuladas.",
    )
