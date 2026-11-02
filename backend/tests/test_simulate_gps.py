import pytest

from app.services.geo import haversine_m
from scripts.simulate_gps import add_gps_noise, interpolate_route

ROUTE = [[-75.69, 4.53], [-75.68, 4.53]]


def test_interpolation_returns_start_middle_and_end_points() -> None:
    start = interpolate_route(ROUTE, 0)
    middle = interpolate_route(ROUTE, 0.5)
    end = interpolate_route(ROUTE, 1)

    assert start[:2] == (4.53, -75.69)
    assert middle[0] == 4.53
    assert middle[1] == pytest.approx(-75.685, abs=1e-5)
    assert end[:2] == (4.53, -75.68)
    assert interpolate_route(ROUTE, 2)[:2] == end[:2]


def test_gps_noise_is_bounded_to_five_metres() -> None:
    latitude, longitude = add_gps_noise(4.53, -75.69)

    assert 3 <= haversine_m(4.53, -75.69, latitude, longitude) <= 5.01


def test_interpolation_supports_single_point_route() -> None:
    assert interpolate_route([[-75.69, 4.53]], 0.7) == (4.53, -75.69, 0.0)
