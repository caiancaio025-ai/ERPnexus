from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("company_code", "document", name="uq_employee_company_document"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(180), index=True)
    document: Mapped[str] = mapped_column(String(20), index=True)
    document_type: Mapped[str] = mapped_column(String(10), default="cpf")
    date_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(1))
    nationality: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(180), index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    whatsapp: Mapped[str | None] = mapped_column(String(20))
    postal_code: Mapped[str | None] = mapped_column(String(12))
    address: Mapped[str | None] = mapped_column(String(220))
    address_number: Mapped[str | None] = mapped_column(String(30))
    complement: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(2))
    department: Mapped[str] = mapped_column(String(120), index=True)
    position: Mapped[str] = mapped_column(String(120), index=True)
    salary_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    hiring_date: Mapped[date] = mapped_column(Date, index=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_type: Mapped[str] = mapped_column(String(30), default="clt")
    bank_name: Mapped[str | None] = mapped_column(String(80))
    bank_account: Mapped[str | None] = mapped_column(String(40))
    bank_routing: Mapped[str | None] = mapped_column(String(20))
    account_type: Mapped[str | None] = mapped_column(String(20))
    account_holder: Mapped[str | None] = mapped_column(String(180))
    pix_key: Mapped[str | None] = mapped_column(String(140))
    pis: Mapped[str | None] = mapped_column(String(20), index=True)
    ctps: Mapped[str | None] = mapped_column(String(20))
    rg_number: Mapped[str | None] = mapped_column(String(20))
    rg_issuer: Mapped[str | None] = mapped_column(String(40))
    rg_issue_date: Mapped[date | None] = mapped_column(Date)
    marital_status: Mapped[str | None] = mapped_column(String(20))
    dependents: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    employment_history: Mapped[list["EmploymentHistory"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="selectin", order_by="EmploymentHistory.start_date.desc()"
    )
    documents: Mapped[list["EmployeeDocument"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="selectin"
    )


class EmploymentHistory(Base):
    __tablename__ = "employment_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    department: Mapped[str] = mapped_column(String(120))
    position: Mapped[str] = mapped_column(String(120))
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    employment_type: Mapped[str] = mapped_column(String(30))
    reason_end: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    employee: Mapped[Employee] = relationship(back_populates="employment_history")


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"
    __table_args__ = (
        UniqueConstraint("employee_id", "document_type", "version", name="uq_employee_doc_type_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column()
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(default=1)
    metadata_period: Mapped[str | None] = mapped_column(String(7))
    expiration_date: Mapped[date | None] = mapped_column(Date)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    accessed_count: Mapped[int] = mapped_column(default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    downloaded_count: Mapped[int] = mapped_column(default=0)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_downloaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    employee: Mapped[Employee] = relationship(back_populates="documents")


class EmployeeAuditEvent(Base):
    __tablename__ = "employee_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("employee_documents.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(String(500))
    before_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    after_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
