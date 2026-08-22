from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class CommercialEquipment(Base):
    __tablename__ = "commercial_equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    serial_code: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    purpose: Mapped[str] = mapped_column(String(30), default="rental_sale", index=True)
    equipment_type: Mapped[str] = mapped_column(String(180), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), index=True)
    model: Mapped[str | None] = mapped_column(String(160), index=True)
    power: Mapped[str | None] = mapped_column(String(80))
    voltage: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
