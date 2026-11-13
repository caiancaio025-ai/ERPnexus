"""scope financial accounts by company

Revision ID: 20261007_01
Revises: 20260914_01
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261007_01"
down_revision: str | None = "20260914_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_accounts",
        sa.Column("company_code", sa.String(length=40), nullable=True),
    )

    # Preserva as contas histÃ³ricas jÃ¡ existentes e seus IDs.
    op.execute(
        """
        UPDATE financial_accounts
        SET company_code = 'universo_eletronica'
        WHERE company_code IS NULL
        """
    )

    op.alter_column(
        "financial_accounts",
        "company_code",
        existing_type=sa.String(length=40),
        nullable=False,
        server_default="universo_eletronica",
    )

    op.drop_constraint(
        "financial_accounts_name_key",
        "financial_accounts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_financial_accounts_company_name",
        "financial_accounts",
        ["company_code", "name"],
    )
    op.create_index(
        "ix_financial_accounts_company_code",
        "financial_accounts",
        ["company_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_accounts_company_code",
        table_name="financial_accounts",
    )
    op.drop_constraint(
        "uq_financial_accounts_company_name",
        "financial_accounts",
        type_="unique",
    )

    # O downgrade sÃ³ Ã© seguro se nÃ£o existirem nomes repetidos entre empresas.
    # Alembic/PostgreSQL abortarÃ£o a criaÃ§Ã£o da constraint em caso de conflito,
    # preservando os dados para reconciliaÃ§Ã£o manual.
    op.create_unique_constraint(
        "financial_accounts_name_key",
        "financial_accounts",
        ["name"],
    )
    op.drop_column("financial_accounts", "company_code")

