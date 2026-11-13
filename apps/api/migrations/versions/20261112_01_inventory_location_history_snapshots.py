"""Referências textuais de localização para exclusão física de endereços.

Revision ID: 20261112_01
Revises: 20261028_01
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20261112_01"
down_revision: str | None = "20261028_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("inventory_location_history", sa.Column("previous_slot_code", sa.String(length=52), nullable=True))
    op.add_column("inventory_location_history", sa.Column("new_slot_code", sa.String(length=52), nullable=True))
    # Registra o código original antes que qualquer endereço seja apagado.
    op.execute(sa.text("""
        UPDATE inventory_location_history AS h
        SET previous_slot_code = s.code
        FROM inventory_slots AS s
        WHERE h.previous_slot_id = s.id AND h.previous_slot_code IS NULL
    """))
    op.execute(sa.text("""
        UPDATE inventory_location_history AS h
        SET new_slot_code = s.code
        FROM inventory_slots AS s
        WHERE h.new_slot_id = s.id AND h.new_slot_code IS NULL
    """))


def downgrade() -> None:
    # Reverter para um esquema sem os códigos descartaria referências textuais
    # dos endereços já removidos; deixe isso explícito.
    connection = op.get_bind()
    removed_refs = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM inventory_location_history
            WHERE (previous_slot_id IS NULL AND previous_slot_code IS NOT NULL)
               OR (new_slot_id IS NULL AND new_slot_code IS NOT NULL)
        )
    """)).scalar()
    if removed_refs:
        raise RuntimeError("Não é seguro reverter: há históricos com endereços excluídos definitivamente.")
    op.drop_column("inventory_location_history", "new_slot_code")
    op.drop_column("inventory_location_history", "previous_slot_code")
