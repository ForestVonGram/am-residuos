import pytest

from app.repositories.citizen import CitizenRepository


def test_distance_and_fraction_for_geojson_linestring() -> None:
    geometry = {
        "type": "LineString",
        "coordinates": [[-75.68, 4.53], [-75.67, 4.53]],
    }

    distance, fraction = CitizenRepository._distance_and_fraction(
        geometry, latitude=4.531, longitude=-75.675
    )

    assert distance == pytest.approx(111.2, abs=1)
    assert fraction == pytest.approx(0.5, abs=0.01)
