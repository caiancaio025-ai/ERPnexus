"""customer master foundation

Revision ID: 20260814_01
Revises: 20260812_01
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_01"
down_revision: str | None = "20260812_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "laboratory_customers",
        sa.Column("municipal_registration", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "laboratory_customers",
        sa.Column("website", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "customer_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("whatsapp", sa.String(length=40), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("receives_quotes", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("receives_invoices", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("receives_reports", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "receives_service_updates",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["laboratory_customers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_customer_contacts_customer_id", "customer_contacts", ["customer_id"])
    op.create_index("ix_customer_contacts_department", "customer_contacts", ["department"])
    op.create_index("ix_customer_contacts_name", "customer_contacts", ["name"])
    op.create_index("ix_customer_contacts_email", "customer_contacts", ["email"])
    op.create_index("ix_customer_contacts_is_active", "customer_contacts", ["is_active"])
    op.create_index("ix_customer_contacts_created_by", "customer_contacts", ["created_by"])

    op.create_table(
        "customer_billing_profiles",
        sa.Column("customer_id", sa.Integer(), primary_key=True),
        sa.Column("billing_cutoff_day", sa.Integer(), nullable=True),
        sa.Column("payment_term_days", sa.Integer(), nullable=True),
        sa.Column(
            "requires_purchase_order", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "requires_customer_order", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "requires_measurement", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "requires_service_report", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("invoice_email", sa.String(length=180), nullable=True),
        sa.Column("xml_email", sa.String(length=180), nullable=True),
        sa.Column("portal_url", sa.String(length=500), nullable=True),
        sa.Column("billing_instructions", sa.Text(), nullable=True),
        sa.Column("financial_notes", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["laboratory_customers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
    )
    op.create_index(
        "ix_customer_billing_profiles_updated_by",
        "customer_billing_profiles",
        ["updated_by"],
    )

    op.create_table(
        "customer_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="general"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["laboratory_customers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_customer_notes_customer_id", "customer_notes", ["customer_id"])
    op.create_index("ix_customer_notes_category", "customer_notes", ["category"])
    op.create_index("ix_customer_notes_created_by", "customer_notes", ["created_by"])

    op.create_table(
        "customer_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="other"),
        sa.Column("reference_number", sa.String(length=120), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["laboratory_customers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
    )
    op.create_index("ix_customer_documents_customer_id", "customer_documents", ["customer_id"])
    op.create_index("ix_customer_documents_category", "customer_documents", ["category"])
    op.create_index(
        "ix_customer_documents_reference_number",
        "customer_documents",
        ["reference_number"],
    )
    op.create_index(
        "ix_customer_documents_checksum_sha256",
        "customer_documents",
        ["checksum_sha256"],
    )
    op.create_index("ix_customer_documents_uploaded_by", "customer_documents", ["uploaded_by"])


def downgrade() -> None:
    op.drop_index("ix_customer_documents_uploaded_by", table_name="customer_documents")
    op.drop_index("ix_customer_documents_checksum_sha256", table_name="customer_documents")
    op.drop_index("ix_customer_documents_reference_number", table_name="customer_documents")
    op.drop_index("ix_customer_documents_category", table_name="customer_documents")
    op.drop_index("ix_customer_documents_customer_id", table_name="customer_documents")
    op.drop_table("customer_documents")

    op.drop_index("ix_customer_notes_created_by", table_name="customer_notes")
    op.drop_index("ix_customer_notes_category", table_name="customer_notes")
    op.drop_index("ix_customer_notes_customer_id", table_name="customer_notes")
    op.drop_table("customer_notes")

    op.drop_index(
        "ix_customer_billing_profiles_updated_by",
        table_name="customer_billing_profiles",
    )
    op.drop_table("customer_billing_profiles")

    op.drop_index("ix_customer_contacts_created_by", table_name="customer_contacts")
    op.drop_index("ix_customer_contacts_is_active", table_name="customer_contacts")
    op.drop_index("ix_customer_contacts_email", table_name="customer_contacts")
    op.drop_index("ix_customer_contacts_name", table_name="customer_contacts")
    op.drop_index("ix_customer_contacts_department", table_name="customer_contacts")
    op.drop_index("ix_customer_contacts_customer_id", table_name="customer_contacts")
    op.drop_table("customer_contacts")

    op.drop_column("laboratory_customers", "website")
    op.drop_column("laboratory_customers", "municipal_registration")
