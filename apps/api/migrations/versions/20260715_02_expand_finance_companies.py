"""expand finance entries for companies and banking details

Revision ID: 20260715_02
Revises: 20260715_01
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_02"
down_revision: str | None = "20260715_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("financial_entries", sa.Column("company_code", sa.String(length=40), nullable=True))
    op.add_column("financial_entries", sa.Column("series", sa.String(length=40), nullable=True))
    op.add_column("financial_entries", sa.Column("counterparty_name", sa.String(length=180), nullable=True))
    op.add_column("financial_entries", sa.Column("issue_date", sa.Date(), nullable=True))
    op.add_column("financial_entries", sa.Column("posting_date", sa.Date(), nullable=True))
    op.add_column("financial_entries", sa.Column("bank_name", sa.String(length=80), nullable=True))
    op.add_column("financial_entries", sa.Column("expense_kind", sa.String(length=30), nullable=True))
    op.add_column("financial_entries", sa.Column("payment_code", sa.Text(), nullable=True))
    op.add_column("financial_entries", sa.Column("attachment_name", sa.String(length=255), nullable=True))
    op.add_column("financial_entries", sa.Column("attachment_path", sa.String(length=500), nullable=True))
    op.add_column("financial_entries", sa.Column("attachment_mime", sa.String(length=100), nullable=True))

    op.execute("""
        UPDATE financial_entries
        SET company_code = 'universo_eletronica',
            counterparty_name = COALESCE(description, 'Não informado'),
            issue_date = due_date,
            posting_date = COALESCE(created_at::date, due_date),
            bank_name = 'Bradesco'
        WHERE company_code IS NULL
    """)

    op.alter_column("financial_entries", "company_code", nullable=False, server_default="universo_eletronica")
    op.alter_column("financial_entries", "counterparty_name", nullable=False)
    op.alter_column("financial_entries", "issue_date", nullable=False)
    op.alter_column("financial_entries", "posting_date", nullable=False)
    op.alter_column("financial_entries", "bank_name", nullable=False)

    op.create_index("ix_financial_entries_company_code", "financial_entries", ["company_code"])
    op.create_index("ix_financial_entries_posting_date", "financial_entries", ["posting_date"])
    op.create_index("ix_financial_entries_expense_kind", "financial_entries", ["expense_kind"])


def downgrade() -> None:
    op.drop_index("ix_financial_entries_expense_kind", table_name="financial_entries")
    op.drop_index("ix_financial_entries_posting_date", table_name="financial_entries")
    op.drop_index("ix_financial_entries_company_code", table_name="financial_entries")
    for column in (
        "attachment_mime", "attachment_path", "attachment_name", "payment_code", "expense_kind",
        "bank_name", "posting_date", "issue_date", "counterparty_name", "series", "company_code",
    ):
        op.drop_column("financial_entries", column)
