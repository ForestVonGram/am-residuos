from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PositionInput(BaseModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    speed_kmh: Annotated[float | None, Field(default=None, ge=0, le=300)]
    heading: Annotated[float | None, Field(default=None, ge=0, lt=360)]
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at debe incluir zona horaria")
        return value


class PositionIngestResponse(BaseModel):
    accepted: int
    duplicates: int


class GPSDeviceCreate(BaseModel):
    device_code: str = Field(min_length=1, max_length=80)
    truck_id: UUID


class GPSDeviceUpdate(BaseModel):
    truck_id: UUID | None = None
    active: bool | None = None


class GPSDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_code: str
    truck_id: UUID
    active: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    online: bool
    truck_plate: str


class GPSDeviceCreated(BaseModel):
    device: GPSDeviceRead
    token: str


class LiveVehicle(BaseModel):
    truck_plate: str
    truck_name: str
    latitude: float
    longitude: float
    speed_kmh: float | None
    heading: float | None
    recorded_at: datetime
    stale: bool
    route_id: UUID
    simulated: bool = True
