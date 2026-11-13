"""notifications and billing compliance foundation

Revision ID: 20260818_02
Revises: 20260818_01
Create Date: 2026-08-18
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260818_02"
down_revision: str | None = "20260818_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("financial_entries", sa.Column("billing_compliance", sa.JSON(), nullable=True))

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("target", sa.String(length=500), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("laboratory_work_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("user_id", "category", "severity", "entity_type", "entity_id", "work_order_id", "is_read", "created_at"):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])


def downgrade() -> None:
    for column in reversed(("user_id", "category", "severity", "entity_type", "entity_id", "work_order_id", "is_read", "created_at")):
        op.drop_index(f"ix_notifications_{column}", table_name="notifications")
    op.drop_table("notifications")
    op.drop_column("financial_entries", "billing_compliance")
