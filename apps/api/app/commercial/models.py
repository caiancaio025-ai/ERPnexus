from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class CommercialCompanyProfile(Base):
    __tablename__ = "commercial_company_profiles"
    __table_args__ = (UniqueConstraint("company_code", name="uq_commercial_company_profile_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    legal_name: Mapped[str] = mapped_column(String(180))
    trade_name: Mapped[str | None] = mapped_column(String(180))
    document: Mapped[str | None] = mapped_column(String(20))
    state_registration: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(180))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(240))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    rental_daily_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    rental_monthly_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    condition: Mapped[str | None] = mapped_column(String(40))
    stock_status: Mapped[str] = mapped_column(String(30), default="available", index=True)
    location: Mapped[str | None] = mapped_column(String(120))
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommercialQuote(Base):
    __tablename__ = "commercial_quotes"
    __table_args__ = (UniqueConstraint("quote_number", "revision", name="uq_commercial_quote_number_revision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[str | None] = mapped_column(String(30), index=True)
    quote_type: Mapped[str] = mapped_column(String(20), index=True)  # sale | rental | preventive
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("laboratory_customers.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    issue_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    valid_until: Mapped[date | None] = mapped_column(Date)
    title: Mapped[str | None] = mapped_column(String(220))
    intro_text: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    delivery_terms: Mapped[str | None] = mapped_column(Text)
    warranty_terms: Mapped[str | None] = mapped_column(Text)
    rental_terms: Mapped[str | None] = mapped_column(Text)
    preventive_scope: Mapped[str | None] = mapped_column(Text)
    exclusions: Mapped[str | None] = mapped_column(Text)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommercialQuoteItem(Base):
    __tablename__ = "commercial_quote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("commercial_quotes.id", ondelete="CASCADE"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("commercial_equipment.id", ondelete="SET NULL"), index=True)
    description: Mapped[str] = mapped_column(String(280))
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(160))
    power: Mapped[str | None] = mapped_column(String(80))
    voltage: Mapped[str | None] = mapped_column(String(80))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1)
    unit: Mapped[str] = mapped_column(String(20), default="UN")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    rental_period_count: Mapped[int | None] = mapped_column(Integer)
    rental_period_unit: Mapped[str | None] = mapped_column(String(20))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CommercialPreventiveOrder(Base):
    __tablename__ = "commercial_preventive_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str | None] = mapped_column(String(30), unique=True, index=True)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("commercial_quotes.id", ondelete="SET NULL"), index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("laboratory_customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", index=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date)
    technical_notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
