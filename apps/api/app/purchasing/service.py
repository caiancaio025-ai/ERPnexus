from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.purchasing.models import PurchaseOrder
from app.purchasing.numbering import next_purchasing_code
from app.purchasing.schemas import PurchaseSummary


async def next_purchase_code(db: AsyncSession) -> str:
    return await next_purchasing_code(db, PurchaseOrder.code, "PC")


async def build_purchase_summary(
    db: AsyncSession,
    company_code: str | None,
) -> PurchaseSummary:
    today = date.today()
    month_start = today.replace(day=1)
    base = [PurchaseOrder.is_deleted.is_(False)]
    if company_code:
        base.append(PurchaseOrder.company_code == company_code)

    open_status = PurchaseOrder.status.notin_(("delivered", "cancelled"))
    total_open = await db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(*base, open_status)
    )
    overdue = await db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            *base,
            open_status,
            PurchaseOrder.estimated_delivery_date < today,
        )
    )
    due_soon = await db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            *base,
            open_status,
            PurchaseOrder.estimated_delivery_date >= today,
            PurchaseOrder.estimated_delivery_date <= today + timedelta(days=7),
        )
    )
    delivered_month = await db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            *base,
            PurchaseOrder.status == "delivered",
            PurchaseOrder.delivered_at >= month_start,
        )
    )
    total_value = await db.scalar(
        select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).where(
            *base,
            open_status,
        )
    )
    return PurchaseSummary(
        total_open=int(total_open or 0),
        overdue=int(overdue or 0),
        due_soon=int(due_soon or 0),
        delivered_month=int(delivered_month or 0),
        total_value_open=Decimal(total_value or 0),
    )
