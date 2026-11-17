"""Central de atividades internas estruturada e filtrável.

Revision ID: 20261117_01
Revises: 20261116_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_01"
down_revision = "20261116_01"
branch_labels = None
depends_on = None

COLUMNS = {
    "activity_module": sa.Column("activity_module", sa.String(40), nullable=True),
    "action": sa.Column("action", sa.String(60), nullable=True),
    "actor_user_id": sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    "actor_name": sa.Column("actor_name", sa.String(120), nullable=True),
    "work_order_number": sa.Column("work_order_number", sa.String(40), nullable=True),
    "equipment_name": sa.Column("equipment_name", sa.String(250), nullable=True),
    "details": sa.Column("details", sa.Text(), nullable=True),
}
INDEXED = ("activity_module", "action", "actor_user_id", "work_order_number")


def upgrade():
    for column in COLUMNS.values():
        op.add_column("notifications", column)
    for name in INDEXED:
        op.create_index(f"ix_notifications_{name}", "notifications", [name])
    # Classifica apenas categorias anteriores reconhecidas.
    op.execute(sa.text("""UPDATE notifications SET activity_module = CASE
      WHEN category IN ('quote', 'commercial_sale_approved') THEN 'orcamentos'
      WHEN category IN ('purchase', 'purchase_request', 'material_request_approved') THEN 'compras'
      WHEN category IN ('finance', 'financeiro', 'billing') THEN 'financeiro'
      ELSE NULL END WHERE activity_module IS NULL"""))
    op.execute(sa.text("UPDATE notifications SET push_processed_at = CURRENT_TIMESTAMP WHERE push_processed_at IS NULL"))


def downgrade():
    for name in reversed(INDEXED):
        op.drop_index(f"ix_notifications_{name}", table_name="notifications")
    for name in reversed(tuple(COLUMNS)):
        op.drop_column("notifications", name)
