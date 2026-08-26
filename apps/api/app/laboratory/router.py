import secrets
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_create_quote
from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload, validate_upload
from app.finance.models import FinancialEntry
from app.laboratory.models import (
    LaboratoryCustomer,
    LaboratoryDocument,
    LaboratoryQuote,
    LaboratoryQuoteItem,
    LaboratoryStatusHistory,
    LaboratoryTechnician,
    LaboratoryWorkOrder,
)
from app.laboratory.quote_pdf import label_pdf, quote_pdf
from app.laboratory.schemas import (
    CompanyCode,
    CustomerInput,
    CustomerOutput,
    DocumentCategory,
    DocumentOutput,
    LaboratoryStatus,
    QuoteInput,
    QuoteOutput,
    StatusChangeInput,
    StatusHistoryOutput,
    TechnicianInput,
    TechnicianOutput,
    TechnicianUpdate,
    WorkOrderInput,
    WorkOrderOutput,
    WorkOrderPage,
    WorkOrderSummary,
    WorkOrderUpdate,
)
from app.notifications.service import notify_quote_users
from app.laboratory.service import (
    TERMINAL_STATUSES,
    apply_work_order_update,
    can_transition_status,
    find_or_create_equipment,
    list_work_orders_page,
    next_work_order_number,
    total_pages,
)

router = APIRouter(prefix="/laboratory", dependencies=[Depends(require_module("laboratorio"))])
UPLOAD_ROOT = Path(settings.storage_root) / "laboratory"
MAX_UPLOAD_SIZE = 15 * 1024 * 1024

CURRENT_USER_DEP = Depends(current_user)
DB_DEP = Depends(get_db)
QUERY_COMPANY_CODE = Query(default=None)
QUERY_INCLUDE_INACTIVE = Query(default=False)
QUERY_PAGE = Query(default=1, ge=1)
QUERY_PAGE_SIZE = Query(default=25, ge=1, le=100)
QUERY_STATUS = Query(default=None, alias="status")
QUERY_SEARCH = Query(default=None, max_length=120)
QUERY_MONTH = Query(default=None, ge=1, le=12)
QUERY_YEAR = Query(default=None, ge=2000, le=2100)
QUERY_PREVIEW = Query(default=True)
QUERY_DOCUMENT_CATEGORY = Query(default="general")
REQUIRED_FILE = File(...)


# ---------------------------------------------------------------- helpers --


async def _work_order_or_404(db: AsyncSession, work_order_id: int) -> LaboratoryWorkOrder:
    work_order = await db.get(LaboratoryWorkOrder, work_order_id)
    if not work_order:
        raise HTTPException(status_code=404, detail="OS não encontrada.")
    return work_order


def _to_work_order_output(work_order: LaboratoryWorkOrder) -> WorkOrderOutput:
    equipment = work_order.equipment
    return WorkOrderOutput(
        id=work_order.id,
        number=work_order.number,
        company_code=work_order.company_code,
        customer_id=work_order.customer_id,
        equipment_id=work_order.equipment_id,
        customer_name=work_order.customer_name,
        equipment_serial=work_order.equipment_serial,
        equipment_type=equipment.equipment_type if equipment else None,
        manufacturer=equipment.manufacturer if equipment else None,
        model=equipment.model if equipment else None,
        power=equipment.power if equipment else None,
        voltage=equipment.voltage if equipment else None,
        equipment_notes=equipment.notes if equipment else None,
        entry_invoice=work_order.entry_invoice,
        exit_invoice=work_order.exit_invoice,
        status=work_order.status,
        priority=work_order.priority,
        reported_defect=work_order.reported_defect,
        entry_condition=work_order.entry_condition,
        accessories_received=work_order.accessories_received,
        assigned_technician_id=work_order.assigned_technician_id,
        opened_at=work_order.opened_at,
        completed_at=work_order.completed_at,
        delivered_at=work_order.delivered_at,
        parts_cost=work_order.parts_cost,
        quoted_value=work_order.quoted_value,
        approved_value=work_order.approved_value,
        internal_notes=work_order.internal_notes,
        customer_notes=work_order.customer_notes,
        version=work_order.version,
        created_at=work_order.created_at,
        updated_at=work_order.updated_at,
    )


