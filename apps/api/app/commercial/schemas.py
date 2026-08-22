from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CompanyCode = Literal["universo_eletronica", "universo_automacao", "solucoes_eletronica"]
CommercialPurpose = Literal["rental_sale", "preventive"]


class CommercialEquipmentInput(BaseModel):
    company_code: CompanyCode = "universo_eletronica"
    purpose: CommercialPurpose = "rental_sale"
    equipment_type: str = Field(min_length=2, max_length=180)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=160)
    power: str | None = Field(default=None, max_length=80)
    voltage: str | None = Field(default=None, max_length=80)
    notes: str | None = None


class CommercialEquipmentOutput(CommercialEquipmentInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    serial_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
