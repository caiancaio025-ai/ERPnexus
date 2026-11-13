"""material request flow

Revision ID: 20260818_01
Revises: 20260817_01
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20260818_01"
down_revision: str | None = "20260817_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("requester_user_id", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(length=250), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("technical_note", sa.Text(), nullable=True),
        sa.Column("suggested_link", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="awaiting_approval"),
        sa.Column("supplier_name", sa.String(length=180), nullable=True),
        sa.Column("purchase_reference", sa.String(length=100), nullable=True),
        sa.Column("purchase_link", sa.String(length=1000), nullable=True),
        sa.Column("tracking_code", sa.String(length=120), nullable=True),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["laboratory_work_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["equipment_id"], ["laboratory_equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("code"),
    )
    for column in ("code", "company_code", "work_order_id", "equipment_id", "requester_user_id", "item_name", "priority", "status", "approved_by", "updated_by"):
        op.create_index(f"ix_material_requests_{column}", "material_requests", [column])

    op.create_table(
        "material_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_request_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["material_request_id"], ["material_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    for column in ("material_request_id", "event_type", "new_status", "user_id"):
        op.create_index(f"ix_material_request_events_{column}", "material_request_events", [column])


def downgrade() -> None:
    op.drop_table("material_request_events")
    op.drop_table("material_requests")
