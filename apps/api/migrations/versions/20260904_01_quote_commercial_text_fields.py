"""add textual commercial terms to laboratory quotes

Revision ID: 20260904_01
Revises: 20260827_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260904_01"
down_revision = "20260827_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("laboratory_quotes", sa.Column("billing_terms", sa.String(length=200), nullable=True))
    op.add_column("laboratory_quotes", sa.Column("warranty_terms", sa.String(length=200), nullable=True))
    op.execute("UPDATE laboratory_quotes SET billing_terms = billing_days::text WHERE billing_terms IS NULL")
    op.execute("UPDATE laboratory_quotes SET warranty_terms = warranty_months::text WHERE warranty_terms IS NULL")


def downgrade() -> None:
    op.drop_column("laboratory_quotes", "warranty_terms")
    op.drop_column("laboratory_quotes", "billing_terms")
