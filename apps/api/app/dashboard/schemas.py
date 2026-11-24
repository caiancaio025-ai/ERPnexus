from typing import Literal

from pydantic import BaseModel, Field


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


class WorkItem(BaseModel):
    id: int
    title: str
    description: str
    status: str
    target: str
    meta: str | None = None
    date_label: str | None = None


class WorkQueue(BaseModel):
    key: str
    section: Literal["laboratorio", "orcamentos", "compras", "financeiro", "estoque"]
    title: str
    description: str
    tone: Literal["info", "warning", "danger", "success"]
    total: int = Field(ge=0)
    target: str
    items: list[WorkItem] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    schema_version: Literal["3"] = "3"
    audience: Literal["gestao", "admin", "lab", "compras", "estoque", "outros"] = "outros"
    alerts: list[Alert]
    work_queues: list[WorkQueue] = Field(default_factory=list)
    purchase_events: list[PurchaseEvent]
    quick_actions: list[QuickAction]
    monthly_equipment_entries: MonthlyEquipmentEntries
    filtered_period: bool = False
