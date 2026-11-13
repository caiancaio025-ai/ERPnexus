"""NF de garantia e inativação auditável de OS.

Revision ID: 20261027_01
Revises: 20261026_03
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20261027_01"
down_revision: str | None = "20261026_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("laboratory_work_orders", sa.Column("warranty_invoice", sa.String(80), nullable=True))
    op.create_index("ix_laboratory_work_orders_warranty_invoice", "laboratory_work_orders", ["warranty_invoice"])
    op.add_column("laboratory_work_orders", sa.Column("is_inactive", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_index("ix_laboratory_work_orders_is_inactive", "laboratory_work_orders", ["is_inactive"])
    op.add_column("laboratory_work_orders", sa.Column("inactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("inactivated_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_lab_wo_inactivated_by", "laboratory_work_orders", "users", ["inactivated_by"], ["id"])
    op.add_column("laboratory_work_orders", sa.Column("inactivation_reason", sa.String(500), nullable=True))

def downgrade() -> None:
    raise RuntimeError("A migração de inativação contém dados históricos; não reverter sem plano de recuperação.")
