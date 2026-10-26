from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RouteSummary(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None = None
    sector: str
    distance_m: float | None = Field(default=None, ge=0)


class RouteDetail(RouteSummary):
    geometry: dict[str, Any]


class PublicPersonnel(BaseModel):
    name: str
    role: str


class PublicTruck(BaseModel):
    plate: str
    name: str


class ScheduleItem(BaseModel):
    id: UUID
    route_id: UUID
    route_code: str
    route_name: str
    sector: str
    service_date: date
    start_time: time
    estimated_start_time: time
    expected_end_time: time
    duration_minutes: int = Field(gt=0)
    delay_minutes: int = Field(default=0, ge=0)
    cancelled: bool = False
    delay_reason: str | None = None
    truck: PublicTruck | None = None
    personnel: list[PublicPersonnel] = Field(default_factory=list)


class ETAResponse(BaseModel):
    route: RouteSummary
    requested_at: datetime
    scheduled_start: datetime
    estimated_arrival: datetime
    distance_to_route_m: float = Field(ge=0)
    progress_fraction: float = Field(ge=0, le=1)
    delay_minutes: int = Field(default=0, ge=0)
    truck: PublicTruck | None = None
    personnel: list[PublicPersonnel] = Field(default_factory=list)
    source: Literal["scheduled"] = "scheduled"
    is_live: bool = False
    message: str = (
        "Estimacion basada en el horario y la duracion programada; "
        "aun no incorpora la ubicacion GPS del vehiculo."
    )
