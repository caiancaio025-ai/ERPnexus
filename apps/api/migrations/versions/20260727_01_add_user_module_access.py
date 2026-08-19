"""add user module access

Revision ID: 20260727_01
Revises: 20260715_05
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_01"
down_revision: str | None = "20260715_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALL_MODULES = [
    "dashboard",
    "financeiro",
    "compras",
    "comercial",
    "laboratorio",
    "estoque",
    "configuracoes",
    "auditoria",
]
ROLE_DEFAULTS = {
    "super_admin": ALL_MODULES,
    "admin": ALL_MODULES,
    "financeiro": ["dashboard", "financeiro"],
    "compras": ["dashboard", "compras"],
    "comercial": ["dashboard", "comercial"],
    "laboratorio": ["dashboard", "laboratorio"],
    "estoque": ["dashboard", "estoque"],
    "consulta": ["dashboard"],
    "user": ["dashboard"],
}


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("modules", sa.JSON(), nullable=True),
    )

    connection = op.get_bind()
    users = connection.execute(sa.text("SELECT id, role FROM users")).mappings()
    for user in users:
        role = (user["role"] or "consulta").lower()
        modules = ROLE_DEFAULTS.get(role, ["dashboard"])
        connection.execute(
            sa.text("UPDATE users SET modules = :modules WHERE id = :user_id").bindparams(
                sa.bindparam("modules", type_=sa.JSON())
            ),
            {"modules": modules, "user_id": user["id"]},
        )

    op.alter_column("users", "modules", nullable=False)
    connection.execute(
        sa.text("UPDATE users SET role = 'consulta' WHERE role = 'user'")
    )


def downgrade() -> None:
    op.drop_column("users", "modules")
