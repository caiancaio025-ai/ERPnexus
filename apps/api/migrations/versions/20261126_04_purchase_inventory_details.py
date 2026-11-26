"""Preserva o cadastro planejado do estoque em pedidos e solicitações.

Revision ID: 20261126_04
Revises: 20261126_03
"""
from alembic import op
import sqlalchemy as sa

revision = "20261126_04"
down_revision = "20261126_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("inventory_details", sa.JSON(), nullable=True))
    op.add_column("material_requests", sa.Column("inventory_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Downgrade bloqueado: preserve os detalhes de estoque salvos nas compras e solicitações.")
