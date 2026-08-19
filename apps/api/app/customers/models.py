from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class CustomerContact(Base):
    __tablename__ = "customer_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_customers.id", ondelete="CASCADE"), index=True
    )
    department: Mapped[str | None] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    job_title: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(180), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    whatsapp: Mapped[str | None] = mapped_column(String(40))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    receives_quotes: Mapped[bool] = mapped_column(Boolean, default=False)
    receives_invoices: Mapped[bool] = mapped_column(Boolean, default=False)
    receives_reports: Mapped[bool] = mapped_column(Boolean, default=False)
    receives_service_updates: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CustomerBillingProfile(Base):
    __tablename__ = "customer_billing_profiles"

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_customers.id", ondelete="CASCADE"), primary_key=True
    )
    billing_cutoff_day: Mapped[int | None] = mapped_column(Integer)
    payment_term_days: Mapped[int | None] = mapped_column(Integer)
    requires_purchase_order: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_customer_order: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_measurement: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_service_report: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_email: Mapped[str | None] = mapped_column(String(180))
    xml_email: Mapped[str | None] = mapped_column(String(180))
    portal_url: Mapped[str | None] = mapped_column(String(500))
    billing_instructions: Mapped[str | None] = mapped_column(Text)
    financial_notes: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CustomerNote(Base):
    __tablename__ = "customer_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_customers.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(40), default="general", index=True)
    text: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomerDocument(Base):
    __tablename__ = "customer_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_customers.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(40), default="other", index=True)
    reference_number: Mapped[str | None] = mapped_column(String(120), index=True)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
