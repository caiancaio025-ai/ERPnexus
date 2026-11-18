"""Web Push opt-in per browser, and committed notification queue.

Revision ID: 20261116_01
Revises: 20261112_01
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261116_01"
down_revision: str | None = "20261112_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("push_processed_at", sa.DateTime(timezone=True), nullable=True))
    # Não disparar retroativamente notificações anteriores à atualização.
    op.execute(sa.text("UPDATE notifications SET push_processed_at = CURRENT_TIMESTAMP"))
    op.create_index("ix_notifications_push_processed_at", "notifications", ["push_processed_at"])
    op.create_table(
        "notification_push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.String(length=1800), nullable=False),
        sa.Column("p256dh", sa.String(length=200), nullable=False),
        sa.Column("auth", sa.String(length=100), nullable=False),
        sa.Column("device_label", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index("ix_notification_push_subscriptions_user_id", "notification_push_subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_push_subscriptions_user_id", table_name="notification_push_subscriptions")
    op.drop_table("notification_push_subscriptions")
    op.drop_index("ix_notifications_push_processed_at", table_name="notifications")
    op.drop_column("notifications", "push_processed_at")
