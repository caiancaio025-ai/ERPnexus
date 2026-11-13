"""Três notas de entrada e três de saída independentes na OS.

Revision ID: 20261027_03
Revises: 20261027_02

A primeira nota de entrada e saída preexistente é preservada sem alteração.
Notas de garantia da V9 permanecem intactas para consulta histórica.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_03"
down_revision: str | None = "20261027_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for prefix in ("entry_invoice", "exit_invoice"):
        for suffix in ("2", "3"):
            column = f"{prefix}_{suffix}"
            op.add_column("laboratory_work_orders", sa.Column(column, sa.String(80), nullable=True))
            op.create_index(f"ix_laboratory_work_orders_{column}", "laboratory_work_orders", [column])


def downgrade() -> None:
    raise RuntimeError("Não reverter sem backup: as NFs adicionais podem conter dados.")
