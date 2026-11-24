"""Chaves NF-e de entrada e saida independentes para cada garantia.

Revision ID: 20261123_01
Revises: 20261117_01

Apenas colunas opcionais (44 digitos); nenhuma NF antiga e removida ou sobrescrita.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261123_01"
down_revision = "20261117_01"
branch_labels = None
depends_on = None

COLUMNS = (
    "warranty_entry_invoice_access_key_1", "warranty_exit_invoice_access_key_1",
    "warranty_entry_invoice_access_key_2", "warranty_exit_invoice_access_key_2",
    "warranty_entry_invoice_access_key_3", "warranty_exit_invoice_access_key_3",
)


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column("laboratory_work_orders", sa.Column(name, sa.String(44), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Nao reverter sem backup: as chaves NF-e de garantia podem conter dados.")
