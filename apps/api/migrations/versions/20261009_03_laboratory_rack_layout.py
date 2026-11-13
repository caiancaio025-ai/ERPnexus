"""add configurable rack placement to laboratory map

Revision ID: 20261009_03
Revises: 20261009_02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_03"
down_revision: str | None = "20261009_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "laboratory_racks",
        sa.Column("layout_row", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "laboratory_racks",
        sa.Column("layout_column", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "laboratory_racks",
        sa.Column("layout_span", sa.Integer(), nullable=False, server_default="1"),
    )

    # Reproduz o desenho operacional informado para a Expedição:
    # E1 no topo à direita; E5/E6 à esquerda; E2/E3/E4 à direita.
    layout = {
        "E1": (1, 2, 1),
        "E5": (2, 1, 1),
        "E2": (2, 2, 1),
        "E6": (3, 1, 1),
        "E3": (3, 2, 1),
        "E4": (4, 2, 1),
    }
    conn = op.get_bind()
    for rack_code, (row, column, span) in layout.items():
        conn.execute(
            sa.text("""
                UPDATE laboratory_racks
                SET layout_row = :row,
                    layout_column = :column,
                    layout_span = :span
                WHERE code = :code
            """),
            {"row": row, "column": column, "span": span, "code": rack_code},
        )


def downgrade() -> None:
    op.drop_column("laboratory_racks", "layout_span")
    op.drop_column("laboratory_racks", "layout_column")
    op.drop_column("laboratory_racks", "layout_row")
