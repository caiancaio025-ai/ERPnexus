from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.customers.models import CustomerDocument, CustomerNote
from app.laboratory.models import (
    LaboratoryCustomer,
    LaboratoryEquipment,
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


@dataclass(slots=True)
class CustomerRelationPageResult:
    items: list
    page: int
    page_size: int
    total: int
    pages: int


def _page_window(*, total: int, page: int, page_size: int) -> tuple[int, int, int]:
    pages = max(1, ceil(total / page_size))
    effective_page = min(page, pages)
    offset = (effective_page - 1) * page_size
    return effective_page, pages, offset


async def list_customer_equipment_page(
    db: AsyncSession, *, customer_id: int, page: int, page_size: int
) -> CustomerRelationPageResult:
    filters = (
        LaboratoryEquipment.customer_id == customer_id,
        LaboratoryEquipment.is_active.is_(True),
    )
    total = int(
        await db.scalar(select(func.count(LaboratoryEquipment.id)).where(*filters)) or 0
    )
    effective_page, pages, offset = _page_window(
        total=total, page=page, page_size=page_size
    )
    query = (
        select(
            LaboratoryEquipment.id,
            LaboratoryEquipment.serial_number,
            LaboratoryEquipment.manufacturer,
            LaboratoryEquipment.model,
            LaboratoryEquipment.equipment_type,
            LaboratoryEquipment.power,
            LaboratoryEquipment.voltage,
        )
        .where(*filters)
        .order_by(LaboratoryEquipment.updated_at.desc(), LaboratoryEquipment.id.desc())
        .limit(page_size)
        .offset(offset)
    )
    rows = (await db.execute(query)).mappings().all()
    return CustomerRelationPageResult(
        items=[dict(row) for row in rows],
        page=effective_page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


async def list_customer_work_orders_page(
    db: AsyncSession, *, customer_id: int, page: int, page_size: int
) -> CustomerRelationPageResult:
    total = int(
        await db.scalar(
            select(func.count(LaboratoryWorkOrder.id)).where(
                LaboratoryWorkOrder.customer_id == customer_id
            )
        )
        or 0
    )
    effective_page, pages, offset = _page_window(
        total=total, page=page, page_size=page_size
    )
    query = (
        select(
            LaboratoryWorkOrder.id,
            LaboratoryWorkOrder.number,
            LaboratoryWorkOrder.equipment_id,
            LaboratoryWorkOrder.equipment_serial,
            LaboratoryWorkOrder.status,
            LaboratoryWorkOrder.priority,
            LaboratoryWorkOrder.opened_at,
            LaboratoryWorkOrder.quoted_value,
            LaboratoryWorkOrder.approved_value,
        )
        .where(LaboratoryWorkOrder.customer_id == customer_id)
        .order_by(LaboratoryWorkOrder.opened_at.desc(), LaboratoryWorkOrder.id.desc())
        .limit(page_size)
        .offset(offset)
    )
    rows = (await db.execute(query)).mappings().all()
    return CustomerRelationPageResult(
        items=[dict(row) for row in rows],
        page=effective_page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


async def list_customer_quotes_page(
    db: AsyncSession, *, customer_id: int, page: int, page_size: int
) -> CustomerRelationPageResult:
    customer_filter = LaboratoryWorkOrder.customer_id == customer_id
    total = int(
        await db.scalar(
            select(func.count(LaboratoryQuote.id))
            .join(
                LaboratoryWorkOrder,
                LaboratoryQuote.work_order_id == LaboratoryWorkOrder.id,
            )
            .where(customer_filter)
        )
        or 0
    )
    effective_page, pages, offset = _page_window(
        total=total, page=page, page_size=page_size
    )
    query = (
        select(
            LaboratoryQuote.id,
            LaboratoryQuote.work_order_id,
            LaboratoryWorkOrder.number.label("work_order_number"),
            LaboratoryQuote.revision,
            LaboratoryQuote.status,
            LaboratoryQuote.total,
            LaboratoryQuote.emitted_at,
            LaboratoryQuote.created_at,
        )
        .join(
            LaboratoryWorkOrder,
            LaboratoryQuote.work_order_id == LaboratoryWorkOrder.id,
        )
        .where(customer_filter)
        .order_by(LaboratoryQuote.created_at.desc(), LaboratoryQuote.id.desc())
        .limit(page_size)
        .offset(offset)
    )
    rows = (await db.execute(query)).mappings().all()
    return CustomerRelationPageResult(
        items=[dict(row) for row in rows],
        page=effective_page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


async def list_customer_notes_page(
    db: AsyncSession, *, customer_id: int, page: int, page_size: int
) -> CustomerRelationPageResult:
    customer_filter = CustomerNote.customer_id == customer_id
    total = int(
        await db.scalar(select(func.count(CustomerNote.id)).where(customer_filter)) or 0
    )
    effective_page, pages, offset = _page_window(
        total=total, page=page, page_size=page_size
    )
    query = (
        select(CustomerNote)
        .where(customer_filter)
        .order_by(CustomerNote.created_at.desc(), CustomerNote.id.desc())
        .limit(page_size)
        .offset(offset)
    )
    items = list((await db.scalars(query)).all())
    return CustomerRelationPageResult(
        items=items, page=effective_page, page_size=page_size, total=total, pages=pages
    )


async def list_customer_documents_page(
    db: AsyncSession, *, customer_id: int, page: int, page_size: int
) -> CustomerRelationPageResult:
    customer_filter = CustomerDocument.customer_id == customer_id
    total = int(
        await db.scalar(select(func.count(CustomerDocument.id)).where(customer_filter)) or 0
    )
    effective_page, pages, offset = _page_window(
        total=total, page=page, page_size=page_size
    )
    query = (
        select(CustomerDocument)
        .where(customer_filter)
        .order_by(CustomerDocument.created_at.desc(), CustomerDocument.id.desc())
        .limit(page_size)
        .offset(offset)
    )
    items = list((await db.scalars(query)).all())
    return CustomerRelationPageResult(
        items=items, page=effective_page, page_size=page_size, total=total, pages=pages
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
