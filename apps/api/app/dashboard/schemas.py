from typing import Literal

from pydantic import BaseModel


class Alert(BaseModel):
    key: str
    label: str
    value: int
    detail: str
    tone: Literal["danger", "warning", "info"]
    target: str


class PurchaseEvent(BaseModel):
    id: int
    code: str
    supplier: str
    message: str
    due_label: str
    status: Literal["overdue", "due_soon"]
    target: str


class QuickAction(BaseModel):
    key: Literal["new_work_order", "new_budget", "unnoted_movement"]
    label: str
    description: str
    target: str


class MonthlyEquipmentEntries(BaseModel):
    month_label: str
    count: int


class DashboardSummary(BaseModel):
    schema_version: Literal["2"] = "2"
    alerts: list[Alert]
    purchase_events: list[PurchaseEvent]
    quick_actions: list[QuickAction]
    monthly_equipment_entries: MonthlyEquipmentEntries
