from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base


class LaboratoryCustomer(Base):
    __tablename__ = "laboratory_customers"
    __table_args__ = (
        UniqueConstraint("company_code", "document", name="uq_lab_customer_company_document"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    document: Mapped[str | None] = mapped_column(String(20), index=True)
    legal_name: Mapped[str] = mapped_column(String(180), index=True)
    trade_name: Mapped[str | None] = mapped_column(String(180), index=True)
    state_registration: Mapped[str | None] = mapped_column(String(30))
    municipal_registration: Mapped[str | None] = mapped_column(String(30))
    phone: Mapped[str | None] = mapped_column(String(40))
    whatsapp: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(180), index=True)
    website: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(12))
    address: Mapped[str | None] = mapped_column(String(220))
    address_number: Mapped[str | None] = mapped_column(String(30))
    complement: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(2))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LaboratoryTechnician(Base):
    __tablename__ = "laboratory_technicians"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    specialty: Mapped[str | None] = mapped_column(String(180))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(180), index=True)
    color: Mapped[str | None] = mapped_column(String(12))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LaboratoryEquipment(Base):
    __tablename__ = "laboratory_equipment"
    __table_args__ = (
        UniqueConstraint(
            "company_code", "serial_normalized", name="uq_laboratory_equipment_company_serial"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_customers.id"), index=True
    )
    customer_name: Mapped[str] = mapped_column(String(180), index=True)
    serial_number: Mapped[str | None] = mapped_column(String(120))
    serial_normalized: Mapped[str | None] = mapped_column(String(120), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), index=True)
    model: Mapped[str | None] = mapped_column(String(160), index=True)
    equipment_type: Mapped[str | None] = mapped_column(String(120), index=True)
    power: Mapped[str | None] = mapped_column(String(80))
    voltage: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LaboratoryWorkOrder(Base):
    __tablename__ = "laboratory_work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("laboratory_equipment.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_customers.id"), index=True
    )
    customer_name: Mapped[str] = mapped_column(String(180), index=True)
    equipment_serial: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default="received", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    reported_defect: Mapped[str] = mapped_column(Text)
    entry_condition: Mapped[str | None] = mapped_column(Text)
    accessories_received: Mapped[str | None] = mapped_column(Text)
    assigned_technician_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_technicians.id"), index=True
    )
    opened_at: Mapped[date] = mapped_column(Date, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    customer_notes: Mapped[str | None] = mapped_column(Text)
    entry_invoice: Mapped[str | None] = mapped_column(String(80), index=True)
    exit_invoice: Mapped[str | None] = mapped_column(String(80), index=True)
    parts_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    quoted_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    approved_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tracking_token: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    equipment: Mapped[LaboratoryEquipment] = relationship(lazy="joined")
    technician: Mapped[LaboratoryTechnician | None] = relationship(lazy="joined")
    history: Mapped[list["LaboratoryStatusHistory"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="LaboratoryStatusHistory.created_at"
    )
    quotes: Mapped[list["LaboratoryQuote"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="LaboratoryQuote.revision.desc()"
    )
    documents: Mapped[list["LaboratoryDocument"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class LaboratoryStatusHistory(Base):
    __tablename__ = "laboratory_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40), index=True)
    note: Mapped[str | None] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LaboratoryAuditEvent(Base):
    __tablename__ = "laboratory_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LaboratoryQuote(Base):
    __tablename__ = "laboratory_quotes"
    __table_args__ = (
        UniqueConstraint("work_order_id", "revision", name="uq_lab_quote_work_order_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    service_code: Mapped[str] = mapped_column(String(50), default="3312102 / 14.01")
    technical_report: Mapped[str] = mapped_column(Text)
    services_description: Mapped[str | None] = mapped_column(Text)
    delivery_days: Mapped[int] = mapped_column(Integer, default=20)
    billing_days: Mapped[int] = mapped_column(Integer, default=21)
    warranty_months: Mapped[int] = mapped_column(Integer, default=3)
    payment_terms: Mapped[str] = mapped_column(String(500))
    validity_days: Mapped[int] = mapped_column(Integer, default=30)
    return_condition: Mapped[str] = mapped_column(String(500))
    consumer_clause: Mapped[str] = mapped_column(Text)
    supply_clause: Mapped[str] = mapped_column(Text)
    estimate_clause: Mapped[str] = mapped_column(Text)
    discount_type: Mapped[str] = mapped_column(String(20), default="none")
    discount_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    emitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["LaboratoryQuoteItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="LaboratoryQuoteItem.position"
    )


class LaboratoryQuoteItem(Base):
    __tablename__ = "laboratory_quote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_quotes.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    unit_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LaboratoryDocument(Base):
    __tablename__ = "laboratory_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(40), default="general", index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
