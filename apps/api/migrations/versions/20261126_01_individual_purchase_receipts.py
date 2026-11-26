"""Permite receber varias unidades individuais sem duplicar a origem fisica.

Revision ID: 20261126_01
Revises: 20261123_02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_01"
down_revision: str | None = "20261123_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Cada recebimento historico continua sendo a unidade/entrada numero 1.
    # Nenhum saldo, custo, codigo de estoque ou vinculo existente e reescrito.
    op.add_column("inventory_movements", sa.Column(
        "receipt_unit_index", sa.Integer(), nullable=False, server_default="1",
    ))
    op.create_check_constraint("ck_inv_receipt_unit_positive", "inventory_movements", "receipt_unit_index > 0")
    op.drop_constraint("uq_inv_movements_purchase_once", "inventory_movements", type_="unique")
    op.drop_constraint("uq_inv_movements_request_once", "inventory_movements", type_="unique")
    op.create_unique_constraint("uq_inv_movements_purchase_unit", "inventory_movements", ["purchase_order_id", "receipt_unit_index"])
    op.create_unique_constraint("uq_inv_movements_request_unit", "inventory_movements", ["material_request_id", "receipt_unit_index"])


def downgrade() -> None:
    raise RuntimeError("Downgrade bloqueado: preserve os recebimentos individuais e seus vinculos de compras.")
