"""add persistent login rate limiting

Revision ID: 20260812_01
Revises: 20260811_02
Create Date: 2026-08-12

Registra somente hashes de identificador/IP e o instante das tentativas falhas.
Os dados sao temporarios e servem exclusivamente para protecao contra brute force.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_01"
down_revision: str | None = "20260811_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_login_attempts_scope_key_time",
        "auth_login_attempts",
        ["scope", "key_hash", "attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_login_attempts_attempted_at",
        "auth_login_attempts",
        ["attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_login_attempts_attempted_at",
        table_name="auth_login_attempts",
    )
    op.drop_index(
        "ix_auth_login_attempts_scope_key_time",
        table_name="auth_login_attempts",
    )
    op.drop_table("auth_login_attempts")
