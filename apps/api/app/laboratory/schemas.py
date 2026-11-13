from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CompanyCode = str
LaboratoryPriority = Literal["low", "normal", "high", "urgent"]
LaboratoryStatus = str
DocumentCategory = Literal["entrada", "analise", "reparo", "testes", "saida", "pintura", "general"]
WorkflowOptionKind = Literal["status", "substatus"]


class CustomerInput(BaseModel):
    company_code: CompanyCode = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")
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
    company_code: CompanyCode = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")
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
    company_code: CompanyCode = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")
    customer_id: int | None = None
    customer_name: str = Field(min_length=1, max_length=180)
    serial_number: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    equipment_type: str | None = None
    power: str | None = None
    voltage: str | None = None
    entry_invoice: str | None = Field(default=None, max_length=80)
    entry_invoice_2: str | None = Field(default=None, max_length=80)
    entry_invoice_3: str | None = Field(default=None, max_length=80)
    entry_invoice_access_key: str | None = None
    exit_invoice: str | None = Field(default=None, max_length=80)
    exit_invoice_2: str | None = Field(default=None, max_length=80)
    exit_invoice_3: str | None = Field(default=None, max_length=80)
    exit_invoice_access_key: str | None = None
    warranty_invoice: str | None = Field(default=None, max_length=80)
    warranty_invoice_2: str | None = Field(default=None, max_length=80)
    warranty_invoice_3: str | None = Field(default=None, max_length=80)
    warranty_entry_invoice_1: str | None = Field(default=None, max_length=80)
    warranty_entry_invoice_2: str | None = Field(default=None, max_length=80)
    warranty_entry_invoice_3: str | None = Field(default=None, max_length=80)
    warranty_exit_invoice_1: str | None = Field(default=None, max_length=80)
    warranty_exit_invoice_2: str | None = Field(default=None, max_length=80)
    warranty_exit_invoice_3: str | None = Field(default=None, max_length=80)
    storage_location: str | None = None
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

    @field_validator("entry_invoice_access_key", "exit_invoice_access_key", mode="before")
    @classmethod
    def validate_invoice_access_key(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if len(digits) != 44:
            raise ValueError("A chave de acesso da NF deve conter exatamente 44 dígitos.")
        return digits

    @field_validator("storage_location", mode="before")
    @classmethod
    def validate_storage_location(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip().upper().replace(" ", "")
        if len(normalized) > 8:
            raise ValueError("O código da localização deve ter no máximo 8 caracteres.")
        return normalized


class WorkOrderUpdate(WorkOrderInput):
    version: int


class InactivateWorkOrderInput(BaseModel):
    version: int
    reason: str = Field(min_length=10, max_length=500)


class StatusChangeInput(BaseModel):
    status: str = Field(min_length=1, max_length=40)
    version: int
    note: str | None = Field(default=None, max_length=500)
    override: bool = False


class WorkflowOptionCreate(BaseModel):
    kind: WorkflowOptionKind
    label: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=10000)


class WorkflowOptionUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=10000)
    is_active: bool = True


class WorkflowOptionOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    code: str
    label: str
    sort_order: int
    is_active: bool
    is_system: bool


class SubstatusToggleInput(BaseModel):
    active: bool
    version: int


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
    entry_invoice_2: str | None
    entry_invoice_3: str | None
    entry_invoice_access_key: str | None
    exit_invoice: str | None
    exit_invoice_2: str | None
    exit_invoice_3: str | None
    exit_invoice_access_key: str | None
    warranty_invoice: str | None
    warranty_invoice_2: str | None
    warranty_invoice_3: str | None
    warranty_entry_invoice_1: str | None
    warranty_entry_invoice_2: str | None
    warranty_entry_invoice_3: str | None
    warranty_exit_invoice_1: str | None
    warranty_exit_invoice_2: str | None
    warranty_exit_invoice_3: str | None
    is_inactive: bool = False
    inactivation_reason: str | None = None
    inactivated_at: datetime | None = None
    storage_location: str | None
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
    substatuses: list[str] = Field(default_factory=list)
    version: int
    created_at: datetime
    updated_at: datetime


class WorkOrderPage(BaseModel):
    items: list[WorkOrderOutput]
    page: int
    page_size: int
    total: int
    pages: int


class LaboratoryLocationOccupantOutput(BaseModel):
    work_order_id: int
    work_order_number: str
    customer_name: str
    equipment_label: str
    status: str
    priority: str
    location_assigned_at: datetime | None = None
    location_duration_seconds: int = 0
    dwell_level: Literal["normal", "attention", "critical"] = "normal"


