"""Create administrative and operational module.

Revision ID: 20261026_02
Revises: 20261026_01
Create Date: 2026-10-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261026_02"
down_revision = "20261026_01"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "personnel",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("employee_code", sa.String(length=40), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "role IN ('driver', 'collector', 'supervisor')",
            name=op.f("ck_personnel_valid_role"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_personnel")),
        sa.UniqueConstraint("employee_code", name=op.f("uq_personnel_employee_code")),
    )
    op.create_index("ix_personnel_active", "personnel", ["active"])
    op.create_index("ix_personnel_role", "personnel", ["role"])

    op.create_table(
        "trucks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plate", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("brand", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("capacity_tons", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="available", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "capacity_tons IS NULL OR capacity_tons > 0",
            name=op.f("ck_trucks_positive_capacity"),
        ),
        sa.CheckConstraint(
            "status IN ('available', 'maintenance', 'out_of_service')",
            name=op.f("ck_trucks_valid_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trucks")),
        sa.UniqueConstraint("plate", name=op.f("uq_trucks_plate")),
    )
    op.create_index("ix_trucks_active", "trucks", ["active"])
    op.create_index("ix_trucks_plate", "trucks", ["plate"])
    op.create_index("ix_trucks_status", "trucks", ["status"])

    op.create_table(
        "route_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("truck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_route_assignments_valid_date_range"),
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["collection_routes.id"],
            name=op.f("fk_route_assignments_route_id_collection_routes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["truck_id"],
            ["trucks.id"],
            name=op.f("fk_route_assignments_truck_id_trucks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_route_assignments")),
    )
    op.create_index("ix_route_assignments_active", "route_assignments", ["active"])
    op.create_index("ix_route_assignments_effective_from", "route_assignments", ["effective_from"])
    op.create_index("ix_route_assignments_route_id", "route_assignments", ["route_id"])
    op.create_index("ix_route_assignments_truck_id", "route_assignments", ["truck_id"])

    op.create_table(
        "assignment_personnel",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("personnel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["route_assignments.id"],
            name=op.f("fk_assignment_personnel_assignment_id_route_assignments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["personnel_id"],
            ["personnel.id"],
            name=op.f("fk_assignment_personnel_personnel_id_personnel"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "assignment_id", "personnel_id", name=op.f("pk_assignment_personnel")
        ),
    )

    op.create_table(
        "service_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cancelled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "delay_minutes >= 0",
            name=op.f("ck_service_adjustments_non_negative_delay"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["route_schedules.id"],
            name=op.f("fk_service_adjustments_schedule_id_route_schedules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_adjustments")),
        sa.UniqueConstraint(
            "schedule_id",
            "service_date",
            name=op.f("uq_service_adjustments_schedule_service_date"),
        ),
    )
    op.create_index("ix_service_adjustments_schedule_id", "service_adjustments", ["schedule_id"])
    op.create_index("ix_service_adjustments_service_date", "service_adjustments", ["service_date"])


def downgrade() -> None:
    op.drop_table("service_adjustments")
    op.drop_table("assignment_personnel")
    op.drop_table("route_assignments")
    op.drop_table("trucks")
    op.drop_table("personnel")
