"""create employees module

Revision ID: 20260817_01
Revises: 20260814_01
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_01"
down_revision: str | None = "20260814_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("document", sa.String(length=20), nullable=False),
        sa.Column("document_type", sa.String(length=10), nullable=False, server_default="cpf"),
        sa.Column("date_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=1), nullable=True),
        sa.Column("nationality", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("whatsapp", sa.String(length=20), nullable=True),
        sa.Column("postal_code", sa.String(length=12), nullable=True),
        sa.Column("address", sa.String(length=220), nullable=True),
        sa.Column("address_number", sa.String(length=30), nullable=True),
        sa.Column("complement", sa.String(length=120), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("salary_base", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("hiring_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("employment_type", sa.String(length=30), nullable=False, server_default="clt"),
        sa.Column("bank_name", sa.String(length=80), nullable=True),
        sa.Column("bank_account", sa.String(length=40), nullable=True),
        sa.Column("bank_routing", sa.String(length=20), nullable=True),
        sa.Column("account_type", sa.String(length=20), nullable=True),
        sa.Column("account_holder", sa.String(length=180), nullable=True),
        sa.Column("pix_key", sa.String(length=140), nullable=True),
        sa.Column("pis", sa.String(length=20), nullable=True),
        sa.Column("ctps", sa.String(length=20), nullable=True),
        sa.Column("rg_number", sa.String(length=20), nullable=True),
        sa.Column("rg_issuer", sa.String(length=40), nullable=True),
        sa.Column("rg_issue_date", sa.Date(), nullable=True),
        sa.Column("marital_status", sa.String(length=20), nullable=True),
        sa.Column("dependents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("company_code", "document", name="uq_employee_company_document"),
    )
    for name, cols in [
        ("ix_employees_company_code", ["company_code"]),
        ("ix_employees_user_id", ["user_id"]),
        ("ix_employees_full_name", ["full_name"]),
        ("ix_employees_document", ["document"]),
        ("ix_employees_email", ["email"]),
        ("ix_employees_department", ["department"]),
        ("ix_employees_position", ["position"]),
        ("ix_employees_hiring_date", ["hiring_date"]),
        ("ix_employees_pis", ["pis"]),
        ("ix_employees_is_active", ["is_active"]),
        ("ix_employees_created_by", ["created_by"]),
    ]:
        op.create_index(name, "employees", cols)

    op.create_table(
        "employment_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("employment_type", sa.String(length=30), nullable=False),
        sa.Column("reason_end", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_employment_history_employee_id", "employment_history", ["employee_id"])
    op.create_index("ix_employment_history_start_date", "employment_history", ["start_date"])

    op.create_table(
        "employee_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_period", sa.String(length=7), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("accessed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_by", sa.Integer(), nullable=True),
        sa.Column("downloaded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_downloaded_by", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_accessed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["last_downloaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.UniqueConstraint("employee_id", "document_type", "version", name="uq_employee_doc_type_version"),
    )
    for name, cols in [
        ("ix_employee_documents_employee_id", ["employee_id"]),
        ("ix_employee_documents_document_type", ["document_type"]),
        ("ix_employee_documents_checksum_sha256", ["checksum_sha256"]),
        ("ix_employee_documents_uploaded_by", ["uploaded_by"]),
    ]:
        op.create_index(name, "employee_documents", cols)

    op.create_table(
        "employee_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["employee_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    for name, cols in [
        ("ix_employee_audit_events_employee_id", ["employee_id"]),
        ("ix_employee_audit_events_document_id", ["document_id"]),
        ("ix_employee_audit_events_action", ["action"]),
        ("ix_employee_audit_events_user_id", ["user_id"]),
        ("ix_employee_audit_events_created_at", ["created_at"]),
    ]:
        op.create_index(name, "employee_audit_events", cols)


def downgrade() -> None:
    op.drop_table("employee_audit_events")
    op.drop_table("employee_documents")
    op.drop_table("employment_history")
    op.drop_table("employees")
