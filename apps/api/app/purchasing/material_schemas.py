from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MaterialPriority = Literal["low", "normal", "high", "urgent"]
MaterialRequestStatus = Literal[
    "awaiting_approval",
    "approved",
    "rejected",
    "purchasing",
    "purchased",
    "in_transit",
    "received",
    "delivered_to_lab",
    "cancelled",
]


class MaterialRequestCreate(BaseModel):
    item_name: str = Field(min_length=2, max_length=250)
    quantity: int = Field(default=1, ge=1, le=100000)
    priority: MaterialPriority = "normal"
    technical_note: str | None = None
    suggested_link: str | None = Field(default=None, max_length=1000)


class StandaloneMaterialRequestCreate(MaterialRequestCreate):
    company_code: str = Field(min_length=2, max_length=40)


class MaterialRequestUpdate(BaseModel):
    status: MaterialRequestStatus
    supplier_name: str | None = Field(default=None, max_length=180)
    purchase_reference: str | None = Field(default=None, max_length=100)
    purchase_link: str | None = Field(default=None, max_length=1000)
    tracking_code: str | None = Field(default=None, max_length=120)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    expected_delivery_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


class MaterialRequestOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    company_code: str
    work_order_id: int | None
    work_order_number: str | None
    equipment_id: int | None
    equipment_serial: str | None
    customer_name: str | None
    source_type: str
    requester_user_id: int
    requester_name: str
    item_name: str
    quantity: int
    priority: MaterialPriority
    technical_note: str | None
    suggested_link: str | None
    status: MaterialRequestStatus
    supplier_name: str | None
    purchase_reference: str | None
    purchase_link: str | None
    tracking_code: str | None
    unit_cost: Decimal | None
    expected_delivery_date: date | None
    purchased_at: datetime | None
    received_at: datetime | None
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MaterialRequestEventOutput(BaseModel):
    id: int
    event_type: str
    previous_status: str | None
    new_status: str | None
    note: str | None
    user_id: int
    user_name: str
    created_at: datetime
