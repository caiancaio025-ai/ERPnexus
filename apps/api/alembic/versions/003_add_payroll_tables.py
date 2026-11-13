"""Add Payroll and Contracheque support

Revision ID: 003_add_payroll_tables
Revises: 002_previous_migration
Create Date: 2026-08-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003_add_payroll_tables"
down_revision = "002_previous_migration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Criar tabelas de contracheques"""
    
    # Criar tabela payrolls (Folhas de Pagamento)
    op.create_table(
        "payrolls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payroll_period", sa.String(length=7), nullable=False),
        sa.Column("company_code", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("total_gross", sa.Numeric(precision=14, scale=2), server_default="0"),
        sa.Column("total_discounts", sa.Numeric(precision=14, scale=2), server_default="0"),
        sa.Column("total_net", sa.Numeric(precision=14, scale=2), server_default="0"),
        sa.Column("transmission_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transmitted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'processed', 'transmitted', 'paid', 'cancelled')", name="check_payroll_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transmitted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Índices para payrolls
    op.create_index("idx_payroll_company", "payrolls", ["company_code"])
    op.create_index("idx_payroll_created", "payrolls", ["created_at"])
    op.create_index("idx_payroll_period", "payrolls", ["payroll_period"])
    op.create_index("idx_payroll_status", "payrolls", ["status"])
    op.create_index("idx_payroll_period_company", "payrolls", ["payroll_period", "company_code"], unique=True)
    
    
    # Criar tabela payslips (Contracheques Individuais)
    op.create_table(
        "payslips",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payroll_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("employee_name", sa.String(length=180), nullable=False),
        sa.Column("employee_document", sa.String(length=20), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("gross_salary", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_earnings", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_discounts", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("net_salary", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payroll_id"], ["payrolls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payroll_id", "employee_id", name="uq_payslip_unique"),
    )
    
    # Índices para payslips
    op.create_index("idx_payslip_accessed", "payslips", ["accessed_at"])
    op.create_index("idx_payslip_downloaded", "payslips", ["downloaded_at"])
    op.create_index("idx_payslip_employee", "payslips", ["employee_id"])
    op.create_index("idx_payslip_employee_name", "payslips", ["employee_name"])
    op.create_index("idx_payslip_payroll", "payslips", ["payroll_id"])
    
    
    # Criar tabela payslip_details (Linhas do Contracheque)
    op.create_table(
        "payslip_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payslip_id", sa.Integer(), nullable=False),
        sa.Column("line_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=180), nullable=False),
        sa.Column("value", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("line_type IN ('earning', 'discount')", name="check_payslip_detail_type"),
        sa.ForeignKeyConstraint(["payslip_id"], ["payslips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Índices para payslip_details
    op.create_index("idx_payslip_detail_payslip", "payslip_details", ["payslip_id"])
    op.create_index("idx_payslip_detail_reference", "payslip_details", ["reference_id"])
    op.create_index("idx_payslip_detail_type", "payslip_details", ["line_type"])
    
    
    # Criar tabela payroll_audit_events (Auditoria)
    op.create_table(
        "payroll_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payroll_id", sa.Integer(), nullable=True),
        sa.Column("payslip_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["payroll_id"], ["payrolls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payslip_id"], ["payslips.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Índices para payroll_audit_events
    op.create_index("idx_audit_action", "payroll_audit_events", ["action"])
    op.create_index("idx_audit_created", "payroll_audit_events", ["created_at"])
    op.create_index("idx_audit_payroll", "payroll_audit_events", ["payroll_id"])
    op.create_index("idx_audit_payslip", "payroll_audit_events", ["payslip_id"])
    op.create_index("idx_audit_user", "payroll_audit_events", ["user_id"])


def downgrade() -> None:
    """Remove tabelas de contracheques"""
    
    # Drop tables em ordem reversa (respeitar foreign keys)
    op.drop_table("payroll_audit_events")
    op.drop_table("payslip_details")
    op.drop_table("payslips")
    op.drop_table("payrolls")


# ============================================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================================

"""
Como usar este arquivo de migration:

1. COPIAR PARA PROJETO:
   cp alembic_payroll_migration.py apps/api/alembic/versions/003_add_payroll_tables.py

2. EDITAR O CABEÇALHO COM OS DADOS CORRETOS:
   - Revision ID (gerar com: alembic revision --autogenerate -m "Add payroll tables")
   - down_revision (verificar última migration)

3. EXECUTAR MIGRATION:
   cd apps/api
   alembic upgrade head

4. VERIFICAR STATUS:
   alembic current
   alembic history

5. ROLLBACK (SE NECESSÁRIO):
   alembic downgrade -1

6. TESTES:
   pytest tests/test_payroll.py

IMPORTANTE:
- Não editar o arquivo após executar em produção
- Sempre fazer backup do banco antes de aplicar
- Testar em staging primeiro
- Versionar no git antes de executar
"""
