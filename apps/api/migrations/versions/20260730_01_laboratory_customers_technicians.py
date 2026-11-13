"""laboratory customers technicians and operational fields

Revision ID: 20260730_01
Revises: 20260729_01
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa

revision = "20260730_01"
down_revision = "20260729_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "laboratory_customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_code", sa.String(40), nullable=False),
        sa.Column("document", sa.String(20), nullable=True),
        sa.Column("legal_name", sa.String(180), nullable=False),
        sa.Column("trade_name", sa.String(180), nullable=True),
        sa.Column("state_registration", sa.String(30), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("whatsapp", sa.String(40), nullable=True),
        sa.Column("email", sa.String(180), nullable=True),
        sa.Column("postal_code", sa.String(12), nullable=True),
        sa.Column("address", sa.String(220), nullable=True),
        sa.Column("address_number", sa.String(30), nullable=True),
        sa.Column("complement", sa.String(120), nullable=True),
        sa.Column("district", sa.String(120), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("company_code", "document", name="uq_lab_customer_company_document"),
    )
    for column in ("company_code", "document", "legal_name", "trade_name", "email", "is_active", "created_by"):
        op.create_index(f"ix_laboratory_customers_{column}", "laboratory_customers", [column])

    op.create_table(
        "laboratory_technicians",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("specialty", sa.String(180), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(180), nullable=True),
        sa.Column("color", sa.String(12), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("company_code", "name", "email", "user_id", "is_active", "created_by"):
        op.create_index(f"ix_laboratory_technicians_{column}", "laboratory_technicians", [column])

    op.add_column("laboratory_equipment", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_lab_equipment_customer", "laboratory_equipment", "laboratory_customers", ["customer_id"], ["id"])
    op.create_index("ix_laboratory_equipment_customer_id", "laboratory_equipment", ["customer_id"])
    op.alter_column("laboratory_equipment", "serial_number", existing_type=sa.String(120), nullable=True)
    op.alter_column("laboratory_equipment", "serial_normalized", existing_type=sa.String(120), nullable=True)

    op.add_column("laboratory_work_orders", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("entry_invoice", sa.String(80), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("exit_invoice", sa.String(80), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("parts_cost", sa.Numeric(14, 2), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("quoted_value", sa.Numeric(14, 2), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("approved_value", sa.Numeric(14, 2), nullable=True))
    op.create_foreign_key("fk_lab_work_order_customer", "laboratory_work_orders", "laboratory_customers", ["customer_id"], ["id"])
    op.create_index("ix_laboratory_work_orders_customer_id", "laboratory_work_orders", ["customer_id"])
    op.create_index("ix_laboratory_work_orders_entry_invoice", "laboratory_work_orders", ["entry_invoice"])
    op.create_index("ix_laboratory_work_orders_exit_invoice", "laboratory_work_orders", ["exit_invoice"])
    op.alter_column("laboratory_work_orders", "equipment_serial", existing_type=sa.String(120), nullable=True)

    op.drop_constraint("laboratory_work_orders_assigned_technician_id_fkey", "laboratory_work_orders", type_="foreignkey")
    op.create_foreign_key(
        "fk_lab_work_order_technician", "laboratory_work_orders", "laboratory_technicians",
        ["assigned_technician_id"], ["id"]
    )
    op.drop_column("laboratory_work_orders", "expected_completion_date")

    # Converte números temporários como OS-2026-000001 para OS-0001.
    op.execute("""
        UPDATE laboratory_work_orders
        SET number = 'OS-' || lpad((regexp_match(number, '(\\d+)$'))[1]::bigint::text, 4, '0')
        WHERE number ~ '\\d+$'
    """)
    op.execute("""
        SELECT setval(
            'laboratory_work_order_number_seq',
            GREATEST(
                COALESCE((SELECT MAX((regexp_match(number, '(\\d+)$'))[1]::bigint) FROM laboratory_work_orders), 0),
                1
            ),
            EXISTS (SELECT 1 FROM laboratory_work_orders)
        )
    """)


def downgrade() -> None:
    op.add_column("laboratory_work_orders", sa.Column("expected_completion_date", sa.Date(), nullable=True))
    op.drop_constraint("fk_lab_work_order_technician", "laboratory_work_orders", type_="foreignkey")
    op.create_foreign_key("laboratory_work_orders_assigned_technician_id_fkey", "laboratory_work_orders", "users", ["assigned_technician_id"], ["id"])
    for column in ("exit_invoice", "entry_invoice", "customer_id"):
        op.drop_index(f"ix_laboratory_work_orders_{column}", table_name="laboratory_work_orders")
    op.drop_constraint("fk_lab_work_order_customer", "laboratory_work_orders", type_="foreignkey")
    for column in ("approved_value", "quoted_value", "parts_cost", "exit_invoice", "entry_invoice", "customer_id"):
        op.drop_column("laboratory_work_orders", column)
    op.drop_index("ix_laboratory_equipment_customer_id", table_name="laboratory_equipment")
    op.drop_constraint("fk_lab_equipment_customer", "laboratory_equipment", type_="foreignkey")
    op.drop_column("laboratory_equipment", "customer_id")
    op.drop_table("laboratory_technicians")
    op.drop_table("laboratory_customers")
