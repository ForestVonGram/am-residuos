from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.geo import route_length_m
from app.services.live_eta import PositionSample, calculate_live_eta

ZONE = ZoneInfo("America/Bogota")
NOW = datetime(2026, 11, 2, 10, 0, tzinfo=ZONE)
GEOMETRY = {"type": "LineString", "coordinates": [[-75.69, 4.53], [-75.68, 4.53]]}


def position(fraction: float, recorded_at: datetime = NOW, speed: float = 20) -> PositionSample:
    return PositionSample(
        latitude=4.53,
        longitude=-75.69 + 0.01 * fraction,
        recorded_at=recorded_at,
        speed_kmh=speed,
        heading=90,
    )


def estimate(fraction: float, positions: list[PositionSample], duration: int = 30):
    return calculate_live_eta(GEOMETRY, fraction, positions, duration, NOW)


def test_live_eta_approaching_when_truck_is_before_citizen() -> None:
    result = estimate(0.75, [position(0.25, speed=5)])

    assert result is not None
    assert result.status == "approaching"
    assert result.eta is not None and result.eta > NOW
    assert result.distance_remaining_m == pytest.approx(route_length_m(GEOMETRY) * 0.5, rel=0.02)


def test_live_eta_reports_passed_when_truck_is_beyond_citizen() -> None:
    result = estimate(0.4, [position(0.8)])

    assert result is not None
    assert result.status == "passed"
    assert result.eta == NOW
    assert result.distance_remaining_m == 0


def test_live_eta_arriving_when_truck_is_over_the_point() -> None:
    result = estimate(0.5, [position(0.5)])

    assert result is not None
    assert result.status == "arriving"
    assert result.minutes_remaining == 0


def test_live_eta_uses_schedule_speed_when_latest_speed_is_zero() -> None:
    result = estimate(0.5, [position(0, speed=0)], duration=30)

    assert result is not None
    remaining = route_length_m(GEOMETRY) * 0.5
    assert result.minutes_remaining == pytest.approx(remaining / (5 * 1000 / 60))


def test_live_eta_averages_recent_speeds_and_excludes_old_positions() -> None:
    samples = [
        position(0.1, NOW - timedelta(minutes=5), speed=3),
        position(0.2, NOW - timedelta(seconds=30), speed=10),
        position(0.3, NOW, speed=30),
    ]

    result = estimate(0.8, samples)

    assert result is not None
    expected_distance = route_length_m(GEOMETRY) * 0.5
    assert result.minutes_remaining == pytest.approx(expected_distance / (20 * 1000 / 60))


def test_live_eta_returns_stale_for_old_position() -> None:
    result = estimate(0.8, [position(0.2, NOW - timedelta(seconds=61))])

    assert result is not None
    assert result.stale is True
    assert result.eta is None
    assert result.status == "scheduled"
    assert "desactualizada" in result.message


def test_live_eta_handles_single_point_route() -> None:
    geometry = {"type": "LineString", "coordinates": [[-75.69, 4.53]]}
    position_on_route = PositionSample(4.53, -75.69, NOW, speed_kmh=0)

    result = calculate_live_eta(geometry, 0.0, [position_on_route], 60, NOW)

    assert result is not None
    assert result.status == "arriving"
    assert result.distance_remaining_m == 0
    assert result.eta == NOW


def test_live_eta_handles_fraction_edges_zero_and_one() -> None:
    at_start = estimate(0.0, [position(0.0)])
    at_end = estimate(1.0, [position(0.0)])

    assert at_start is not None and at_start.minutes_remaining == 0
    assert at_end is not None
    assert at_end.distance_remaining_m == pytest.approx(route_length_m(GEOMETRY), rel=0.02)


def test_live_eta_preserves_bogota_timezone_across_midnight() -> None:
    now = datetime(2026, 11, 2, 23, 59, tzinfo=ZONE)
    sample = PositionSample(4.53, -75.69, now, speed_kmh=40)

    result = calculate_live_eta(GEOMETRY, 1.0, [sample], 30, now)

    assert result is not None
    assert result.eta is not None
    assert result.eta.date() == (now + timedelta(days=1)).date()
    assert result.eta.tzinfo == ZONE
