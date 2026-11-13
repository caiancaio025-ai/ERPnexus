"""create commercial equipment registry

Revision ID: 20260821_01
Revises: 20260818_02
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_01"
down_revision: str | None = "20260818_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("serial_code", sa.String(length=20), nullable=True),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False, server_default="rental_sale"),
        sa.Column("equipment_type", sa.String(length=180), nullable=False),
        sa.Column("manufacturer", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("power", sa.String(length=80), nullable=True),
        sa.Column("voltage", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("serial_code", name="uq_commercial_equipment_serial_code"),
    )
    op.create_index("ix_commercial_equipment_serial_code", "commercial_equipment", ["serial_code"])
    op.create_index("ix_commercial_equipment_company_code", "commercial_equipment", ["company_code"])
    op.create_index("ix_commercial_equipment_purpose", "commercial_equipment", ["purpose"])
    op.create_index("ix_commercial_equipment_equipment_type", "commercial_equipment", ["equipment_type"])
    op.create_index("ix_commercial_equipment_manufacturer", "commercial_equipment", ["manufacturer"])
    op.create_index("ix_commercial_equipment_model", "commercial_equipment", ["model"])
    op.create_index("ix_commercial_equipment_is_active", "commercial_equipment", ["is_active"])
    op.create_index("ix_commercial_equipment_created_by", "commercial_equipment", ["created_by"])


def downgrade() -> None:
    op.drop_table("commercial_equipment")
