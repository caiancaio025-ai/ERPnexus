"""create finance module

Revision ID: 20260715_01
Revises: 20260714_02
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_01"
down_revision: str | None = "20260714_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False, server_default="bank"),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "financial_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "financial_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=180), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("financial_accounts.id"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("financial_categories.id"), nullable=True),
        sa.Column("document_number", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_financial_entries_entry_type", "financial_entries", ["entry_type"])
    op.create_index("ix_financial_entries_due_date", "financial_entries", ["due_date"])
    op.create_index("ix_financial_entries_status", "financial_entries", ["status"])
    op.create_index("ix_financial_entries_created_by", "financial_entries", ["created_by"])

    op.create_table(
        "financial_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_account_id", sa.Integer(), sa.ForeignKey("financial_accounts.id"), nullable=False),
        sa.Column("destination_account_id", sa.Integer(), sa.ForeignKey("financial_accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_financial_transfers_transfer_date", "financial_transfers", ["transfer_date"])
    op.create_index("ix_financial_transfers_created_by", "financial_transfers", ["created_by"])

    op.create_table(
        "financial_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=280), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_financial_audit_events_entity_type", "financial_audit_events", ["entity_type"])
    op.create_index("ix_financial_audit_events_entity_id", "financial_audit_events", ["entity_id"])
    op.create_index("ix_financial_audit_events_user_id", "financial_audit_events", ["user_id"])

    op.bulk_insert(
        sa.table(
            "financial_accounts",
            sa.column("name", sa.String),
            sa.column("account_type", sa.String),
            sa.column("opening_balance", sa.Numeric),
        ),
        [
            {"name": "Conta principal", "account_type": "bank", "opening_balance": 0},
            {"name": "Caixa interno", "account_type": "cash", "opening_balance": 0},
        ],
    )
    op.bulk_insert(
        sa.table(
            "financial_categories",
            sa.column("name", sa.String),
            sa.column("entry_type", sa.String),
        ),
        [
            {"name": "Serviços", "entry_type": "income"},
            {"name": "Venda de equipamentos", "entry_type": "income"},
            {"name": "Fornecedores", "entry_type": "expense"},
            {"name": "Despesas operacionais", "entry_type": "expense"},
        ],
    )


def downgrade() -> None:
    op.drop_table("financial_audit_events")
    op.drop_table("financial_transfers")
    op.drop_table("financial_entries")
    op.drop_table("financial_categories")
    op.drop_table("financial_accounts")
