from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PersonnelRole = Literal["driver", "collector", "supervisor"]
TruckStatus = Literal["available", "maintenance", "out_of_service"]


class PersonnelCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    employee_code: str | None = Field(default=None, max_length=40)
    role: PersonnelRole


class PersonnelUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    employee_code: str | None = Field(default=None, max_length=40)
    role: PersonnelRole | None = None
    active: bool | None = None


class PersonnelRead(PersonnelCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime


class TruckCreate(BaseModel):
    plate: str = Field(min_length=5, max_length=10, pattern=r"^[A-Za-z0-9-]+$")
    name: str = Field(min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    capacity_tons: int | None = Field(default=None, gt=0)
    status: TruckStatus = "available"

    @field_validator("plate")
    @classmethod
    def normalize_plate(cls, value: str) -> str:
        return value.upper()


class TruckUpdate(BaseModel):
    plate: str | None = Field(default=None, min_length=5, max_length=10, pattern=r"^[A-Za-z0-9-]+$")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    capacity_tons: int | None = Field(default=None, gt=0)
    status: TruckStatus | None = None
    active: bool | None = None

    @field_validator("plate")
    @classmethod
    def normalize_plate(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class TruckRead(TruckCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime


class ScheduleCreate(BaseModel):
    route_id: UUID
    weekday: int = Field(ge=0, le=6)
    start_time: time
    duration_minutes: int = Field(gt=0, le=1440)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to no puede ser anterior a effective_from")
        return self


class ScheduleUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    effective_from: date | None = None
    effective_to: date | None = None
    active: bool | None = None


class ScheduleRead(ScheduleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime


class AssignmentCreate(BaseModel):
    route_id: UUID
    truck_id: UUID
    personnel_ids: list[UUID] = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None

    @field_validator("personnel_ids")
    @classmethod
    def unique_personnel(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("personnel_ids contiene valores repetidos")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to no puede ser anterior a effective_from")
        return self


class AssignmentUpdate(BaseModel):
    truck_id: UUID | None = None
    personnel_ids: list[UUID] | None = Field(default=None, min_length=1)
    effective_from: date | None = None
    effective_to: date | None = None
    active: bool | None = None

    @field_validator("personnel_ids")
    @classmethod
    def unique_personnel(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value and len(value) != len(set(value)):
            raise ValueError("personnel_ids contiene valores repetidos")
        return value


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    route_id: UUID
    truck: TruckRead
    personnel: list[PersonnelRead]
    effective_from: date
    effective_to: date | None
    active: bool
    created_at: datetime
    updated_at: datetime


class ServiceAdjustmentWrite(BaseModel):
    schedule_id: UUID
    service_date: date
    delay_minutes: int = Field(default=0, ge=0, le=1440)
    cancelled: bool = False
    reason: str | None = Field(default=None, max_length=500)


class ServiceAdjustmentRead(ServiceAdjustmentWrite):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
