"""Cliente atual da locação na etiqueta patrimonial.

Revision ID: 20261028_01
Revises: 20261027_05
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20261028_01"
down_revision: str | None = "20261027_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("commercial_equipment", sa.Column("rental_customer_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_commercial_equipment_rental_customer", "commercial_equipment", "laboratory_customers", ["rental_customer_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_commercial_equipment_rental_customer_id", "commercial_equipment", ["rental_customer_id"])


def downgrade() -> None:
    op.drop_index("ix_commercial_equipment_rental_customer_id", table_name="commercial_equipment")
    op.drop_constraint("fk_commercial_equipment_rental_customer", "commercial_equipment", type_="foreignkey")
    op.drop_column("commercial_equipment", "rental_customer_id")
