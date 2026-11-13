"""Contratos públicos do estoque; custo monetário filtrado por perfil no router."""
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator


class TypeInput(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=90)


class CategoryInput(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)


class SubtypeInput(BaseModel):
    category: str = Field(min_length=2, max_length=80)
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)


class FormatInput(BaseModel):
    category: str = Field(min_length=2, max_length=80)
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)


class AreaInput(BaseModel):
    code: str = Field(min_length=2, max_length=24, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)


class ContainerInput(BaseModel):
    area_id: int = Field(gt=0)
    type_id: int = Field(gt=0)
    parent_id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    rows: int = Field(default=1, ge=1, le=20)
    columns: int = Field(default=1, ge=1, le=20)
    layout_row: int = Field(default=1, ge=1, le=50)
    layout_column: int = Field(default=1, ge=1, le=12)
    layout_span: int = Field(default=1, ge=1, le=12)


class ContainerUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    layout_row: int = Field(ge=1, le=50)
    layout_column: int = Field(ge=1, le=12)
    layout_span: int = Field(ge=1, le=12)
    is_active: bool


class ItemInput(BaseModel):
    company_code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=220)
    category: str = Field(default="outros", max_length=80)
    subtype_id: int | None = Field(default=None, gt=0)
    format_id: int | None = Field(default=None, gt=0)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    mode: str = Field(pattern=r"^(serialized|bulk)$")
    manufacturer_serial: str | None = Field(default=None, max_length=120)
    unit: str = Field(default="UN", max_length=12)
    quantity: int = Field(default=1, ge=0, le=1000000)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    slot_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode == "serialized" and (self.quantity != 1 or not (self.manufacturer_serial or "").strip()):
            raise ValueError("Item serializado exige um número de série e quantidade exatamente 1.")
        return self


class ItemUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    category: str = Field(max_length=80)
    subtype_id: int | None = Field(default=None, gt=0)
    format_id: int | None = Field(default=None, gt=0)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    slot_id: int | None = Field(default=None, gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool = True


class MovementInput(BaseModel):
    quantity: int = Field(ge=1, le=1000000)
    work_order_id: int | None = Field(default=None, gt=0)
    reversal_of_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)
