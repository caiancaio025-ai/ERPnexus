from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CompanyCode = Literal["universo_eletronica", "universo_automacao", "solucoes_eletronica"]
PurchaseOrigin = Literal["national", "international"]
PurchaseStatus = Literal[
    "awaiting_payment", "ordered", "processing", "shipped", "customs", "delivered", "cancelled"
]


class SupplierInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    origin: PurchaseOrigin = "national"
    website: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=150)
    contact_phone: str | None = Field(default=None, max_length=40)


class SupplierOutput(SupplierInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime | None = None


class PurchaseInput(BaseModel):
    company_code: CompanyCode
    supplier_id: int
    equipment_serial: str | None = Field(default=None, max_length=120)
    invoice_number: str | None = Field(default=None, max_length=100)
    client_destination: str | None = Field(default=None, max_length=180)
    product_name: str = Field(min_length=2, max_length=250)
    # Configuração de entrada opcional durante a compra; obrigatória ao receber.
    inventory_destination: Literal["new", "existing"] | None = None
    inventory_item_id: int | None = Field(default=None, gt=0)
    inventory_name: str | None = Field(default=None, max_length=220)
    inventory_mode: Literal["bulk", "serialized"] | None = None
    inventory_serial: str | None = Field(default=None, max_length=120)
    inventory_category: str | None = Field(default=None, max_length=80)
    inventory_format_id: int | None = Field(default=None, gt=0)
    quantity: int = Field(default=1, ge=1, le=100000)
    total_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    origin: PurchaseOrigin = "national"
    tracking_code: str | None = Field(default=None, max_length=120)
    purchase_date: date
    estimated_delivery_date: date
    status: PurchaseStatus = "awaiting_payment"
    product_link: str | None = Field(default=None, max_length=1000)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "PurchaseInput":
        if self.estimated_delivery_date < self.purchase_date:
            raise ValueError("A previsão de entrega não pode ser anterior à data da compra.")
        if self.status == "delivered":
            if self.inventory_destination == "existing" and not self.inventory_item_id:
                raise ValueError("Selecione o item de estoque para somar o recebimento.")
            if self.inventory_destination == "new":
                if not (self.inventory_name or "").strip() or len(self.inventory_name.strip()) < 2:
                    raise ValueError("Informe o nome do item no Estoque antes de confirmar o recebimento.")
                if self.inventory_mode == "serialized":
                    if self.quantity != 1 or not (self.inventory_serial or "").strip():
                        raise ValueError("Item individual exige quantidade 1 e número de série.")
        return self


class PurchaseUpdate(PurchaseInput):
    delivered_at: date | None = None


class PurchaseOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    company_code: CompanyCode
    supplier_id: int
    supplier_name: str
    equipment_serial: str | None
    invoice_number: str | None
    client_destination: str | None
    product_name: str
    quantity: int
    total_amount: Decimal | None
    origin: PurchaseOrigin
    tracking_code: str | None
    purchase_date: date
    estimated_delivery_date: date
    delivered_at: date | None
    status: PurchaseStatus
    product_link: str | None
    notes: str | None
    attachment_name: str | None
    attachment_mime: str | None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_legacy_status(cls, value: object) -> object:
        # Compatibilidade com pedidos criados por versões antigas do NEXUS.
        # O status histórico `in_transit` representa o mesmo estágio atual
        # chamado `shipped` (Em transporte). Normalizamos apenas na saída,
        # sem alterar silenciosamente o registro no banco.
        if value == "in_transit":
            return "shipped"
        return value

    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseSummary(BaseModel):
    total_open: int
    overdue: int
    due_soon: int
    delivered_month: int
    total_value_open: Decimal | None


class PurchaseAuditOutput(BaseModel):
    id: int
    purchase_id: int | None
    action: str
    description: str
    user_id: int
    user_name: str
    created_at: datetime

PurchaseSpendingSource = Literal["purchase_order", "material_request"]


class PurchaseSpendingItem(BaseModel):
    source: PurchaseSpendingSource
    source_id: int
    code: str
    company_code: str
    purchase_date: date
    supplier_name: str
    item_name: str
    quantity: int
    amount: Decimal
    status: str
    work_order_id: int | None = None
    work_order_number: str | None = None
    customer_name: str | None = None
    equipment_serial: str | None = None
    purchase_reference: str | None = None


class PurchaseSpendingSummary(BaseModel):
    purchase_count: int
    total_spent: Decimal
    purchase_order_total: Decimal
    material_request_total: Decimal
    average_purchase: Decimal


class PurchaseSpendingBreakdown(BaseModel):
    key: str
    label: str
    count: int
    amount: Decimal


class PurchaseSpendingMonth(BaseModel):
    month: str
    count: int
    amount: Decimal


class PurchaseSpendingReport(BaseModel):
    start_date: date
    end_date: date
    company_code: str | None
    summary: PurchaseSpendingSummary
    by_supplier: list[PurchaseSpendingBreakdown]
    by_source: list[PurchaseSpendingBreakdown]
    by_month: list[PurchaseSpendingMonth]
    items: list[PurchaseSpendingItem]
