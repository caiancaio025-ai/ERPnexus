"""add finance idempotency keys

Revision ID: 20260827_01
Revises: 20260821_02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827_01"
down_revision = "20260821_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_entries",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "financial_entries",
        sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_financial_entries_idempotency_key",
        "financial_entries",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_financial_entries_idempotency_key", table_name="financial_entries")
    op.drop_column("financial_entries", "idempotency_fingerprint")
    op.drop_column("financial_entries", "idempotency_key")
