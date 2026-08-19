"""Add Employees and Documents support

Revision ID: 004_add_employees_tables
Revises: 003_add_payroll_tables
Create Date: 2026-08-17 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004_add_employees_tables"
down_revision = "003_add_payroll_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Criar tabelas de funcionários e documentos"""

    # ========================================================================
    # Tabela: employees (Funcionários)
    # ========================================================================
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        
        # Dados pessoais
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("document", sa.String(length=20), nullable=False),
        sa.Column("document_type", sa.String(length=10), nullable=False, server_default="cpf"),
        sa.Column("date_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=1), nullable=True),
        sa.Column("nationality", sa.String(length=120), nullable=True),
        
        # Contato
        sa.Column("email", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("whatsapp", sa.String(length=20), nullable=True),
        
        # Endereço
        sa.Column("postal_code", sa.String(length=12), nullable=True),
        sa.Column("address", sa.String(length=220), nullable=True),
        sa.Column("address_number", sa.String(length=30), nullable=True),
        sa.Column("complement", sa.String(length=120), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        
        # Dados profissionais
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("salary_base", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("hiring_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("employment_type", sa.String(length=30), nullable=False, server_default="clt"),
        
        # Banco
        sa.Column("bank_name", sa.String(length=80), nullable=True),
        sa.Column("bank_account", sa.String(length=40), nullable=True),
        sa.Column("bank_routing", sa.String(length=20), nullable=True),
        sa.Column("account_type", sa.String(length=20), nullable=True),
        sa.Column("account_holder", sa.String(length=180), nullable=True),
        sa.Column("pix_key", sa.String(length=140), nullable=True),
        
        # Documentos
        sa.Column("pis", sa.String(length=20), nullable=True),
        sa.Column("ctps", sa.String(length=20), nullable=True),
        sa.Column("rg_number", sa.String(length=20), nullable=True),
        sa.Column("rg_issuer", sa.String(length=40), nullable=True),
        sa.Column("rg_issue_date", sa.Date(), nullable=True),
        
        # Informações adicionais
        sa.Column("marital_status", sa.String(length=20), nullable=True),
        sa.Column("dependents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        
        # Auditoria
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        # Constraints
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_code", "document", name="uq_employee_company_document"),
    )
    
    # Índices para employees
    op.create_index("idx_employee_company", "employees", ["company_code"])
    op.create_index("idx_employee_department", "employees", ["department"])
    op.create_index("idx_employee_document", "employees", ["document"])
    op.create_index("idx_employee_email", "employees", ["email"])
    op.create_index("idx_employee_full_name", "employees", ["full_name"])
    op.create_index("idx_employee_hiring_date", "employees", ["hiring_date"])
    op.create_index("idx_employee_is_active", "employees", ["is_active"])
    op.create_index("idx_employee_pis", "employees", ["pis"])
    op.create_index("idx_employee_user_id", "employees", ["user_id"])


    # ========================================================================
    # Tabela: employment_history (Histórico de Emprego)
    # ========================================================================
    op.create_table(
        "employment_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("salary", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("employment_type", sa.String(length=30), nullable=False),
        sa.Column("reason_end", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    op.create_index("idx_employment_history_employee", "employment_history", ["employee_id"])
    op.create_index("idx_employment_history_start_date", "employment_history", ["start_date"])


    # ========================================================================
    # Tabela: employee_documents (Documentos)
    # ========================================================================
    op.create_table(
        "employee_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        
        # Metadados
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_period", sa.String(length=7), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        
        # Visibilidade
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("accessed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_by", sa.Integer(), nullable=True),
        
        sa.Column("downloaded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_downloaded_by", sa.Integer(), nullable=True),
        
        # Auditoria
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["last_accessed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_downloaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "document_type", "version", name="uq_employee_doc_type_version"),
    )
    
    op.create_index("idx_doc_checksum", "employee_documents", ["checksum_sha256"])
    op.create_index("idx_doc_document_type", "employee_documents", ["document_type"])
    op.create_index("idx_doc_employee", "employee_documents", ["employee_id"])
    op.create_index("idx_doc_is_public", "employee_documents", ["is_public"])
    op.create_index("idx_doc_metadata_period", "employee_documents", ["metadata_period"])
    op.create_index("idx_doc_uploaded_by", "employee_documents", ["uploaded_by"])


    # ========================================================================
    # Tabela: employee_audit_events (Auditoria)
    # ========================================================================
    op.create_table(
        "employee_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.ForeignKeyConstraint(["document_id"], ["employee_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    op.create_index("idx_audit_action", "employee_audit_events", ["action"])
    op.create_index("idx_audit_created_at", "employee_audit_events", ["created_at"])
    op.create_index("idx_audit_document", "employee_audit_events", ["document_id"])
    op.create_index("idx_audit_employee", "employee_audit_events", ["employee_id"])
    op.create_index("idx_audit_user", "employee_audit_events", ["user_id"])


    # ========================================================================
    # Atualizar tabela payslips para referenciar employees
    # ========================================================================
    # Adicionar coluna employee_id em payslips (se ainda não existe)
    # op.add_column("payslips", sa.Column("employee_id", sa.Integer(), nullable=True))
    # op.create_foreign_key(
    #     "fk_payslip_employee",
    #     "payslips",
    #     "employees",
    #     ["employee_id"],
    #     ["id"],
    #     ondelete="CASCADE"
    # )


def downgrade() -> None:
    """Remove tabelas de funcionários"""
    
    op.drop_table("employee_audit_events")
    op.drop_table("employee_documents")
    op.drop_table("employment_history")
    op.drop_table("employees")
