"""laboratory configurable statuses and substatuses

Revision ID: 20260914_01
Revises: 20260904_02
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_01"
down_revision: str | None = "20260904_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_OPTIONS = (
    ("status", "received", "Entrada", 10, True),
    ("status", "in_analysis", "Em análise", 20, True),
    ("status", "awaiting_approval", "Ag. Aprovação", 30, True),
    ("status", "approved", "Aprovado", 40, True),
    ("status", "no_repair", "Sem conserto", 50, True),
    ("status", "awaiting_pickup", "Liberado", 60, True),
    ("status", "warranty", "Garantia", 70, True),
    ("status", "invoiced", "Faturado", 80, True),
    ("substatus", "quote_sent", "Orçamento enviado", 10, True),
    ("substatus", "awaiting_delivery", "Ag. entregar", 20, True),
    ("substatus", "delivered", "Entregue", 30, True),
)


def upgrade() -> None:
    op.create_table(
        "laboratory_workflow_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("kind", "code", name="uq_lab_workflow_option_kind_code"),
    )
    op.create_index("ix_laboratory_workflow_options_kind", "laboratory_workflow_options", ["kind"])
    op.create_index("ix_laboratory_workflow_options_code", "laboratory_workflow_options", ["code"])
    op.create_index("ix_laboratory_workflow_options_sort_order", "laboratory_workflow_options", ["sort_order"])
    op.create_index("ix_laboratory_workflow_options_is_active", "laboratory_workflow_options", ["is_active"])
    op.create_index("ix_laboratory_workflow_options_is_system", "laboratory_workflow_options", ["is_system"])
    op.create_index("ix_laboratory_workflow_options_created_by", "laboratory_workflow_options", ["created_by"])

    workflow_table = sa.table(
        "laboratory_workflow_options",
        sa.column("kind", sa.String),
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("is_system", sa.Boolean),
    )
    op.bulk_insert(
        workflow_table,
        [
            {
                "kind": kind,
                "code": code,
                "label": label,
                "sort_order": sort_order,
                "is_active": active,
                "is_system": True,
            }
            for kind, code, label, sort_order, active in DEFAULT_OPTIONS
        ],
    )

    op.create_table(
        "laboratory_work_order_substatuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_order_id",
            sa.Integer(),
            sa.ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("work_order_id", "code", name="uq_lab_work_order_substatus_code"),
    )
    op.create_index(
        "ix_laboratory_work_order_substatuses_work_order_id",
        "laboratory_work_order_substatuses",
        ["work_order_id"],
    )
    op.create_index("ix_laboratory_work_order_substatuses_code", "laboratory_work_order_substatuses", ["code"])
    op.create_index(
        "ix_laboratory_work_order_substatuses_is_active",
        "laboratory_work_order_substatuses",
        ["is_active"],
    )
    op.create_index(
        "ix_laboratory_work_order_substatuses_updated_by",
        "laboratory_work_order_substatuses",
        ["updated_by"],
    )

    # Preserve historical meaning without rewriting the stored status values.
    # Existing rows gain the corresponding new substatus so the new UI can
    # represent the old workflow faithfully from the first migration run.
    op.execute(
        """
        INSERT INTO laboratory_work_order_substatuses (work_order_id, code, is_active)
        SELECT id, 'quote_sent', TRUE
        FROM laboratory_work_orders
        WHERE status = 'quote_sent'
        ON CONFLICT (work_order_id, code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO laboratory_work_order_substatuses (work_order_id, code, is_active)
        SELECT id, 'awaiting_delivery', TRUE
        FROM laboratory_work_orders
        WHERE status = 'completed'
        ON CONFLICT (work_order_id, code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO laboratory_work_order_substatuses (work_order_id, code, is_active)
        SELECT id, 'delivered', TRUE
        FROM laboratory_work_orders
        WHERE status = 'delivered'
        ON CONFLICT (work_order_id, code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("laboratory_work_order_substatuses")
    op.drop_table("laboratory_workflow_options")
