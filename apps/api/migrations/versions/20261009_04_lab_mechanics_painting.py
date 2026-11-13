"""add mechanics external-painting custody controls

Revision ID: 20261009_04
Revises: 20261009_03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_04"
down_revision: str | None = "20261009_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "laboratory_mechanical_painting_dispatches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("provider", sa.String(length=180), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sent_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("returned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lab_mech_paint_dispatch_work_order", "laboratory_mechanical_painting_dispatches", ["work_order_id"])
    op.create_index("ix_lab_mech_paint_dispatch_status", "laboratory_mechanical_painting_dispatches", ["status"])
    op.create_index("ix_lab_mech_paint_dispatch_sent_at", "laboratory_mechanical_painting_dispatches", ["sent_at"])
    op.create_index("ix_lab_mech_paint_dispatch_returned_at", "laboratory_mechanical_painting_dispatches", ["returned_at"])
    op.create_index("ix_lab_mech_paint_dispatch_created_by", "laboratory_mechanical_painting_dispatches", ["created_by"])
    op.create_index("ix_lab_mech_paint_dispatch_sent_by", "laboratory_mechanical_painting_dispatches", ["sent_by"])
    op.create_index("ix_lab_mech_paint_dispatch_returned_by", "laboratory_mechanical_painting_dispatches", ["returned_by"])

    op.create_table(
        "laboratory_mechanical_painting_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dispatch_id", sa.Integer(), sa.ForeignKey("laboratory_mechanical_painting_dispatches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("returned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("return_note", sa.String(length=300), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_lab_mech_paint_item_dispatch", "laboratory_mechanical_painting_items", ["dispatch_id"])
    op.create_index("ix_lab_mech_paint_item_returned", "laboratory_mechanical_painting_items", ["returned"])

    op.create_table(
        "laboratory_mechanical_painting_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dispatch_id", sa.Integer(), sa.ForeignKey("laboratory_mechanical_painting_dispatches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("laboratory_documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False, server_default="outbound"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("caption", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dispatch_id", "document_id", name="uq_lab_mech_paint_photo_document"),
    )
    op.create_index("ix_lab_mech_paint_photo_dispatch", "laboratory_mechanical_painting_photos", ["dispatch_id"])
    op.create_index("ix_lab_mech_paint_photo_document", "laboratory_mechanical_painting_photos", ["document_id"])
    op.create_index("ix_lab_mech_paint_photo_phase", "laboratory_mechanical_painting_photos", ["phase"])


def downgrade() -> None:
    op.drop_table("laboratory_mechanical_painting_photos")
    op.drop_table("laboratory_mechanical_painting_items")
    op.drop_table("laboratory_mechanical_painting_dispatches")
