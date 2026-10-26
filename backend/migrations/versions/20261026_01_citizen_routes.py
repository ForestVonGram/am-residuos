"""Create citizen routes and schedules.

Revision ID: 20261026_01
Revises:
Create Date: 2026-10-26
"""

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261026_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "collection_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sector", sa.String(length=160), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collection_routes"),
        sa.UniqueConstraint("code", name="uq_collection_routes_code"),
    )
    op.create_index("ix_collection_routes_active", "collection_routes", ["active"])
    op.create_index("ix_collection_routes_code", "collection_routes", ["code"])
    op.create_index("ix_collection_routes_sector", "collection_routes", ["sector"])
    op.create_index(
        "ix_collection_routes_geometry",
        "collection_routes",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "route_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "duration_minutes > 0", name=op.f("ck_route_schedules_positive_duration")
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6", name=op.f("ck_route_schedules_weekday_range")
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["collection_routes.id"],
            name="fk_route_schedules_route_id_collection_routes",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_route_schedules"),
    )
    op.create_index("ix_route_schedules_active", "route_schedules", ["active"])
    op.create_index("ix_route_schedules_route_id", "route_schedules", ["route_id"])
    op.create_index("ix_route_schedules_weekday", "route_schedules", ["weekday"])


def downgrade() -> None:
    op.drop_table("route_schedules")
    op.drop_index("ix_collection_routes_geometry", table_name="collection_routes")
    op.drop_table("collection_routes")
