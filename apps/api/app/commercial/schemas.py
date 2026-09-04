from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CompanyCode = Literal["universo_eletronica", "universo_automacao", "solucoes_eletronica"]
CommercialPurpose = Literal["rental_sale", "preventive"]
StockStatus = Literal["available", "reserved", "rented", "sold", "maintenance", "inactive"]
RentalPeriodUnit = Literal["day", "week", "month"]
QuoteType = Literal["sale", "rental", "preventive"]
QuoteStatus = Literal["draft", "issued", "approved", "rejected", "cancelled"]


class CompanyProfileInput(BaseModel):
    company_code: CompanyCode
    legal_name: str = Field(min_length=2, max_length=180)
    trade_name: str | None = Field(default=None, max_length=180)
    document: str | None = Field(default=None, max_length=20)
    state_registration: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)


class CompanyProfileOutput(CompanyProfileInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CommercialEquipmentInput(BaseModel):
    company_code: CompanyCode = "universo_eletronica"
    purpose: CommercialPurpose = "rental_sale"
    equipment_type: str = Field(min_length=2, max_length=180)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=160)
    power: str | None = Field(default=None, max_length=80)
    voltage: str | None = Field(default=None, max_length=80)
    quantity: int = Field(default=1, ge=0, le=1_000_000)
    unit_cost: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    rental_daily_price: float | None = Field(default=None, ge=0)
    rental_monthly_price: float | None = Field(default=None, ge=0)
    condition: str | None = Field(default=None, max_length=40)
    stock_status: StockStatus = "available"
    location: str | None = Field(default=None, max_length=120)
    acquisition_date: date | None = None
    notes: str | None = None


class CommercialEquipmentOutput(CommercialEquipmentInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    serial_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class QuoteItemInput(BaseModel):
    equipment_id: int | None = None
    description: str = Field(min_length=1, max_length=280)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=160)
    power: str | None = Field(default=None, max_length=80)
    voltage: str | None = Field(default=None, max_length=80)
    serial_number: str | None = Field(default=None, max_length=120)
    quantity: float = Field(default=1, gt=0)
    unit: str = Field(default="UN", min_length=1, max_length=20)
    unit_price: float = Field(default=0, ge=0)
    discount_pct: float = Field(default=0, ge=0, le=100)
    rental_period_count: int | None = Field(default=None, ge=1, le=3650)
    rental_period_unit: RentalPeriodUnit | None = None


class QuoteItemOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipment_id: int | None
    description: str
    manufacturer: str | None
    model: str | None
    power: str | None
    voltage: str | None
    serial_number: str | None
    quantity: float
    unit: str
    unit_price: float | None
    discount_pct: float
    rental_period_count: int | None
    rental_period_unit: str | None
    line_total: float | None
    sort_order: int


class CommercialQuoteInput(BaseModel):
    quote_type: QuoteType
    company_code: CompanyCode
    customer_id: int
    valid_until: date | None = None
    title: str | None = Field(default=None, max_length=220)
    intro_text: str | None = None
    notes: str | None = None
    payment_terms: str | None = None
    delivery_terms: str | None = None
    warranty_terms: str | None = None
    rental_terms: str | None = None
    preventive_scope: str | None = None
    exclusions: str | None = None
    items: list[QuoteItemInput] = Field(min_length=1, max_length=200)


class CommercialQuoteOutput(BaseModel):
    id: int
    quote_number: str
    quote_type: str
    company_code: str
    customer_id: int
    customer_name: str
    revision: int
    status: str
    issue_date: date
    valid_until: date | None
    title: str | None
    intro_text: str | None
    notes: str | None
    payment_terms: str | None
    delivery_terms: str | None
    warranty_terms: str | None
    rental_terms: str | None
    preventive_scope: str | None
    exclusions: str | None
    total: float | None
    issued_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[QuoteItemOutput]


class QuoteStatusInput(BaseModel):
    status: QuoteStatus


class PreventiveOrderInput(BaseModel):
    quote_id: int
    scheduled_date: date | None = None
    technical_notes: str | None = None


class PreventiveOrderUpdate(BaseModel):
    status: Literal["scheduled", "in_progress", "completed", "delivered", "cancelled"]
    scheduled_date: date | None = None
    completed_date: date | None = None
    technical_notes: str | None = None


class PreventiveOrderOutput(BaseModel):
    id: int
    order_number: str
    quote_id: int | None
    company_code: str
    customer_id: int
    customer_name: str
    status: str
    scheduled_date: date | None
    completed_date: date | None
    technical_notes: str | None
    created_at: datetime
    updated_at: datetime