async def _issue_tracking_token(db: AsyncSession, work_order: LaboratoryWorkOrder) -> str:
    """Gera o token uma única vez e persiste. Reaproveitado nas próximas
    chamadas -- essencial para que um QR já impresso nunca pare de funcionar."""
    while True:
        candidate = secrets.token_hex(16)
        exists = await db.scalar(
            select(LaboratoryWorkOrder.id).where(LaboratoryWorkOrder.tracking_token == candidate)
        )
        if not exists:
            break
    work_order.tracking_token = candidate
    await db.commit()
    await db.refresh(work_order)
    return candidate


async def _sync_finance_on_status_change(
    db: AsyncSession,
    work_order: LaboratoryWorkOrder,
    previous_status: str,
    new_status: str,
    user_id: int,
) -> None:
    """Mantém somente sincronizações de lifecycle.

    Aprovação comercial NÃO cria receita. Receita/faturamento nasce no Financeiro,
    após o checklist de conformidade do cliente, e então sincroniza a OS como Faturado.
    """
    if new_status == "delivered":
        work_order.delivered_at = datetime.now(UTC)

    if new_status == "invoiced" and work_order.invoiced_at is None:
        work_order.invoiced_at = datetime.now(UTC)

    if new_status == "cancelled":
        entries = list((await db.scalars(
            select(FinancialEntry).where(
                FinancialEntry.work_order_id == work_order.id,
                FinancialEntry.is_deleted.is_(False),
                FinancialEntry.status == "pending",
            )
        )).all())
        for entry in entries:
            entry.status = "cancelled"


def _quote_totals(payload: QuoteInput) -> tuple:
    from decimal import Decimal

    subtotal = sum(
        (Decimal(item.quantity) * Decimal(item.unit_value) for item in payload.items),
        Decimal("0"),
    )
    if payload.discount_type == "percent":
        discount = subtotal * (Decimal(payload.discount_value) / 100)
    elif payload.discount_type == "amount":
        discount = Decimal(payload.discount_value)
    else:
        discount = Decimal("0")
    total = max(Decimal("0"), subtotal - discount)
    return subtotal, total


# --------------------------------------------------------------- summary ---


def _period_bounds(year: int | None, month: int | None) -> tuple[date | None, date | None]:
    """Retorna o intervalo de entrada do Laboratório.

    - ano + mês: filtra apenas o mês;
    - apenas ano: filtra todos os meses daquele ano;
    - nenhum dos dois: todo o histórico.
    """
    if year is None and month is None:
        return None, None
    if year is None:
        raise HTTPException(status_code=422, detail="Informe o ano para filtrar por mês.")
    if month is None:
        return date(year, 1, 1), date(year + 1, 1, 1)
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


