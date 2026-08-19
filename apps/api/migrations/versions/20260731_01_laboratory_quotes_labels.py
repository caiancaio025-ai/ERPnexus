"""create laboratory quotes

Revision ID: 20260731_01
Revises: 20260730_01
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260731_01"
down_revision: str | None = "20260730_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "laboratory_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("service_code", sa.String(50), nullable=False, server_default="3312102 / 14.01"),
        sa.Column("technical_report", sa.Text(), nullable=False),
        sa.Column("services_description", sa.Text()),
        sa.Column("delivery_days", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("billing_days", sa.Integer(), nullable=False, server_default="21"),
        sa.Column("warranty_months", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("payment_terms", sa.String(500), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("return_condition", sa.String(500), nullable=False),
        sa.Column("consumer_clause", sa.Text(), nullable=False),
        sa.Column("supply_clause", sa.Text(), nullable=False),
        sa.Column("estimate_clause", sa.Text(), nullable=False),
        sa.Column("discount_type", sa.String(20), nullable=False, server_default="none"),
        sa.Column("discount_value", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("emitted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("work_order_id", "revision", name="uq_lab_quote_work_order_revision"),
    )
    op.create_index("ix_laboratory_quotes_work_order_id", "laboratory_quotes", ["work_order_id"])
    op.create_index("ix_laboratory_quotes_status", "laboratory_quotes", ["status"])
    op.create_table(
        "laboratory_quote_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("laboratory_quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12,3), nullable=False, server_default="1"),
        sa.Column("unit_value", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_laboratory_quote_items_quote_id", "laboratory_quote_items", ["quote_id"])


def downgrade() -> None:
    op.drop_table("laboratory_quote_items")
    op.drop_table("laboratory_quotes")
