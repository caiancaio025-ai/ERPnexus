"""NFs comuns independentes de tres pares de NFs de garantia.

Revision ID: 20261027_04
Revises: 20261027_03

Preserva as colunas e dados legados das V9/V10 sem reclassificacao automatica.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_04"
down_revision: str | None = "20261027_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for kind in ("entry", "exit"):
        for number in (1, 2, 3):
            name = f"warranty_{kind}_invoice_{number}"
            op.add_column("laboratory_work_orders", sa.Column(name, sa.String(80), nullable=True))
            op.create_index(f"ix_laboratory_work_orders_{name}", "laboratory_work_orders", [name])


def downgrade() -> None:
    raise RuntimeError("Nao reverter sem backup: NFs de garantia podem conter dados.")
