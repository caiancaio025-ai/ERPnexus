"""create laboratory module

Revision ID: 20260729_01
Revises: 20260727_01
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260729_01"
down_revision = "20260727_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE laboratory_work_order_number_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "laboratory_equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_code", sa.String(40), nullable=False),
        sa.Column("customer_name", sa.String(180), nullable=False),
        sa.Column("serial_number", sa.String(120), nullable=False),
        sa.Column("serial_normalized", sa.String(120), nullable=False),
        sa.Column("manufacturer", sa.String(120), nullable=True),
        sa.Column("model", sa.String(160), nullable=True),
        sa.Column("equipment_type", sa.String(120), nullable=True),
        sa.Column("power", sa.String(80), nullable=True),
        sa.Column("voltage", sa.String(80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_code", "serial_normalized", name="uq_laboratory_equipment_company_serial"
        ),
    )
    for column in (
        "company_code", "customer_name", "serial_normalized", "manufacturer", "model",
        "equipment_type", "is_active", "created_by",
    ):
        op.create_index(f"ix_laboratory_equipment_{column}", "laboratory_equipment", [column])

    op.create_table(
        "laboratory_work_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("company_code", sa.String(40), nullable=False),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("laboratory_equipment.id"), nullable=False),
        sa.Column("customer_name", sa.String(180), nullable=False),
        sa.Column("equipment_serial", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="received"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("reported_defect", sa.Text(), nullable=False),
        sa.Column("entry_condition", sa.Text(), nullable=True),
        sa.Column("accessories_received", sa.Text(), nullable=True),
        sa.Column("assigned_technician_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("opened_at", sa.Date(), nullable=False),
        sa.Column("expected_completion_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("number", name="uq_laboratory_work_orders_number"),
        sa.CheckConstraint("version > 0", name="ck_laboratory_work_orders_version_positive"),
    )
    for column in (
        "number", "company_code", "equipment_id", "customer_name", "equipment_serial", "status",
        "priority", "assigned_technician_id", "opened_at", "expected_completion_date",
        "is_cancelled", "created_by",
    ):
        op.create_index(f"ix_laboratory_work_orders_{column}", "laboratory_work_orders", [column])

    op.create_table(
        "laboratory_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_order_id", sa.Integer(),
            sa.ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("previous_status", sa.String(40), nullable=True),
        sa.Column("new_status", sa.String(40), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_laboratory_status_history_work_order_id", "laboratory_status_history", ["work_order_id"])
    op.create_index("ix_laboratory_status_history_new_status", "laboratory_status_history", ["new_status"])
    op.create_index("ix_laboratory_status_history_user_id", "laboratory_status_history", ["user_id"])

    op.create_table(
        "laboratory_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_order_id", sa.Integer(),
            sa.ForeignKey("laboratory_work_orders.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_laboratory_audit_events_work_order_id", "laboratory_audit_events", ["work_order_id"])
    op.create_index("ix_laboratory_audit_events_action", "laboratory_audit_events", ["action"])
    op.create_index("ix_laboratory_audit_events_user_id", "laboratory_audit_events", ["user_id"])

    op.add_column("purchase_orders", sa.Column("laboratory_equipment_id", sa.Integer(), nullable=True))
    op.add_column("purchase_orders", sa.Column("laboratory_work_order_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_purchase_orders_laboratory_equipment_id",
        "purchase_orders", "laboratory_equipment", ["laboratory_equipment_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_purchase_orders_laboratory_work_order_id",
        "purchase_orders", "laboratory_work_orders", ["laboratory_work_order_id"], ["id"],
    )
    op.create_index("ix_purchase_orders_laboratory_equipment_id", "purchase_orders", ["laboratory_equipment_id"])
    op.create_index("ix_purchase_orders_laboratory_work_order_id", "purchase_orders", ["laboratory_work_order_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_orders_laboratory_work_order_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_laboratory_equipment_id", table_name="purchase_orders")
    op.drop_constraint("fk_purchase_orders_laboratory_work_order_id", "purchase_orders", type_="foreignkey")
    op.drop_constraint("fk_purchase_orders_laboratory_equipment_id", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "laboratory_work_order_id")
    op.drop_column("purchase_orders", "laboratory_equipment_id")
    op.drop_table("laboratory_audit_events")
    op.drop_table("laboratory_status_history")
    op.drop_table("laboratory_work_orders")
    op.drop_table("laboratory_equipment")
    op.execute("DROP SEQUENCE laboratory_work_order_number_seq")
