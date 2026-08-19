from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class Supplier(Base):
    __tablename__ = "purchase_suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    origin: Mapped[str] = mapped_column(String(20), default="national")
    website: Mapped[str | None] = mapped_column(String(500))
    contact_name: Mapped[str | None] = mapped_column(String(150))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("purchase_suppliers.id"), index=True)
    supplier_name: Mapped[str] = mapped_column(String(180))
    laboratory_equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_equipment.id"), index=True
    )
    laboratory_work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_work_orders.id"), index=True
    )
    equipment_serial: Mapped[str | None] = mapped_column(String(120), index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True)
    client_destination: Mapped[str | None] = mapped_column(String(180), index=True)
    product_name: Mapped[str] = mapped_column(String(250), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    origin: Mapped[str] = mapped_column(String(20), default="national")
    tracking_code: Mapped[str | None] = mapped_column(String(120), index=True)
    purchase_date: Mapped[date] = mapped_column(Date, index=True)
    estimated_delivery_date: Mapped[date] = mapped_column(Date, index=True)
    delivered_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="awaiting_payment", index=True)
    product_link: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(Text)
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment_path: Mapped[str | None] = mapped_column(String(1000))
    attachment_mime: Mapped[str | None] = mapped_column(String(100))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PurchaseAuditEvent(Base):
    __tablename__ = "purchase_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
