"""split invoice numbers into NFS-e and NF-e fields

Revision ID: 20260715_04
Revises: 20260715_03
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260715_04"
down_revision = "20260715_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_entries",
        sa.Column("nfse_number", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "financial_entries",
        sa.Column("nfe_number", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_financial_entries_nfse_number",
        "financial_entries",
        ["nfse_number"],
        unique=False,
    )
    op.create_index(
        "ix_financial_entries_nfe_number",
        "financial_entries",
        ["nfe_number"],
        unique=False,
    )
    op.execute(
        """
        UPDATE financial_entries
        SET nfse_number = document_number
        WHERE entry_type = 'income'
          AND invoice_type = 'nfse'
          AND document_number IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE financial_entries
        SET nfe_number = document_number
        WHERE entry_type = 'income'
          AND invoice_type = 'nfe'
          AND document_number IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE financial_entries
        SET document_number = COALESCE(nfse_number, nfe_number)
        WHERE entry_type = 'income'
        """
    )
    op.drop_index("ix_financial_entries_nfe_number", table_name="financial_entries")
    op.drop_index("ix_financial_entries_nfse_number", table_name="financial_entries")
    op.drop_column("financial_entries", "nfe_number")
    op.drop_column("financial_entries", "nfse_number")
