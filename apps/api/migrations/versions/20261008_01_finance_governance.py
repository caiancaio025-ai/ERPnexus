"""finance period closing and alert acknowledgments

Revision ID: 20261008_01
Revises: 20261007_02
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261008_01"
down_revision: str | None = "20261007_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_period_closures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("snapshot_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("closed_by", sa.Integer(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reopened_by", sa.Integer(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("month >= 1 AND month <= 12", name="ck_financial_period_closures_month"),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reopened_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_code", "year", "month", name="uq_financial_period_closures_company_period"),
    )
    op.create_index(
        op.f("ix_financial_period_closures_company_code"),
        "financial_period_closures",
        ["company_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_period_closures_year"),
        "financial_period_closures",
        ["year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_period_closures_month"),
        "financial_period_closures",
        ["month"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_period_closures_is_closed"),
        "financial_period_closures",
        ["is_closed"],
        unique=False,
    )

    op.create_table(
        "financial_alert_acknowledgments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("acknowledged_by", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["financial_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entry_id",
            "fingerprint",
            name="uq_financial_alert_acknowledgments_entry_fingerprint",
        ),
    )
    op.create_index(
        op.f("ix_financial_alert_acknowledgments_entry_id"),
        "financial_alert_acknowledgments",
        ["entry_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_alert_acknowledgments_fingerprint"),
        "financial_alert_acknowledgments",
        ["fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_alert_acknowledgments_acknowledged_by"),
        "financial_alert_acknowledgments",
        ["acknowledged_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_alert_acknowledgments_acknowledged_at"),
        "financial_alert_acknowledgments",
        ["acknowledged_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("financial_alert_acknowledgments")
    op.drop_table("financial_period_closures")
