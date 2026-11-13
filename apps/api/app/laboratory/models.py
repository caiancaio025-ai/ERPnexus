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


class LaboratoryWorkflowOption(Base):
    __tablename__ = "laboratory_workflow_options"
    __table_args__ = (
        UniqueConstraint("kind", "code", name="uq_lab_workflow_option_kind_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )



class LaboratoryArea(Base):
    __tablename__ = "laboratory_areas"
    __table_args__ = (UniqueConstraint("code", name="uq_laboratory_area_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LaboratoryRack(Base):
    __tablename__ = "laboratory_racks"
    __table_args__ = (
        UniqueConstraint("code", name="uq_laboratory_rack_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_areas.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(12), index=True)
    name: Mapped[str] = mapped_column(String(120))
    position_prefix: Mapped[str] = mapped_column(String(4))
    rows: Mapped[int] = mapped_column(Integer, default=3)
    columns: Mapped[int] = mapped_column(Integer, default=2)
    layout_row: Mapped[int] = mapped_column(Integer, default=1)
    layout_column: Mapped[int] = mapped_column(Integer, default=1)
    layout_span: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LaboratoryLocation(Base):
    __tablename__ = "laboratory_locations"
    __table_args__ = (UniqueConstraint("code", name="uq_laboratory_location_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_areas.id", ondelete="RESTRICT"), index=True
    )
    rack_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_racks.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(8), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
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
    entry_invoice_2: Mapped[str | None] = mapped_column(String(80), index=True)
    entry_invoice_3: Mapped[str | None] = mapped_column(String(80), index=True)
    entry_invoice_access_key: Mapped[str | None] = mapped_column(String(44), index=True)
    exit_invoice: Mapped[str | None] = mapped_column(String(80), index=True)
    exit_invoice_2: Mapped[str | None] = mapped_column(String(80), index=True)
    exit_invoice_3: Mapped[str | None] = mapped_column(String(80), index=True)
    exit_invoice_access_key: Mapped[str | None] = mapped_column(String(44), index=True)
    warranty_invoice: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_invoice_2: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_invoice_3: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_entry_invoice_1: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_entry_invoice_2: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_entry_invoice_3: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_exit_invoice_1: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_exit_invoice_2: Mapped[str | None] = mapped_column(String(80), index=True)
    warranty_exit_invoice_3: Mapped[str | None] = mapped_column(String(80), index=True)
    is_inactive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    inactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inactivated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    inactivation_reason: Mapped[str | None] = mapped_column(String(500))
    storage_location: Mapped[str | None] = mapped_column(String(8), index=True)
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
    substatuses: Mapped[list["LaboratoryWorkOrderSubstatus"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    location_history: Mapped[list["LaboratoryLocationHistory"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="LaboratoryLocationHistory.assigned_at"
    )


class LaboratoryLocationHistory(Base):
    __tablename__ = "laboratory_location_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    location: Mapped[str] = mapped_column(String(8), index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


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


class LaboratoryReleaseEvent(Base):
    __tablename__ = "laboratory_release_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    technician_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_technicians.id", ondelete="SET NULL"), nullable=True, index=True
    )
    technician_name: Mapped[str | None] = mapped_column(String(160))
    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    released_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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


class LaboratoryWorkOrderSubstatus(Base):
    __tablename__ = "laboratory_work_order_substatuses"
    __table_args__ = (
        UniqueConstraint("work_order_id", "code", name="uq_lab_work_order_substatus_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )



class LaboratoryMechanicalPaintingDispatch(Base):
    __tablename__ = "laboratory_mechanical_painting_dispatches"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    provider: Mapped[str | None] = mapped_column(String(180))
    notes: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    sent_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    returned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LaboratoryMechanicalPaintingItem(Base):
    __tablename__ = "laboratory_mechanical_painting_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    dispatch_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_mechanical_painting_dispatches.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(String(300))
    returned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    return_note: Mapped[str | None] = mapped_column(String(300))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LaboratoryMechanicalPaintingPhoto(Base):
    __tablename__ = "laboratory_mechanical_painting_photos"
    __table_args__ = (
        UniqueConstraint("dispatch_id", "document_id", name="uq_lab_mech_paint_photo_document"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dispatch_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_mechanical_painting_dispatches.id", ondelete="CASCADE"),
        index=True,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_documents.id", ondelete="RESTRICT"), index=True
    )
    phase: Mapped[str] = mapped_column(String(20), default="outbound", index=True)
    position: Mapped[int] = mapped_column(Integer, default=1)
    caption: Mapped[str | None] = mapped_column(String(300))
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
    billing_terms: Mapped[str | None] = mapped_column(String(200))
    warranty_months: Mapped[int] = mapped_column(Integer, default=3)
    warranty_terms: Mapped[str | None] = mapped_column(String(200))
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
    company_snapshot: Mapped[str | None] = mapped_column(Text)
    emitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["LaboratoryQuoteItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="LaboratoryQuoteItem.position"
    )
    photos: Mapped[list["LaboratoryQuotePhoto"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="LaboratoryQuotePhoto.position"
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


class LaboratoryQuotePhoto(Base):
    __tablename__ = "laboratory_quote_photos"
    __table_args__ = (
        UniqueConstraint("quote_id", "document_id", name="uq_lab_quote_photo_document"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_quotes.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_documents.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=1)
    caption: Mapped[str | None] = mapped_column(String(300))
    document: Mapped["LaboratoryDocument"] = relationship(lazy="joined")


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
