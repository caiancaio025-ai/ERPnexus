from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CustomerUpdate(BaseModel):
    document: str | None = None
    legal_name: str = Field(min_length=1, max_length=180)
    trade_name: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    website: str | None = None
    postal_code: str | None = None
    address: str | None = None
    address_number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    notes: str | None = None


class CustomerCreate(CustomerUpdate):
    company_code: Literal["universo_eletronica", "universo_automacao", "solucoes_eletronica"]


class CustomerListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_code: str
    document: str | None
    legal_name: str
    trade_name: str | None
    phone: str | None
    email: str | None
    city: str | None
    state: str | None
    is_active: bool


class CustomerPage(BaseModel):
    items: list[CustomerListItem]
    page: int
    page_size: int
    total: int
    pages: int


class ContactInput(BaseModel):
    department: str | None = None
    name: str = Field(min_length=1, max_length=160)
    job_title: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    is_primary: bool = False
    receives_quotes: bool = False
    receives_invoices: bool = False
    receives_reports: bool = False
    receives_service_updates: bool = False
    notes: str | None = None


class ContactOutput(ContactInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    is_active: bool
    created_at: datetime


class BillingInput(BaseModel):
    billing_cutoff_day: int | None = Field(default=None, ge=1, le=31)
    payment_term_days: int | None = Field(default=None, ge=0, le=365)
    requires_purchase_order: bool = False
    requires_customer_order: bool = False
    requires_measurement: bool = False
    requires_service_report: bool = False
    invoice_email: str | None = None
    xml_email: str | None = None
    portal_url: str | None = None
    billing_instructions: str | None = None
    financial_notes: str | None = None


class BillingOutput(BillingInput):
    model_config = ConfigDict(from_attributes=True)
    customer_id: int
    updated_at: datetime


class NoteInput(BaseModel):
    category: Literal[
        "general", "commercial", "financial", "technical", "administrative"
    ] = "general"
    text: str = Field(min_length=1, max_length=5000)


class NoteOutput(NoteInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    created_by: int
    created_at: datetime


class DocumentOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    category: str
    reference_number: str | None
    issue_date: date | None
    expiration_date: date | None
    original_name: str
    mime_type: str
    size_bytes: int
    notes: str | None
    created_at: datetime


class CustomerEquipmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    serial_number: str | None
    manufacturer: str | None
    model: str | None
    equipment_type: str | None
    power: str | None
    voltage: str | None


class CustomerWorkOrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    equipment_id: int
    equipment_serial: str | None
    status: str
    priority: str
    opened_at: date
    quoted_value: float | None
    approved_value: float | None


class CustomerQuoteSummary(BaseModel):
    id: int
    work_order_id: int
    work_order_number: str
    revision: int
    status: str
    total: float
    emitted_at: datetime | None
    created_at: datetime


class CustomerDetail(BaseModel):
    id: int
    company_code: str
    document: str | None
    legal_name: str
    trade_name: str | None
    state_registration: str | None
    municipal_registration: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    website: str | None
    postal_code: str | None
    address: str | None
    address_number: str | None
    complement: str | None
    district: str | None
    city: str | None
    state: str | None
    notes: str | None
    is_active: bool
    work_orders_count: int
    quotes_count: int
    contacts: list[ContactOutput]
    billing: BillingOutput | None
    notes_history: list[NoteOutput]
    documents: list[DocumentOutput]
    equipment: list[CustomerEquipmentSummary]
    work_orders: list[CustomerWorkOrderSummary]
    quotes: list[CustomerQuoteSummary]
