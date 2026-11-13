"""allow standalone material requests

Revision ID: 20260821_02
Revises: 20260821_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260821_02"
down_revision = "20260821_01"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("material_requests", sa.Column("source_type", sa.String(length=30), nullable=False, server_default="work_order"))
    op.create_index("ix_material_requests_source_type", "material_requests", ["source_type"])
    op.drop_constraint("material_requests_work_order_id_fkey", "material_requests", type_="foreignkey")
    op.drop_constraint("material_requests_equipment_id_fkey", "material_requests", type_="foreignkey")
    op.alter_column("material_requests", "work_order_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("material_requests", "equipment_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key("material_requests_work_order_id_fkey", "material_requests", "laboratory_work_orders", ["work_order_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("material_requests_equipment_id_fkey", "material_requests", "laboratory_equipment", ["equipment_id"], ["id"], ondelete="SET NULL")

def downgrade() -> None:
    op.execute("DELETE FROM material_requests WHERE work_order_id IS NULL OR equipment_id IS NULL")
    op.drop_constraint("material_requests_work_order_id_fkey", "material_requests", type_="foreignkey")
    op.drop_constraint("material_requests_equipment_id_fkey", "material_requests", type_="foreignkey")
    op.alter_column("material_requests", "equipment_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("material_requests", "work_order_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key("material_requests_work_order_id_fkey", "material_requests", "laboratory_work_orders", ["work_order_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("material_requests_equipment_id_fkey", "material_requests", "laboratory_equipment", ["equipment_id"], ["id"], ondelete="CASCADE")
    op.drop_index("ix_material_requests_source_type", table_name="material_requests")
    op.drop_column("material_requests", "source_type")