@router.get("/periods")
async def laboratory_periods(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    filters = [LaboratoryWorkOrder.company_code == company_code] if company_code else []
    latest = await db.scalar(select(func.max(LaboratoryWorkOrder.opened_at)).where(*filters))
    earliest = await db.scalar(select(func.min(LaboratoryWorkOrder.opened_at)).where(*filters))
    reference = latest or date.today()
    first_year = earliest.year if earliest else reference.year
    years = list(range(reference.year, first_year - 1, -1))
    return {
        "latest_month": reference.month,
        "latest_year": reference.year,
        "years": years,
    }


@router.get("/summary", response_model=WorkOrderSummary)
async def summary(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    month: int | None = QUERY_MONTH,
    year: int | None = QUERY_YEAR,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    today = date.today()
    month_start = today.replace(day=1)
    base = [LaboratoryWorkOrder.company_code == company_code] if company_code else []
    period_start, period_end = _period_bounds(year, month)
    if period_start is not None and period_end is not None:
        base.extend((
            LaboratoryWorkOrder.opened_at >= period_start,
            LaboratoryWorkOrder.opened_at < period_end,
        ))

    async def count_for(*extra) -> int:
        count = await db.scalar(
            select(func.count(LaboratoryWorkOrder.id)).where(*base, *extra)
        )
        return int(count or 0)

    return WorkOrderSummary(
        total_open=await count_for(LaboratoryWorkOrder.status.notin_(TERMINAL_STATUSES)),
        analyzed=await count_for(LaboratoryWorkOrder.status == "in_analysis"),
        awaiting_approval=await count_for(LaboratoryWorkOrder.status == "awaiting_approval"),
        approved=await count_for(LaboratoryWorkOrder.status == "approved"),
        awaiting_analysis=await count_for(
            LaboratoryWorkOrder.status.in_(("received", "awaiting_analysis"))
        ),
        in_repair=await count_for(LaboratoryWorkOrder.status == "in_repair"),
        in_testing=await count_for(LaboratoryWorkOrder.status == "in_testing"),
        high_priority=await count_for(
            LaboratoryWorkOrder.priority.in_(("high", "urgent")),
            LaboratoryWorkOrder.status.notin_(TERMINAL_STATUSES),
        ),
        completed_month=await count_for(
            LaboratoryWorkOrder.status.in_(("completed", "delivered")),
            LaboratoryWorkOrder.completed_at >= month_start,
        ),
    )


# -------------------------------------------------------------- customers --


@router.get("/customers", response_model=list[CustomerOutput])
async def list_customers(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    include_inactive: bool = QUERY_INCLUDE_INACTIVE,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    query = select(LaboratoryCustomer)
    if company_code:
        query = query.where(LaboratoryCustomer.company_code == company_code)
    if not include_inactive:
        query = query.where(LaboratoryCustomer.is_active.is_(True))
    return list((await db.scalars(query.order_by(LaboratoryCustomer.legal_name))).all())


@router.post("/customers", response_model=CustomerOutput, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    customer = LaboratoryCustomer(**payload.model_dump(), created_by=user.id)
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_customer(
    customer_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    customer = await db.get(LaboratoryCustomer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    customer.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------ technicians --


@router.get("/technicians", response_model=list[TechnicianOutput])
async def list_technicians(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    include_inactive: bool = QUERY_INCLUDE_INACTIVE,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    query = select(LaboratoryTechnician)
    if company_code:
        query = query.where(LaboratoryTechnician.company_code == company_code)
    if not include_inactive:
        query = query.where(LaboratoryTechnician.is_active.is_(True))
    return list((await db.scalars(query.order_by(LaboratoryTechnician.name))).all())


@router.post("/technicians", response_model=TechnicianOutput, status_code=status.HTTP_201_CREATED)
async def create_technician(
    payload: TechnicianInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    technician = LaboratoryTechnician(**payload.model_dump(), created_by=user.id)
    db.add(technician)
    await db.commit()
    await db.refresh(technician)
    return technician


@router.put("/technicians/{technician_id}", response_model=TechnicianOutput)
async def update_technician(
    technician_id: int,
    payload: TechnicianUpdate,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    technician = await db.get(LaboratoryTechnician, technician_id)
    if not technician:
        raise HTTPException(status_code=404, detail="Técnico não encontrado.")
    for field, value in payload.model_dump().items():
        setattr(technician, field, value)
    await db.commit()
    await db.refresh(technician)
    return technician


@router.delete("/technicians/{technician_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_technician(
    technician_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    technician = await db.get(LaboratoryTechnician, technician_id)
    if not technician:
        raise HTTPException(status_code=404, detail="Técnico não encontrado.")
    technician.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------ work orders --


@router.get("/work-orders", response_model=WorkOrderPage)
async def list_work_orders(
    page: int = QUERY_PAGE,
    page_size: int = QUERY_PAGE_SIZE,
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    work_order_status: LaboratoryStatus | None = QUERY_STATUS,
    search: str | None = QUERY_SEARCH,
    month: int | None = QUERY_MONTH,
    year: int | None = QUERY_YEAR,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    period_start, period_end = _period_bounds(year, month)
    work_orders, total = await list_work_orders_page(
        db,
        page=page,
        page_size=page_size,
        company_code=company_code,
        status=work_order_status,
        search=search,
        opened_from=period_start,
        opened_before=period_end,
    )
    return WorkOrderPage(
        items=[_to_work_order_output(wo) for wo in work_orders],
        page=page,
        page_size=page_size,
        total=total,
        pages=total_pages(total, page_size),
    )


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderOutput)
async def get_work_order(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    return _to_work_order_output(await _work_order_or_404(db, work_order_id))


@router.post("/work-orders", response_model=WorkOrderOutput, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    payload: WorkOrderInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    equipment = await find_or_create_equipment(
        db,
        company_code=payload.company_code,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name.strip(),
        serial_number=payload.serial_number,
        manufacturer=payload.manufacturer,
        model=payload.model,
        equipment_type=payload.equipment_type,
        power=payload.power,
        voltage=payload.voltage,
        user_id=user.id,
    )
    work_order = LaboratoryWorkOrder(
        number=await next_work_order_number(db),
        company_code=payload.company_code,
        equipment_id=equipment.id,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name.strip(),
        equipment_serial=payload.serial_number,
        status="received",
        priority=payload.priority,
        reported_defect=payload.reported_defect,
        entry_condition=payload.entry_condition,
        accessories_received=payload.accessories_received,
        assigned_technician_id=payload.assigned_technician_id,
        opened_at=date.today(),
        entry_invoice=payload.entry_invoice,
        exit_invoice=payload.exit_invoice,
        parts_cost=payload.parts_cost or None,
        quoted_value=payload.quoted_value or None,
        approved_value=payload.approved_value or None,
        internal_notes=payload.internal_notes,
        customer_notes=payload.customer_notes,
        created_by=user.id,
    )
    db.add(work_order)
    await db.flush()
    db.add(
        LaboratoryStatusHistory(
            work_order_id=work_order.id,
            previous_status=None,
            new_status="received",
            note="OS criada.",
            user_id=user.id,
        )
    )
    await db.commit()
    await db.refresh(work_order)
    return _to_work_order_output(await _work_order_or_404(db, work_order.id))


@router.patch("/work-orders/{work_order_id}", response_model=WorkOrderOutput)
async def update_work_order(
    work_order_id: int,
    payload: WorkOrderUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    if work_order.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail="Esta OS foi alterada por outra pessoa. Recarregue antes de salvar.",
        )

    equipment = await find_or_create_equipment(
        db,
        company_code=payload.company_code,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name.strip(),
        serial_number=payload.serial_number,
        manufacturer=payload.manufacturer,
        model=payload.model,
        equipment_type=payload.equipment_type,
        power=payload.power,
        voltage=payload.voltage,
        user_id=user.id,
    )

    apply_work_order_update(work_order, payload, equipment_id=equipment.id)
    work_order.version += 1

    await db.commit()
    return _to_work_order_output(await _work_order_or_404(db, work_order.id))


@router.post("/work-orders/{work_order_id}/status", response_model=WorkOrderOutput)
async def change_status(
    work_order_id: int,
    payload: StatusChangeInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    if work_order.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail="Esta OS foi alterada por outra pessoa. Recarregue antes de aplicar o status.",
        )
    if not can_transition_status(work_order.status, payload.status):
        raise HTTPException(
            status_code=409,
            detail=f"Transição de {work_order.status} para {payload.status} não permitida.",
        )

    previous = work_order.status
    if previous != payload.status:
        work_order.status = payload.status
        work_order.version += 1
        if payload.status in ("completed",):
            work_order.completed_at = datetime.now(UTC)
        if payload.status == "cancelled":
            work_order.is_cancelled = True
        db.add(
            LaboratoryStatusHistory(
                work_order_id=work_order.id,
                previous_status=previous,
                new_status=payload.status,
                note=payload.note,
                user_id=user.id,
            )
        )
        await _sync_finance_on_status_change(db, work_order, previous, payload.status, user.id)
        if payload.status == "in_analysis" and previous != "in_analysis":
            await notify_quote_users(
                db,
                category="quote",
                severity="warning",
                title=f"OS {work_order.number} analisada · orçamento pendente",
                message=f"{work_order.customer_name} · {work_order.equipment_name}. O diagnóstico foi concluído e a OS aguarda orçamento.",
                target=f"/laboratorio?os={work_order.id}&aba=quote",
                entity_type="laboratory_work_order",
                entity_id=work_order.id,
                work_order_id=work_order.id,
                exclude_user_id=user.id,
            )
        await db.commit()
    return _to_work_order_output(await _work_order_or_404(db, work_order.id))


@router.get("/work-orders/{work_order_id}/history", response_model=list[StatusHistoryOutput])
async def list_history(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    query = (
        select(LaboratoryStatusHistory, User.name)
        .join(User, User.id == LaboratoryStatusHistory.user_id)
        .where(LaboratoryStatusHistory.work_order_id == work_order_id)
        .order_by(LaboratoryStatusHistory.created_at, LaboratoryStatusHistory.id)
    )
    rows = (await db.execute(query)).all()
    return [
        StatusHistoryOutput(
            id=row.LaboratoryStatusHistory.id,
            previous_status=row.LaboratoryStatusHistory.previous_status,
            new_status=row.LaboratoryStatusHistory.new_status,
            note=row.LaboratoryStatusHistory.note,
            user_id=row.LaboratoryStatusHistory.user_id,
            user_name=row.name,
            created_at=row.LaboratoryStatusHistory.created_at,
        )
        for row in rows
    ]


# ------------------------------------------------------------------ label --


@router.get("/work-orders/{work_order_id}/label.pdf")
async def work_order_label_pdf(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    tracking_token = work_order.tracking_token or await _issue_tracking_token(db, work_order)
    pdf_bytes = label_pdf(work_order, work_order.equipment, tracking_token)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="etiqueta-{work_order.number}.pdf"'},
    )



def _require_quote_permission(user: User) -> None:
    if not user_can_create_quote(user.role, user.modules):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu perfil não possui permissão para criar, alterar ou emitir orçamentos.",
        )

# ---------------------------------------------------------------- quotes ---


@router.get("/work-orders/{work_order_id}/quotes", response_model=list[QuoteOutput])
async def list_quotes(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    query = (
        select(LaboratoryQuote)
        .where(LaboratoryQuote.work_order_id == work_order_id)
        .order_by(LaboratoryQuote.revision.desc())
    )
    return list((await db.scalars(query)).all())


@router.post(
    "/work-orders/{work_order_id}/quotes",
    response_model=QuoteOutput,
    status_code=status.HTTP_201_CREATED,
)
async def create_quote(
    work_order_id: int,
    payload: QuoteInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_quote_permission(user)
    await _work_order_or_404(db, work_order_id)
    last_revision = await db.scalar(
        select(func.max(LaboratoryQuote.revision)).where(
            LaboratoryQuote.work_order_id == work_order_id
        )
    )
    subtotal, total = _quote_totals(payload)
    quote = LaboratoryQuote(
        work_order_id=work_order_id,
        revision=(last_revision or 0) + 1,
        service_code=payload.service_code,
        technical_report=payload.technical_report,
        services_description=payload.services_description,
        delivery_days=payload.delivery_days,
        billing_days=payload.billing_days,
        warranty_months=payload.warranty_months,
        payment_terms=payload.payment_terms,
        validity_days=payload.validity_days,
        return_condition=payload.return_condition,
        consumer_clause=payload.consumer_clause,
        supply_clause=payload.supply_clause,
        estimate_clause=payload.estimate_clause,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        subtotal=subtotal,
        total=total,
        created_by=user.id,
    )
    quote.items = [
        LaboratoryQuoteItem(position=index + 1, **item.model_dump())
        for index, item in enumerate(payload.items)
    ]
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return quote


@router.put("/quotes/{quote_id}", response_model=QuoteOutput)
async def update_quote(
    quote_id: int,
    payload: QuoteInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_quote_permission(user)
    quote = await db.get(LaboratoryQuote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    if quote.status == "emitted" or quote.emitted_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Orçamento emitido não pode ser alterado. Crie uma nova revisão.",
        )
    subtotal, total = _quote_totals(payload)
    for field in (
        "service_code", "technical_report", "services_description", "delivery_days", "billing_days",
        "warranty_months", "payment_terms", "validity_days", "return_condition", "consumer_clause",
        "supply_clause", "estimate_clause", "discount_type", "discount_value",
    ):
        setattr(quote, field, getattr(payload, field))
    quote.subtotal = subtotal
    quote.total = total
    quote.items = [
        LaboratoryQuoteItem(position=index + 1, **item.model_dump())
        for index, item in enumerate(payload.items)
    ]
    await db.commit()
    await db.refresh(quote)
    return quote


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quote(
    quote_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_quote_permission(user)
    quote = await db.get(LaboratoryQuote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    if quote.status == "emitted" or quote.emitted_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Orçamento emitido não pode ser excluído. O histórico de revisões deve ser preservado.",
        )
    await db.delete(quote)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/quotes/{quote_id}/pdf")
async def quote_pdf_endpoint(
    quote_id: int,
    preview: bool = QUERY_PREVIEW,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    quote = await db.get(LaboratoryQuote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    work_order = await _work_order_or_404(db, quote.work_order_id)

    if not preview:
        _require_quote_permission(user)

    if not preview and quote.emitted_at is None:
        quote.emitted_at = datetime.now(UTC)
        quote.status = "emitted"
        await db.commit()
        await db.refresh(quote)

    customer = await db.get(LaboratoryCustomer, work_order.customer_id) if work_order.customer_id else None
    pdf_bytes = quote_pdf(work_order, work_order.equipment, quote, customer)
    disposition = "inline" if preview else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="orcamento-{work_order.number}-'
                f'r{quote.revision:02d}.pdf"'
            )
        },
    )


# -------------------------------------------------------------- documents --


@router.post(
    "/work-orders/{work_order_id}/documents",
    response_model=DocumentOutput,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    work_order_id: int,
    file: UploadFile = REQUIRED_FILE,
    category: DocumentCategory = QUERY_DOCUMENT_CATEGORY,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="O arquivo excede 15 MB.")
    try:
        detected = validate_upload(content, file.filename, file.content_type)
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    suffix = detected.extension
    directory = UPLOAD_ROOT / work_order.company_code / work_order.number
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid4().hex}{suffix}"
    target.write_bytes(content)

    document = LaboratoryDocument(
        work_order_id=work_order.id,
        category=category,
        original_name=file.filename or target.name,
        storage_path=str(target),
        mime_type=detected.mime_type,
        size_bytes=len(content),
        checksum_sha256=sha256(content).hexdigest(),
        uploaded_by=user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


@router.get("/documents/{document_id}/preview")
async def preview_document(
    document_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    document = await db.get(LaboratoryDocument, document_id)
    if not document or not Path(document.storage_path).is_file():
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    safe_name = quote(document.original_name)
    return FileResponse(
        document.storage_path,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{safe_name}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    document = await db.get(LaboratoryDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    path = Path(document.storage_path)
    await db.delete(document)
    await db.commit()
    if path.is_file():
        path.unlink()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ------------------------------------------------------- material requests ---

from app.purchasing.material_models import MaterialRequest, MaterialRequestEvent
from app.purchasing.material_schemas import MaterialRequestCreate, MaterialRequestOutput
from app.purchasing.material_service import event as material_event, next_material_request_code, output_rows


@router.get("/work-orders/{work_order_id}/materials", response_model=list[MaterialRequestOutput])
async def list_material_requests_for_work_order(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    rows = list((await db.scalars(
        select(MaterialRequest)
        .where(MaterialRequest.work_order_id == work_order_id)
        .order_by(MaterialRequest.created_at.desc())
    )).all())
    return await output_rows(db, rows)


@router.post(
    "/work-orders/{work_order_id}/materials",
    response_model=MaterialRequestOutput,
    status_code=status.HTTP_201_CREATED,
)
async def create_material_request_for_work_order(
    work_order_id: int,
    payload: MaterialRequestCreate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    request = MaterialRequest(
        code=await next_material_request_code(db),
        company_code=work_order.company_code,
        work_order_id=work_order.id,
        equipment_id=work_order.equipment_id,
        requester_user_id=user.id,
        source_type="work_order",
        item_name=payload.item_name.strip(),
        quantity=payload.quantity,
        priority=payload.priority,
        technical_note=payload.technical_note,
        suggested_link=payload.suggested_link,
        status="awaiting_approval",
        updated_by=user.id,
    )
    db.add(request)
    await db.flush()
    db.add(material_event(
        request,
        user_id=user.id,
        event_type="created",
        previous=None,
        target="awaiting_approval",
        note="Solicitação criada pelo laboratório.",
    ))
    await db.commit()
    await db.refresh(request)
    return (await output_rows(db, [request]))[0]
