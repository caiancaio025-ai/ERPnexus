from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.purchasing.models import PurchaseOrder
from app.purchasing.schemas import PurchaseSummary


async def next_purchase_code(db: AsyncSession) -> str:
    current_year = date.today().year
    prefix = f"PC-{current_year}-"
    latest = await db.scalar(
        select(PurchaseOrder.code)
        .where(PurchaseOrder.code.like(f"{prefix}%"))
        .order_by(PurchaseOrder.id.desc())
        .limit(1)
    )
    sequence = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{sequence:04d}"


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
