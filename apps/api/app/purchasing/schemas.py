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
