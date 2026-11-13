"""laboratory workflow, invoice keys, locations and quote photos

Revision ID: 20261008_02
Revises: 20261008_01
Create Date: 2026-10-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261008_02"
down_revision: str | None = "20261008_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("laboratory_work_orders", sa.Column("entry_invoice_access_key", sa.String(44), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("exit_invoice_access_key", sa.String(44), nullable=True))
    op.add_column("laboratory_work_orders", sa.Column("storage_location", sa.String(8), nullable=True))
    op.create_index("ix_laboratory_work_orders_entry_invoice_access_key", "laboratory_work_orders", ["entry_invoice_access_key"])
    op.create_index("ix_laboratory_work_orders_exit_invoice_access_key", "laboratory_work_orders", ["exit_invoice_access_key"])
    op.create_index("ix_laboratory_work_orders_storage_location", "laboratory_work_orders", ["storage_location"], unique=True)

    op.create_table(
        "laboratory_location_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location", sa.String(8), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_laboratory_location_history_work_order_id", "laboratory_location_history", ["work_order_id"])
    op.create_index("ix_laboratory_location_history_location", "laboratory_location_history", ["location"])
    op.create_index("ix_laboratory_location_history_changed_by", "laboratory_location_history", ["changed_by"])

    op.create_table(
        "laboratory_quote_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("laboratory_quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("laboratory_documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.UniqueConstraint("quote_id", "document_id", name="uq_lab_quote_photo_document"),
    )
    op.create_index("ix_laboratory_quote_photos_quote_id", "laboratory_quote_photos", ["quote_id"])
    op.create_index("ix_laboratory_quote_photos_document_id", "laboratory_quote_photos", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_laboratory_quote_photos_document_id", table_name="laboratory_quote_photos")
    op.drop_index("ix_laboratory_quote_photos_quote_id", table_name="laboratory_quote_photos")
    op.drop_table("laboratory_quote_photos")
    op.drop_index("ix_laboratory_location_history_changed_by", table_name="laboratory_location_history")
    op.drop_index("ix_laboratory_location_history_location", table_name="laboratory_location_history")
    op.drop_index("ix_laboratory_location_history_work_order_id", table_name="laboratory_location_history")
    op.drop_table("laboratory_location_history")
    op.drop_index("ix_laboratory_work_orders_storage_location", table_name="laboratory_work_orders")
    op.drop_index("ix_laboratory_work_orders_exit_invoice_access_key", table_name="laboratory_work_orders")
    op.drop_index("ix_laboratory_work_orders_entry_invoice_access_key", table_name="laboratory_work_orders")
    op.drop_column("laboratory_work_orders", "storage_location")
    op.drop_column("laboratory_work_orders", "exit_invoice_access_key")
    op.drop_column("laboratory_work_orders", "entry_invoice_access_key")