class LaboratoryLocationSlotOutput(BaseModel):
    location: str
    area_code: str
    area_name: str
    area_sort_order: int
    rack_code: str | None = None
    rack_name: str | None = None
    rack_sort_order: int = 0
    rack_rows: int = 1
    rack_columns: int = 1
    rack_layout_row: int = 1
    rack_layout_column: int = 1
    rack_layout_span: int = 1
    slot_number: int
    occupants: list[LaboratoryLocationOccupantOutput] = Field(default_factory=list)
    occupancy_count: int = 0
    has_urgent: bool = False
    has_attention: bool = False
    has_critical: bool = False
    max_location_duration_seconds: int = 0
    work_order_id: int | None = None
    work_order_number: str | None = None
    customer_name: str | None = None
    equipment_label: str | None = None
    status: str | None = None
    priority: str | None = None


class LaboratoryLocationMapOutput(BaseModel):
    total_positions: int
    occupied_positions: int
    free_positions: int
    located_work_orders: int
    urgent_positions: int
    urgent_work_orders: int
    attention_positions: int
    attention_work_orders: int
    critical_positions: int
    critical_work_orders: int
    work_orders_without_location: int
    slots: list[LaboratoryLocationSlotOutput]



class CompanyMasterInput(BaseModel):
    company_code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")
    legal_name: str = Field(min_length=2, max_length=180)
    trade_name: str | None = Field(default=None, max_length=180)
    document: str | None = Field(default=None, max_length=20)
    state_registration: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)


class CompanyMasterUpdate(BaseModel):
    legal_name: str = Field(min_length=2, max_length=180)
    trade_name: str | None = Field(default=None, max_length=180)
    document: str | None = Field(default=None, max_length=20)
    state_registration: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)
    is_active: bool = True


