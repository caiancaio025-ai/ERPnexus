"""link financial entries to laboratory work orders

Revision ID: 20260811_02
Revises: 20260811_01
Create Date: 2026-08-11

Adiciona financial_entries.work_order_id, para que um titulo a receber
gerado a partir da aprovacao de uma O.S. fique rastreavel ate ela. O valor
usado e o laboratory_work_orders.approved_value ja existente -- nao ha
necessidade de nenhum campo novo de valor na O.S.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_02"
down_revision: str | None = "20260811_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_entries",
        sa.Column(
            "work_order_id",
            sa.Integer(),
            sa.ForeignKey("laboratory_work_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_financial_entries_work_order_id", "financial_entries", ["work_order_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_financial_entries_work_order_id", table_name="financial_entries")
    op.drop_column("financial_entries", "work_order_id")
