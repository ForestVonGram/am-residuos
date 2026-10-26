import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.route import CollectionRoute, RouteSchedule

assignment_personnel = Table(
    "assignment_personnel",
    Base.metadata,
    Column(
        "assignment_id",
        UUID(as_uuid=True),
        ForeignKey("route_assignments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "personnel_id",
        UUID(as_uuid=True),
        ForeignKey("personnel.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class Personnel(TimestampMixin, Base):
    __tablename__ = "personnel"
    __table_args__ = (
        CheckConstraint("role IN ('driver', 'collector', 'supervisor')", name="valid_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    employee_code: Mapped[str | None] = mapped_column(String(40), unique=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)

    assignments: Mapped[list["RouteAssignment"]] = relationship(
        secondary=assignment_personnel, back_populates="personnel"
    )


class Truck(TimestampMixin, Base):
    __tablename__ = "trucks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'maintenance', 'out_of_service')", name="valid_status"
        ),
        CheckConstraint("capacity_tons IS NULL OR capacity_tons > 0", name="positive_capacity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plate: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    brand: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    capacity_tons: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), default="available", server_default="available", index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)

    assignments: Mapped[list["RouteAssignment"]] = relationship(back_populates="truck")


class RouteAssignment(TimestampMixin, Base):
    __tablename__ = "route_assignments"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="valid_date_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_routes.id", ondelete="CASCADE"), index=True
    )
    truck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trucks.id", ondelete="RESTRICT"), index=True
    )
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)

    route: Mapped["CollectionRoute"] = relationship(back_populates="assignments")
    truck: Mapped[Truck] = relationship(back_populates="assignments")
    personnel: Mapped[list[Personnel]] = relationship(
        secondary=assignment_personnel, back_populates="assignments"
    )


class ServiceAdjustment(TimestampMixin, Base):
    __tablename__ = "service_adjustments"
    __table_args__ = (
        UniqueConstraint("schedule_id", "service_date", name="schedule_service_date"),
        CheckConstraint("delay_minutes >= 0", name="non_negative_delay"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_schedules.id", ondelete="CASCADE"), index=True
    )
    service_date: Mapped[date] = mapped_column(Date, index=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reason: Mapped[str | None] = mapped_column(Text)

    schedule: Mapped["RouteSchedule"] = relationship(back_populates="adjustments")
