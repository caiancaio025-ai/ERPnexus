"""allow multiple work orders in same laboratory location

Revision ID: 20261009_01
Revises: 20261008_02
"""
from collections.abc import Sequence
from alembic import op
revision: str = "20261009_01"
down_revision: str | None = "20261008_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.drop_index("ix_laboratory_work_orders_storage_location", table_name="laboratory_work_orders")
    op.create_index("ix_laboratory_work_orders_storage_location", "laboratory_work_orders", ["storage_location"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_laboratory_work_orders_storage_location", table_name="laboratory_work_orders")
    op.create_index("ix_laboratory_work_orders_storage_location", "laboratory_work_orders", ["storage_location"], unique=True)
