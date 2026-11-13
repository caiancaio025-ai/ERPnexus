"""Planejamento do destino de estoque por pedido sem vincular pela descrição.

Revision ID: 20261026_01
Revises: 20261022_02
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20261026_01"
down_revision: str | None = "20261022_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("inventory_destination", sa.String(12), nullable=True))
    op.add_column("purchase_orders", sa.Column("inventory_item_id", sa.Integer(), nullable=True))
    op.add_column("purchase_orders", sa.Column("inventory_name", sa.String(220), nullable=True))
    op.add_column("purchase_orders", sa.Column("inventory_mode", sa.String(12), nullable=True))
    op.add_column("purchase_orders", sa.Column("inventory_serial", sa.String(120), nullable=True))
    op.add_column("purchase_orders", sa.Column("inventory_category", sa.String(80), nullable=True))
    op.add_column("purchase_orders", sa.Column("inventory_format_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_purchase_inventory_item", "purchase_orders", "inventory_items", ["inventory_item_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_purchase_inventory_format", "purchase_orders", "inventory_component_formats", ["inventory_format_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_purchase_orders_inventory_item_id", "purchase_orders", ["inventory_item_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade exige preservar os vínculos de Compras com Estoque.")
