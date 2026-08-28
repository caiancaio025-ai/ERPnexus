from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.laboratory.models import (
    LaboratoryCustomer,
    LaboratoryQuote,
    LaboratoryWorkOrder,
)


@dataclass(slots=True)
class CustomerPageResult:
    items: list[LaboratoryCustomer]
    page: int
    page_size: int
    total: int
    pages: int


def customer_filters(*, company_code: str | None, search: str | None):
    filters = [LaboratoryCustomer.is_active.is_(True)]
    if company_code:
        filters.append(LaboratoryCustomer.company_code == company_code)
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                LaboratoryCustomer.legal_name.ilike(term),
                LaboratoryCustomer.trade_name.ilike(term),
                LaboratoryCustomer.document.ilike(term),
                LaboratoryCustomer.email.ilike(term),
            )
        )
    return filters


async def customer_activity_counts(
    db: AsyncSession,
    *,
    customer_id: int,
) -> tuple[int, int]:
    work_orders_count = (
        select(func.count(LaboratoryWorkOrder.id))
        .where(LaboratoryWorkOrder.customer_id == customer_id)
        .scalar_subquery()
    )

    quotes_count = (
        select(func.count(LaboratoryQuote.id))
        .join(
            LaboratoryWorkOrder,
            LaboratoryQuote.work_order_id == LaboratoryWorkOrder.id,
        )
        .where(LaboratoryWorkOrder.customer_id == customer_id)
        .scalar_subquery()
    )

    row = (
        await db.execute(
            select(
                work_orders_count.label("work_orders_count"),
                quotes_count.label("quotes_count"),
            )
        )
    ).one()

    return (
        int(row.work_orders_count or 0),
        int(row.quotes_count or 0),
    )


async def list_customers_page(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    company_code: str | None = None,
    search: str | None = None,
) -> CustomerPageResult:
    filters = customer_filters(company_code=company_code, search=search)
    total = int(await db.scalar(select(func.count(LaboratoryCustomer.id)).where(*filters)) or 0)
    pages = max(1, ceil(total / page_size))
    effective_page = min(page, pages)
    query = (
        select(LaboratoryCustomer)
        .where(*filters)
        .order_by(LaboratoryCustomer.legal_name, LaboratoryCustomer.id)
        .limit(page_size)
        .offset((effective_page - 1) * page_size)
    )
    items = list((await db.scalars(query)).all())
    return CustomerPageResult(items=items, page=effective_page, page_size=page_size, total=total, pages=pages)
