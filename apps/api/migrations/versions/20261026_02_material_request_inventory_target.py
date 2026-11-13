"""Destino de estoque para solicitações avulsas e de ordens de serviço.

Revision ID: 20261026_02
Revises: 20261026_01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_02"
down_revision: str | None = "20261026_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("material_requests", sa.Column("inventory_destination", sa.String(12), nullable=True))
    op.add_column("material_requests", sa.Column("inventory_item_id", sa.Integer(), nullable=True))
    op.add_column("material_requests", sa.Column("inventory_name", sa.String(220), nullable=True))
    op.add_column("material_requests", sa.Column("inventory_mode", sa.String(12), nullable=True))
    op.add_column("material_requests", sa.Column("inventory_serial", sa.String(120), nullable=True))
    op.add_column("material_requests", sa.Column("inventory_category", sa.String(80), nullable=True))
    op.add_column("material_requests", sa.Column("inventory_format_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_material_requests_inventory_item", "material_requests", "inventory_items", ["inventory_item_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_material_requests_inventory_format", "material_requests", "inventory_component_formats", ["inventory_format_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_material_requests_inventory_item_id", "material_requests", ["inventory_item_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade requer preservar a vinculação de solicitações ao Estoque.")
