"""add laboratory technical release events

Revision ID: 20261013_01
Revises: 20261009_04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_01"
down_revision: str | None = "20261009_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "laboratory_release_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_order_id",
            sa.Integer(),
            sa.ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "technician_id",
            sa.Integer(),
            sa.ForeignKey("laboratory_technicians.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("technician_name", sa.String(length=160), nullable=True),
        sa.Column(
            "released_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "released_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_lab_release_events_work_order",
        "laboratory_release_events",
        ["work_order_id"],
    )
    op.create_index(
        "ix_lab_release_events_technician",
        "laboratory_release_events",
        ["technician_id"],
    )
    op.create_index(
        "ix_lab_release_events_released_at",
        "laboratory_release_events",
        ["released_at"],
    )
    op.create_index(
        "ix_lab_release_events_released_by",
        "laboratory_release_events",
        ["released_by_user_id"],
    )

    # Histórico anterior à criação desta tabela:
    # preservamos a ocorrência e a data da liberação, mas NÃO atribuímos um
    # técnico retroativamente. Usar o técnico atual da O.S. poderia falsificar
    # o histórico caso a atribuição tenha sido alterada depois.
    op.execute(
        sa.text(
            """
            INSERT INTO laboratory_release_events (
                work_order_id,
                technician_id,
                technician_name,
                released_at,
                released_by_user_id,
                previous_status,
                created_at
            )
            SELECT
                history.work_order_id,
                NULL,
                NULL,
                history.created_at,
                history.user_id,
                history.previous_status,
                history.created_at
            FROM laboratory_status_history AS history
            WHERE history.new_status = 'awaiting_pickup'
            ORDER BY history.id
            """
        )
    )


def downgrade() -> None:
    op.drop_table("laboratory_release_events")
