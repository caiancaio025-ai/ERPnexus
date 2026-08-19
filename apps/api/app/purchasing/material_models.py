from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class MaterialRequest(Base):
    __tablename__ = "material_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"), index=True
    )
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("laboratory_equipment.id", ondelete="CASCADE"), index=True
    )
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(250), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    technical_note: Mapped[str | None] = mapped_column(Text)
    suggested_link: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(40), default="awaiting_approval", index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(180))
    purchase_reference: Mapped[str | None] = mapped_column(String(100))
    purchase_link: Mapped[str | None] = mapped_column(String(1000))
    tracking_code: Mapped[str | None] = mapped_column(String(120))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MaterialRequestEvent(Base):
    __tablename__ = "material_request_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_request_id: Mapped[int] = mapped_column(
        ForeignKey("material_requests.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str | None] = mapped_column(String(40), index=True)
    note: Mapped[str | None] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
