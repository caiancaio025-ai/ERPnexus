"""create purchasing module

Revision ID: 20260715_05
Revises: 20260715_04
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260715_05"
down_revision = "20260715_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="national"),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("contact_name", sa.String(length=150), nullable=True),
        sa.Column("contact_phone", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_purchase_suppliers_name"),
    )
    op.create_index("ix_purchase_suppliers_name", "purchase_suppliers", ["name"])
    op.create_index("ix_purchase_suppliers_is_active", "purchase_suppliers", ["is_active"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("purchase_suppliers.id"), nullable=False),
        sa.Column("supplier_name", sa.String(length=180), nullable=False),
        sa.Column("equipment_serial", sa.String(length=120), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("client_destination", sa.String(length=180), nullable=True),
        sa.Column("product_name", sa.String(length=250), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="national"),
        sa.Column("tracking_code", sa.String(length=120), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("estimated_delivery_date", sa.Date(), nullable=False),
        sa.Column("delivered_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="awaiting_payment"),
        sa.Column("product_link", sa.String(length=1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_path", sa.String(length=1000), nullable=True),
        sa.Column("attachment_mime", sa.String(length=100), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_purchase_orders_code"),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_orders_quantity_positive"),
        sa.CheckConstraint("total_amount > 0", name="ck_purchase_orders_amount_positive"),
    )
    for column in (
        "code", "company_code", "supplier_id", "equipment_serial", "invoice_number",
        "client_destination", "product_name", "tracking_code", "purchase_date",
        "estimated_delivery_date", "status", "is_deleted", "created_by",
    ):
        op.create_index(f"ix_purchase_orders_{column}", "purchase_orders", [column])

    op.create_table(
        "purchase_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_purchase_audit_events_purchase_id", "purchase_audit_events", ["purchase_id"])
    op.create_index("ix_purchase_audit_events_action", "purchase_audit_events", ["action"])
    op.create_index("ix_purchase_audit_events_user_id", "purchase_audit_events", ["user_id"])

    suppliers = sa.table(
        "purchase_suppliers",
        sa.column("name", sa.String),
        sa.column("origin", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        suppliers,
        [
            {"name": "AliExpress", "origin": "international", "is_active": True},
            {"name": "Mercado Livre", "origin": "national", "is_active": True},
        ],
    )


def downgrade() -> None:
    op.drop_table("purchase_audit_events")
    op.drop_table("purchase_orders")
    op.drop_table("purchase_suppliers")