class CompanyMasterOutput(CompanyMasterInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LaboratoryAreaInput(BaseModel):
    code: str = Field(min_length=2, max_length=8, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=2, max_length=120)
    sort_order: int = Field(default=0, ge=0, le=999)
    direct_assignment: bool = False


class LaboratoryAreaUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    sort_order: int = Field(default=0, ge=0, le=999)
    is_active: bool = True


class LaboratoryAreaOutput(BaseModel):
    id: int
    code: str
    name: str
    sort_order: int
    is_active: bool
    direct_location_code: str | None = None


class LaboratoryRackInput(BaseModel):
    area_id: int
    code: str = Field(min_length=2, max_length=12, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=2, max_length=120)
    position_prefix: str = Field(min_length=1, max_length=4, pattern=r"^[A-Z0-9]+$")
    rows: int = Field(default=3, ge=1, le=20)
    columns: int = Field(default=2, ge=1, le=20)
    layout_row: int = Field(default=1, ge=1, le=50)
    layout_column: int = Field(default=1, ge=1, le=12)
    layout_span: int = Field(default=1, ge=1, le=12)
    sort_order: int = Field(default=0, ge=0, le=999)


class LaboratoryRackUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    layout_row: int = Field(default=1, ge=1, le=50)
    layout_column: int = Field(default=1, ge=1, le=12)
    layout_span: int = Field(default=1, ge=1, le=12)
    sort_order: int = Field(default=0, ge=0, le=999)
    is_active: bool = True


class LaboratoryRackOutput(BaseModel):
    id: int
    area_id: int
    area_code: str
    area_name: str
    code: str
    name: str
    position_prefix: str
    rows: int
    columns: int
    layout_row: int
    layout_column: int
    layout_span: int
    sort_order: int
    is_active: bool


class LaboratoryLocationConfigOutput(BaseModel):
    id: int
    area_id: int
    area_code: str
    area_name: str
    rack_id: int | None
    rack_code: str | None
    rack_name: str | None
    code: str
    name: str
    sort_order: int
    is_active: bool


class LaboratoryLocationConfig(BaseModel):
    areas: list[LaboratoryAreaOutput]
    racks: list[LaboratoryRackOutput]
    locations: list[LaboratoryLocationConfigOutput]


class WorkOrderSummary(BaseModel):
    total_open: int
    analyzed: int
    awaiting_approval: int
    approved: int
    awaiting_analysis: int
    in_repair: int
    in_testing: int
    high_priority: int
    completed_month: int
    approved_total: Decimal | None = None
    awaiting_approval_total: Decimal | None = None


class StatusHistoryOutput(BaseModel):
    id: int
    previous_status: str | None
    new_status: str
    note: str | None
    user_id: int
    user_name: str
    created_at: datetime
    release_event_id: int | None = None
    release_technician_id: int | None = None
    release_technician_name: str | None = None
    release_released_at: datetime | None = None



class LocationHistoryOutput(BaseModel):
    id: int
    location: str
    assigned_at: datetime
    released_at: datetime | None
    changed_by: int
    changed_by_name: str
    duration_seconds: int
    is_current: bool


class PaintingDispatchCreate(BaseModel):
    provider: str | None = Field(default=None, max_length=180)
    notes: str | None = Field(default=None, max_length=3000)
    items: list[str] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("Informe ao menos uma peça ou parte que seguirá para pintura.")
        if any(len(item) > 300 for item in cleaned):
            raise ValueError("Cada item da pintura deve ter no máximo 300 caracteres.")
        return cleaned


class PaintingItemUpdate(BaseModel):
    returned: bool
    return_note: str | None = Field(default=None, max_length=300)


class PaintingItemOutput(BaseModel):
    id: int
    position: int
    description: str
    returned: bool
    return_note: str | None
    returned_at: datetime | None


class PaintingPhotoOutput(BaseModel):
    id: int
    document_id: int
    phase: str
    position: int
    caption: str | None
    original_name: str
    mime_type: str
    created_at: datetime


class PaintingDispatchOutput(BaseModel):
    id: int
    work_order_id: int
    status: str
    provider: str | None
    notes: str | None
    sent_at: datetime | None
    returned_at: datetime | None
    created_by: int
    created_by_name: str
    sent_by: int | None
    sent_by_name: str | None
    returned_by: int | None
    returned_by_name: str | None
    created_at: datetime
    updated_at: datetime
    items: list[PaintingItemOutput]
    photos: list[PaintingPhotoOutput]


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
    unit_value: Decimal | None


class QuotePhotoInput(BaseModel):
    document_id: int
    caption: str | None = Field(default=None, max_length=300)


class QuotePhotoOutput(BaseModel):
    id: int | None = None
    document_id: int
    position: int
    caption: str | None = None
    original_name: str
    mime_type: str


class QuoteInput(BaseModel):
    service_code: str = Field(default="3312102 / 14.01", max_length=50)
    technical_report: str = Field(default="", max_length=20000)
    services_description: str | None = None
    delivery_days: int = 20
    billing_days: int = 21
    billing_terms: str | None = Field(default=None, max_length=200)
    warranty_months: int = 3
    warranty_terms: str | None = Field(default=None, max_length=200)
    payment_terms: str
    validity_days: int = 30
    return_condition: str
    consumer_clause: str
    supply_clause: str
    estimate_clause: str
    discount_type: Literal["none", "amount", "percent"] = "none"
    discount_value: Decimal = Decimal("0")
    items: list[QuoteItemInput]
    photos: list[QuotePhotoInput] = Field(default_factory=list)


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
    billing_terms: str | None
    warranty_months: int
    warranty_terms: str | None
    payment_terms: str
    validity_days: int
    return_condition: str
    consumer_clause: str
    supply_clause: str
    estimate_clause: str
    discount_type: str
    discount_value: Decimal | None
    subtotal: Decimal | None
    total: Decimal | None
    emitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[QuoteItemOutput]
    photos: list[QuotePhotoOutput] = Field(default_factory=list)
class TechnicianProductionPartItem(BaseModel):
    material_request_id: int | None
    code: str
    item_name: str
    quantity: int
    unit_cost: Decimal
    subtotal: Decimal
    status: str


class TechnicianProductionRow(BaseModel):
    release_event_id: int
    released_at: datetime
    technician_id: int | None
    technician_name: str | None
    work_order_id: int
    work_order_number: str
    company_code: str
    customer_id: int | None
    customer_name: str
    equipment_id: int
    equipment_label: str
    equipment_serial: str | None
    invoiced_total: Decimal | None = None
    received_total: Decimal | None = None
    receivable_total: Decimal | None = None
    parts_cost: Decimal | None = None
    parts: list[TechnicianProductionPartItem] = []
    gross_result: Decimal | None = None
    gross_margin_percent: Decimal | None = None


class TechnicianProductionSummary(BaseModel):
    released_equipment_count: int
    release_event_count: int
    invoiced_total: Decimal | None = None
    received_total: Decimal | None = None
    receivable_total: Decimal | None = None
    parts_cost_total: Decimal | None = None
    gross_result: Decimal | None = None
    gross_margin_percent: Decimal | None = None
    gross_margin_percent: Decimal | None = None
    average_invoice: Decimal | None = None
    average_parts_cost: Decimal | None = None


class TechnicianProductionBreakdown(BaseModel):
    technician_id: int | None
    technician_name: str | None
    released_equipment_count: int
    invoiced_total: Decimal | None = None
    received_total: Decimal | None = None
    receivable_total: Decimal | None = None
    parts_cost_total: Decimal | None = None
    gross_result: Decimal | None = None


class TechnicianProductionReport(BaseModel):
    start_date: date
    end_date: date
    sensitive_values_visible: bool
    summary: TechnicianProductionSummary
    by_technician: list[TechnicianProductionBreakdown]
    items: list[TechnicianProductionRow]
