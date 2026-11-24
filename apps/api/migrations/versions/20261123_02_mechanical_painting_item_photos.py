"""Vincular fotos de envio e retorno de pintura a cada peca, preservando historico.

Revision ID: 20261123_02
Revises: 20261123_01

Fotos antigas recebem item_id NULL e continuam acessiveis pelo controle.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261123_02"
down_revision = "20261123_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("laboratory_mechanical_painting_photos") as batch:
        batch.add_column(
            sa.Column(
                "item_id", sa.Integer(),
                sa.ForeignKey("laboratory_mechanical_painting_items.id", name="fk_lab_mech_photo_item", ondelete="RESTRICT"),
                nullable=True,
            )
        )
    op.create_index(
        "ix_laboratory_mechanical_painting_photos_item_id",
        "laboratory_mechanical_painting_photos", ["item_id"],
    )


def downgrade() -> None:
    raise RuntimeError("Nao remover vinculos de fotos de pintura sem backup.")
