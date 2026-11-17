from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class NotificationOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    severity: Literal["info", "success", "warning", "danger"] | str
    title: str
    message: str
    target: str | None
    entity_type: str | None
    entity_id: int | None
    work_order_id: int | None
    amount: Decimal | None
    activity_module: str | None = None
    action: str | None = None
    actor_user_id: int | None = None
    actor_name: str | None = None
    work_order_number: str | None = None
    equipment_name: str | None = None
    details: str | None = None
    is_read: bool
    created_at: datetime


class NotificationSummary(BaseModel):
    unread_count: int
    items: list[NotificationOutput]


class NotificationHistory(BaseModel):
    items: list[NotificationOutput]
    unread_count: int
    total: int
    page: int
    page_size: int
