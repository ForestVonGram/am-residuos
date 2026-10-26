from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.route import RouteSchedule


def ensure_local_datetime(value: datetime | None, timezone: str) -> datetime:
    zone = ZoneInfo(timezone)
    if value is None:
        return datetime.now(zone)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def expected_arrival(
    service_date: date,
    schedule: RouteSchedule,
    progress_fraction: float,
    timezone: str,
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    start = datetime.combine(service_date, schedule.start_time, zone)
    bounded_fraction = min(1.0, max(0.0, progress_fraction))
    arrival = start + timedelta(minutes=schedule.duration_minutes * bounded_fraction)
    return start, arrival
