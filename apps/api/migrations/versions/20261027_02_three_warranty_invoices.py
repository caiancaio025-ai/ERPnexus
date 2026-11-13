"""Três campos independentes para notas fiscais de garantia na OS.

Revision ID: 20261027_02
Revises: 20261027_01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_02"
down_revision: str | None = "20261027_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # O campo warranty_invoice anterior permanece intacto: passa a ser Garantia 1.
    for suffix in ("2", "3"):
        column = f"warranty_invoice_{suffix}"
        op.add_column("laboratory_work_orders", sa.Column(column, sa.String(80), nullable=True))
        op.create_index(f"ix_laboratory_work_orders_{column}", "laboratory_work_orders", [column])


def downgrade() -> None:
    raise RuntimeError("Não reverter sem backup: as notas de garantia 2 e 3 podem conter dados.")
