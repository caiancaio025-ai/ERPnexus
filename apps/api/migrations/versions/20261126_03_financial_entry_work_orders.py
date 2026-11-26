"""Várias OS no mesmo título financeiro, preservando receitas e baixas existentes."""
import sqlalchemy as sa
from alembic import op

revision = "20261126_03"
down_revision = "20261126_02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("financial_entries", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("financial_obligations", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("financial_entry_work_orders",
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("financial_entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("laboratory_work_orders.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("billing_compliance", sa.JSON(), nullable=True),
        sa.CheckConstraint("amount >= 0", name="ck_fin_entry_os_amount_nonnegative"),
    )
    op.create_index("ix_financial_entry_work_orders_work_order_id", "financial_entry_work_orders", ["work_order_id"])
    # O vínculo singular histórico permanece intacto. A projeção de leitura usa
    # fallback somente quando o título ainda não possui rateio nesta tabela.


def downgrade():
    raise RuntimeError("Downgrade bloqueado: preserve os rateios das receitas e seu histórico financeiro.")
