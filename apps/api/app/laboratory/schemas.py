from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CompanyCode = Literal["universo_eletronica", "universo_automacao", "solucoes_eletronica"]
LaboratoryPriority = Literal["low", "normal", "high", "urgent"]
LaboratoryStatus = Literal[
    "received",
    "awaiting_analysis",
    "in_analysis",
    "awaiting_quote",
    "quote_sent",
    "awaiting_approval",
    "approved",
    "rejected",
    "awaiting_parts",
    "in_repair",
    "in_testing",
    "completed",
    "awaiting_pickup",
    "delivered",
    "warranty",
    "invoiced",
    "cancelled",
    "no_repair",
]
DocumentCategory = Literal["entrada", "analise", "reparo", "testes", "saida", "general"]


class CustomerInput(BaseModel):
    company_code: CompanyCode
    document: str | None = None
    legal_name: str = Field(min_length=1, max_length=180)
    trade_name: str | None = None
    state_registration: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    postal_code: str | None = None
    address: str | None = None
    address_number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    notes: str | None = None


class CustomerOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_code: str
    document: str | None
    legal_name: str
    trade_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    state: str | None
    is_active: bool


class TechnicianInput(BaseModel):
    company_code: CompanyCode
    name: str = Field(min_length=1, max_length=160)
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    color: str | None = None
    user_id: int | None = None


class TechnicianUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    color: str | None = None


class TechnicianOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_code: str
    name: str
    specialty: str | None
    phone: str | None
    email: str | None
    color: str | None
    user_id: int | None
    is_active: bool


class WorkOrderInput(BaseModel):
    company_code: CompanyCode
    customer_id: int | None = None
    customer_name: str = Field(min_length=1, max_length=180)
    serial_number: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    equipment_type: str | None = None
    power: str | None = None
    voltage: str | None = None
    entry_invoice: str | None = None
    exit_invoice: str | None = None
    assigned_technician_id: int | None = None
    priority: LaboratoryPriority = "normal"
    reported_defect: str = Field(min_length=1)
    entry_condition: str | None = None
    accessories_received: str | None = None
    parts_cost: str | None = None
    quoted_value: str | None = None
    approved_value: str | None = None
    internal_notes: str | None = None
    customer_notes: str | None = None


class WorkOrderUpdate(WorkOrderInput):
    version: int


class StatusChangeInput(BaseModel):
    status: LaboratoryStatus
    version: int
    note: str | None = Field(default=None, max_length=500)


class WorkOrderOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    company_code: str
    customer_id: int | None
    equipment_id: int
    customer_name: str
    equipment_serial: str | None
    equipment_type: str | None
    manufacturer: str | None
    model: str | None
    power: str | None
    voltage: str | None
    equipment_notes: str | None
    entry_invoice: str | None
    exit_invoice: str | None
    status: LaboratoryStatus
    priority: LaboratoryPriority
    reported_defect: str
    entry_condition: str | None
    accessories_received: str | None
    assigned_technician_id: int | None
    opened_at: date
    completed_at: datetime | None
    delivered_at: datetime | None
    parts_cost: Decimal | None
    quoted_value: Decimal | None
    approved_value: Decimal | None
    internal_notes: str | None
    customer_notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class WorkOrderPage(BaseModel):
    items: list[WorkOrderOutput]
    page: int
    page_size: int
    total: int
    pages: int


class WorkOrderSummary(BaseModel):
    total_open: int
    awaiting_analysis: int
    in_repair: int
    in_testing: int
    high_priority: int
    completed_month: int


class StatusHistoryOutput(BaseModel):
    id: int
    previous_status: str | None
    new_status: str
    note: str | None
    user_id: int
    user_name: str
    created_at: datetime


class DocumentOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    category: str
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class QuoteItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Decimal("1")
    unit_value: Decimal = Decimal("0")


class QuoteItemOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    position: int | None = None
    description: str
    quantity: Decimal
    unit_value: Decimal


class QuoteInput(BaseModel):
    service_code: str = Field(default="3312102 / 14.01", max_length=50)
    technical_report: str = Field(min_length=1)
    services_description: str | None = None
    delivery_days: int = 20
    billing_days: int = 21
    warranty_months: int = 3
    payment_terms: str
    validity_days: int = 30
    return_condition: str
    consumer_clause: str
    supply_clause: str
    estimate_clause: str
    discount_type: Literal["none", "amount", "percent"] = "none"
    discount_value: Decimal = Decimal("0")
    items: list[QuoteItemInput]


class QuoteOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    revision: int
    status: str
    service_code: str
    technical_report: str
    services_description: str | None
    delivery_days: int
    billing_days: int
    warranty_months: int
    payment_terms: str
    validity_days: int
    return_condition: str
    consumer_clause: str
    supply_clause: str
    estimate_clause: str
    discount_type: str
    discount_value: Decimal
    subtotal: Decimal
    total: Decimal
    emitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[QuoteItemOutput]
