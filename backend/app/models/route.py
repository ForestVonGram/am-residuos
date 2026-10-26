import uuid
from datetime import date, time

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CollectionRoute(TimestampMixin, Base):
    __tablename__ = "collection_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str] = mapped_column(String(160), index=True)
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True)
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)

    schedules: Mapped[list["RouteSchedule"]] = relationship(
        back_populates="route", cascade="all, delete-orphan"
    )


class RouteSchedule(TimestampMixin, Base):
    __tablename__ = "route_schedules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("duration_minutes > 0", name="positive_duration"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_routes.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, index=True)
    start_time: Mapped[time] = mapped_column(Time(timezone=False))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)

    route: Mapped[CollectionRoute] = relationship(back_populates="schedules")
