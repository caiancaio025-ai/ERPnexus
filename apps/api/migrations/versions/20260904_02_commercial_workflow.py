"""expand commercial workflow

Revision ID: 20260904_02
Revises: 20260904_01
Create Date: 2026-09-04
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260904_02"
down_revision: str | None = "20260904_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_company_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_code", sa.String(40), nullable=False),
        sa.Column("legal_name", sa.String(180), nullable=False),
        sa.Column("trade_name", sa.String(180)), sa.Column("document", sa.String(20)), sa.Column("state_registration", sa.String(30)),
        sa.Column("email", sa.String(180)), sa.Column("phone", sa.String(40)), sa.Column("address", sa.String(240)), sa.Column("city", sa.String(120)), sa.Column("state", sa.String(2)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_code", name="uq_commercial_company_profile_code"),
    )
    op.create_index("ix_commercial_company_profiles_company_code", "commercial_company_profiles", ["company_code"])
    op.create_index("ix_commercial_company_profiles_is_active", "commercial_company_profiles", ["is_active"])
    op.create_index("ix_commercial_company_profiles_created_by", "commercial_company_profiles", ["created_by"])

    with op.batch_alter_table("commercial_equipment") as batch:
        batch.add_column(sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("unit_cost", sa.Numeric(14,2), nullable=True))
        batch.add_column(sa.Column("sale_price", sa.Numeric(14,2), nullable=True))
        batch.add_column(sa.Column("rental_daily_price", sa.Numeric(14,2), nullable=True))
        batch.add_column(sa.Column("rental_monthly_price", sa.Numeric(14,2), nullable=True))
        batch.add_column(sa.Column("condition", sa.String(40), nullable=True))
        batch.add_column(sa.Column("stock_status", sa.String(30), nullable=False, server_default="available"))
        batch.add_column(sa.Column("location", sa.String(120), nullable=True))
        batch.add_column(sa.Column("acquisition_date", sa.Date(), nullable=True))
        batch.create_index("ix_commercial_equipment_stock_status", ["stock_status"])

    op.create_table(
        "commercial_quotes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("quote_number", sa.String(30)), sa.Column("quote_type", sa.String(20), nullable=False),
        sa.Column("company_code", sa.String(40), nullable=False), sa.Column("customer_id", sa.Integer(), sa.ForeignKey("laboratory_customers.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")), sa.Column("valid_until", sa.Date()), sa.Column("title", sa.String(220)),
        sa.Column("intro_text", sa.Text()), sa.Column("notes", sa.Text()), sa.Column("payment_terms", sa.Text()), sa.Column("delivery_terms", sa.Text()),
        sa.Column("warranty_terms", sa.Text()), sa.Column("rental_terms", sa.Text()), sa.Column("preventive_scope", sa.Text()), sa.Column("exclusions", sa.Text()),
        sa.Column("total", sa.Numeric(14,2), nullable=False, server_default="0"), sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("quote_number", "revision", name="uq_commercial_quote_number_revision"),
    )
    for name, cols in [("quote_number",["quote_number"]),("quote_type",["quote_type"]),("company_code",["company_code"]),("customer_id",["customer_id"]),("status",["status"]),("created_by",["created_by"])]:
        op.create_index(f"ix_commercial_quotes_{name}", "commercial_quotes", cols)

    op.create_table(
        "commercial_quote_items",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("quote_id", sa.Integer(), sa.ForeignKey("commercial_quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("commercial_equipment.id", ondelete="SET NULL")), sa.Column("description", sa.String(280), nullable=False),
        sa.Column("manufacturer", sa.String(120)), sa.Column("model", sa.String(160)), sa.Column("power", sa.String(80)), sa.Column("voltage", sa.String(80)), sa.Column("serial_number", sa.String(120)),
        sa.Column("quantity", sa.Numeric(12,2), nullable=False, server_default="1"), sa.Column("unit", sa.String(20), nullable=False, server_default="UN"), sa.Column("unit_price", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("discount_pct", sa.Numeric(7,4), nullable=False, server_default="0"), sa.Column("rental_period_count", sa.Integer()), sa.Column("rental_period_unit", sa.String(20)),
        sa.Column("line_total", sa.Numeric(14,2), nullable=False, server_default="0"), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_commercial_quote_items_quote_id", "commercial_quote_items", ["quote_id"])
    op.create_index("ix_commercial_quote_items_equipment_id", "commercial_quote_items", ["equipment_id"])

    op.create_table(
        "commercial_preventive_orders",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_number", sa.String(30)), sa.Column("quote_id", sa.Integer(), sa.ForeignKey("commercial_quotes.id", ondelete="SET NULL")),
        sa.Column("company_code", sa.String(40), nullable=False), sa.Column("customer_id", sa.Integer(), sa.ForeignKey("laboratory_customers.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"), sa.Column("scheduled_date", sa.Date()), sa.Column("completed_date", sa.Date()), sa.Column("technical_notes", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("order_number", name="uq_commercial_preventive_order_number"),
    )
    for name, cols in [("order_number",["order_number"]),("quote_id",["quote_id"]),("company_code",["company_code"]),("customer_id",["customer_id"]),("status",["status"]),("created_by",["created_by"])]:
        op.create_index(f"ix_commercial_preventive_orders_{name}", "commercial_preventive_orders", cols)


def downgrade() -> None:
    op.drop_table("commercial_preventive_orders")
    op.drop_table("commercial_quote_items")
    op.drop_table("commercial_quotes")
    with op.batch_alter_table("commercial_equipment") as batch:
        batch.drop_index("ix_commercial_equipment_stock_status")
        for col in ["acquisition_date","location","stock_status","condition","rental_monthly_price","rental_daily_price","sale_price","unit_cost","quantity"]:
            batch.drop_column(col)
    op.drop_table("commercial_company_profiles")
