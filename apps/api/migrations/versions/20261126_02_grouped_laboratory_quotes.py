"""Orçamentos conjuntos com revisões e identidade/valores preservados por OS.

Revision ID: 20261126_02
Revises: 20261126_01
"""
import sqlalchemy as sa
from alembic import op

revision = "20261126_02"
down_revision = "20261126_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("laboratory_quote_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("company_code", sa.String(40), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("laboratory_customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_name", sa.String(180), nullable=False),
        sa.Column("creation_key", sa.String(128)),
        sa.Column("creation_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("created_by", "creation_key", name="uq_lab_quote_group_creation_key"),
    )
    op.create_table("laboratory_grouped_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("laboratory_quote_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("document_snapshot", sa.JSON()),
        sa.Column("pdf_content", sa.LargeBinary()),
        sa.Column("pdf_sha256", sa.String(64)),
        sa.Column("emitted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "revision", name="uq_lab_grouped_quote_revision"),
        sa.CheckConstraint("revision > 0 AND version > 0", name="ck_lab_grouped_quote_version"),
        sa.CheckConstraint("status IN ('draft','emitted')", name="ck_lab_grouped_quote_status"),
        sa.CheckConstraint("subtotal >= 0 AND discount_amount >= 0 AND total >= 0 AND total = subtotal - discount_amount", name="ck_lab_grouped_quote_totals"),
    )
    op.create_table("laboratory_grouped_quote_work_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("laboratory_grouped_quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("laboratory_work_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("quote_id", "work_order_id", name="uq_lab_grouped_quote_os"),
        sa.UniqueConstraint("quote_id", "position", name="uq_lab_grouped_quote_os_position"),
        sa.CheckConstraint("position > 0", name="ck_lab_grouped_quote_os_position"),
        sa.CheckConstraint("subtotal >= 0 AND discount_amount >= 0 AND total >= 0 AND total = subtotal - discount_amount", name="ck_lab_grouped_quote_os_totals"),
    )
    op.create_table("laboratory_grouped_quote_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("laboratory_grouped_quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_value", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["quote_id", "work_order_id"], ["laboratory_grouped_quote_work_orders.quote_id", "laboratory_grouped_quote_work_orders.work_order_id"], ondelete="CASCADE", name="fk_lab_grouped_quote_item_os"),
        sa.UniqueConstraint("quote_id", "position", name="uq_lab_grouped_quote_item_position"),
        sa.CheckConstraint("position > 0 AND quantity > 0 AND unit_value >= 0", name="ck_lab_grouped_quote_item_values"),
    )
    for table, columns in {
        "laboratory_quote_groups": ["company_code", "customer_id"],
        "laboratory_grouped_quotes": ["group_id", "status"],
        "laboratory_grouped_quote_work_orders": ["quote_id", "work_order_id"],
        "laboratory_grouped_quote_items": ["quote_id", "work_order_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    raise RuntimeError("Downgrade bloqueado: preserve orçamentos conjuntos, revisões e documentos emitidos.")
