"""finance entry management and audit detail

Revision ID: 20260715_03
Revises: 20260715_02
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260715_03"
down_revision = "20260715_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_entries", sa.Column("invoice_type", sa.String(length=10), nullable=True))
    op.add_column("financial_entries", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("financial_entries", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_financial_entries_is_deleted", "financial_entries", ["is_deleted"])
    op.create_check_constraint("ck_financial_entries_invoice_type", "financial_entries", "invoice_type IS NULL OR invoice_type IN ('nfse', 'nfe')")
    op.add_column("financial_audit_events", sa.Column("before_data", sa.JSON(), nullable=True))
    op.add_column("financial_audit_events", sa.Column("after_data", sa.JSON(), nullable=True))
    op.create_index("ix_financial_audit_events_action", "financial_audit_events", ["action"])
    op.create_index("ix_financial_audit_events_created_at", "financial_audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_financial_audit_events_created_at", table_name="financial_audit_events")
    op.drop_index("ix_financial_audit_events_action", table_name="financial_audit_events")
    op.drop_column("financial_audit_events", "after_data")
    op.drop_column("financial_audit_events", "before_data")
    op.drop_constraint("ck_financial_entries_invoice_type", "financial_entries", type_="check")
    op.drop_index("ix_financial_entries_is_deleted", table_name="financial_entries")
    op.drop_column("financial_entries", "deleted_at")
    op.drop_column("financial_entries", "is_deleted")
    op.drop_column("financial_entries", "invoice_type")
