"""Codigos curtos EST: EST-01 ... EST-99, EST-100 etc.

Revision ID: 20261027_05
Revises: 20261027_04

Atualiza somente as etiquetas que seguem o padrao historico EST + ID.
Sem apagar itens, series de fabricante, movimentos ou historico. Os QR antigos
continuam pesquisaveis pelo ID canonico. Exige backup antes de aplicar.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20261027_05"
down_revision: str | None = "20261027_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotente em reexecucoes; nao toca etiquetas personalizadas ou que
    # nao correspondam ao ID real. EST-01 ... EST-09; EST-10, EST-100...
    op.execute("""
        UPDATE inventory_items AS item
        SET stock_code = 'EST-' || CASE WHEN item.id < 10 THEN '0' || item.id::text ELSE item.id::text END
        WHERE CASE
            WHEN item.stock_code ~ '^EST-[0-9]{3,12}$'
            THEN substring(item.stock_code from 5)::bigint = item.id
            ELSE FALSE
          END
          AND NOT EXISTS (
              SELECT 1 FROM inventory_items AS other
              WHERE other.stock_code = 'EST-' || CASE WHEN item.id < 10 THEN '0' || item.id::text ELSE item.id::text END
                AND other.id <> item.id
          )
    """)


def downgrade() -> None:
    raise RuntimeError("Nao reverter etiquetas sem backup: os codigos curtos podem estar impressos.")
