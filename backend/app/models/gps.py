import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.operational import Truck


class GPSDevice(TimestampMixin, Base):
    __tablename__ = "gps_devices"
    __table_args__ = (UniqueConstraint("truck_id", name="one_device_per_truck"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    truck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trucks.id", ondelete="RESTRICT"), nullable=False
    )
    api_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    truck: Mapped["Truck"] = relationship(back_populates="gps_device")
    positions: Mapped[list["VehiclePosition"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class VehiclePosition(Base):
    __tablename__ = "vehicle_positions"
    __table_args__ = (
        UniqueConstraint("device_id", "recorded_at", name="device_recorded_at"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="valid_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="valid_longitude"),
        Index(
            "ix_vehicle_positions_truck_recorded_at", "truck_id", desc("recorded_at")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gps_devices.id", ondelete="CASCADE"), nullable=False
    )
    truck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trucks.id", ondelete="RESTRICT"), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    device: Mapped[GPSDevice] = relationship(back_populates="positions")
