"""add native finance obligations and installments

Revision ID: 20261007_02
Revises: 20261007_01
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261007_02"
down_revision: str | None = "20261007_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_obligations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("invoice_type", sa.String(length=10), nullable=True),
        sa.Column("series", sa.String(length=40), nullable=True),
        sa.Column("nfse_number", sa.String(length=80), nullable=True),
        sa.Column("nfe_number", sa.String(length=80), nullable=True),
        sa.Column("counterparty_name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=180), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("installment_count", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=False),
        sa.Column("bank_name", sa.String(length=80), nullable=False),
        sa.Column("expense_kind", sa.String(length=30), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("document_number", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("work_order_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "installment_count > 0",
            name="ck_financial_obligations_installment_count_positive",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["financial_accounts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["financial_categories.id"]),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["laboratory_work_orders.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_financial_obligations_idempotency_key",
        ),
    )
    op.create_index(
        op.f("ix_financial_obligations_company_code"),
        "financial_obligations",
        ["company_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_obligations_entry_type"),
        "financial_obligations",
        ["entry_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_obligations_nfse_number"),
        "financial_obligations",
        ["nfse_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_obligations_nfe_number"),
        "financial_obligations",
        ["nfe_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_obligations_posting_date"),
        "financial_obligations",
        ["posting_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_obligations_expense_kind"),
        "financial_obligations",
        ["expense_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_obligations_work_order_id"),
        "financial_obligations",
        ["work_order_id"],
        unique=False,
    )

    op.add_column(
        "financial_entries",
        sa.Column("obligation_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "financial_entries",
        sa.Column("installment_number", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_financial_entries_obligation_id",
        "financial_entries",
        "financial_obligations",
        ["obligation_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_financial_entries_installment_number_positive",
        "financial_entries",
        "installment_number IS NULL OR installment_number > 0",
    )
    op.create_unique_constraint(
        "uq_financial_entries_obligation_installment",
        "financial_entries",
        ["obligation_id", "installment_number"],
    )
    op.create_index(
        op.f("ix_financial_entries_obligation_id"),
        "financial_entries",
        ["obligation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_financial_entries_obligation_id"),
        table_name="financial_entries",
    )
    op.drop_constraint(
        "uq_financial_entries_obligation_installment",
        "financial_entries",
        type_="unique",
    )
    op.drop_constraint(
        "ck_financial_entries_installment_number_positive",
        "financial_entries",
        type_="check",
    )
    op.drop_constraint(
        "fk_financial_entries_obligation_id",
        "financial_entries",
        type_="foreignkey",
    )
    op.drop_column("financial_entries", "installment_number")
    op.drop_column("financial_entries", "obligation_id")

    op.drop_index(
        op.f("ix_financial_obligations_work_order_id"),
        table_name="financial_obligations",
    )
    op.drop_index(
        op.f("ix_financial_obligations_expense_kind"),
        table_name="financial_obligations",
    )
    op.drop_index(
        op.f("ix_financial_obligations_posting_date"),
        table_name="financial_obligations",
    )
    op.drop_index(
        op.f("ix_financial_obligations_nfe_number"),
        table_name="financial_obligations",
    )
    op.drop_index(
        op.f("ix_financial_obligations_nfse_number"),
        table_name="financial_obligations",
    )
    op.drop_index(
        op.f("ix_financial_obligations_entry_type"),
        table_name="financial_obligations",
    )
    op.drop_index(
        op.f("ix_financial_obligations_company_code"),
        table_name="financial_obligations",
    )
    op.drop_table("financial_obligations")
