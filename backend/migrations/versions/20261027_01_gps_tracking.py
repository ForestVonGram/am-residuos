"""Add simulated GPS device tracking.

Revision ID: 20261027_01
Revises: 20261026_02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261027_01"
down_revision = "20261026_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gps_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_code", sa.String(length=80), nullable=False),
        sa.Column("truck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_token_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["truck_id"], ["trucks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code"),
        sa.UniqueConstraint("truck_id", name="uq_gps_devices_one_device_per_truck"),
    )
    op.create_index("ix_gps_devices_device_code", "gps_devices", ["device_code"])
    op.create_index("ix_gps_devices_active", "gps_devices", ["active"])
    op.create_table(
        "vehicle_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("truck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed_kmh", sa.Float(), nullable=True),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="valid_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="valid_longitude"),
        sa.ForeignKeyConstraint(["device_id"], ["gps_devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["truck_id"], ["trucks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "recorded_at", name="uq_vehicle_positions_device_recorded_at"),
    )
    op.create_index("ix_vehicle_positions_recorded_at", "vehicle_positions", ["recorded_at"])
    op.create_index(
        "ix_vehicle_positions_truck_recorded_at",
        "vehicle_positions",
        ["truck_id", sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("vehicle_positions")
    op.drop_table("gps_devices")
