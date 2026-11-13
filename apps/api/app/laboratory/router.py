import asyncio
import json
import secrets
import re
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_create_quote, user_can_view_sensitive_values
from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload
from app.core.upload_stream import UploadTooLarge, persist_streamed_upload
from app.commercial.models import CommercialCompanyProfile
from app.finance.models import FinancialEntry
from app.laboratory.models import (
    LaboratoryArea,
    LaboratoryAuditEvent,
    LaboratoryCustomer,
    LaboratoryDocument,
    LaboratoryLocation,
    LaboratoryLocationHistory,
    LaboratoryMechanicalPaintingDispatch,
    LaboratoryMechanicalPaintingItem,
    LaboratoryMechanicalPaintingPhoto,
    LaboratoryRack,
    LaboratoryQuote,
    LaboratoryQuoteItem,
    LaboratoryQuotePhoto,
    LaboratoryReleaseEvent,
    LaboratoryStatusHistory,
    LaboratoryTechnician,
    LaboratoryWorkflowOption,
    LaboratoryWorkOrder,
    LaboratoryWorkOrderSubstatus,
)
from app.laboratory.quote_pdf import label_pdf, quote_pdf
from app.laboratory.storage import (
    commit_laboratory_document,
    delete_laboratory_document as delete_laboratory_document_storage,
    resolve_laboratory_storage_path,
)
from app.laboratory.schemas import (
    CompanyCode,
    CompanyMasterInput,
    CompanyMasterOutput,
    CompanyMasterUpdate,
    CustomerInput,
    CustomerOutput,
    DocumentCategory,
    DocumentOutput,
    LaboratoryStatus,
    QuoteInput,
    QuoteOutput,
    QuotePhotoOutput,
    StatusChangeInput,
    StatusHistoryOutput,
    SubstatusToggleInput,
    TechnicianInput,
    TechnicianOutput,
    TechnicianUpdate,
    WorkflowOptionCreate,
    WorkflowOptionOutput,
    WorkflowOptionUpdate,
    WorkOrderInput,
    WorkOrderOutput,
    WorkOrderPage,
    LaboratoryLocationMapOutput,
    LaboratoryAreaInput,
    LaboratoryAreaOutput,
    LaboratoryAreaUpdate,
    LaboratoryLocationConfig,
    LaboratoryLocationConfigOutput,
    LaboratoryRackInput,
    LaboratoryRackOutput,
    LaboratoryRackUpdate,
    LaboratoryLocationOccupantOutput,
    LaboratoryLocationSlotOutput,
    LocationHistoryOutput,
    PaintingDispatchCreate,
    PaintingDispatchOutput,
    PaintingItemOutput,
    PaintingItemUpdate,
    PaintingPhotoOutput,
    WorkOrderSummary,
    WorkOrderUpdate,
    TechnicianProductionReport,
    InactivateWorkOrderInput,
)
from app.notifications.service import notify_quote_users, notify_roles
from app.laboratory.service import (
    TERMINAL_STATUSES,
    apply_work_order_update,
    find_or_create_equipment,
    list_work_orders_page,
    next_work_order_number,
    next_free_storage_location,
    ensure_storage_location_available,
    set_storage_location,
    group_work_orders_by_location,
    total_pages,
    work_order_period_range,
    work_order_summary_counts,
)
from app.laboratory.production_report import build_technician_production_report
from app.laboratory.location_dwell import location_dwell_level, location_dwell_seconds
from app.laboratory.status_flow import (
    BUSINESS_STATUS_TARGETS,
    LEGACY_SUBSTATUS_TARGETS,
    WORK_ORDER_STATUSES,
    can_transition,
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
QUERY_PAINT_PHASE = Query(default="outbound", pattern=r"^(outbound|return)$")
REQUIRED_FILE = File(...)


# ---------------------------------------------------------------- helpers --


def _can_override_work_order_status(user: User) -> bool:
    return user.role.strip().lower() in {"super_admin", "admin", "gestao"}


def _require_workflow_management(user: User) -> None:
    if not _can_override_work_order_status(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A configuração de status do Laboratório é restrita à ADM/Gestão.",
        )



def _require_master_management(user: User) -> None:
    if user.role.strip().lower() not in {"super_admin", "admin", "gestao"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente ADM ou Gestão pode alterar empresas e estrutura física.",
        )


async def _active_company_or_422(db: AsyncSession, company_code: str) -> CommercialCompanyProfile:
    company = await db.scalar(
        select(CommercialCompanyProfile).where(
            CommercialCompanyProfile.company_code == company_code,
            CommercialCompanyProfile.is_active.is_(True),
        )
    )
    if company is None:
        raise HTTPException(status_code=422, detail="Empresa emissora inexistente ou inativa.")
    return company


async def _validate_customer_company(
    db: AsyncSession,
    customer_id: int | None,
    company_code: str,
) -> None:
    if customer_id is None:
        return
    customer = await db.get(LaboratoryCustomer, customer_id)
    if customer is None or not customer.is_active:
        raise HTTPException(status_code=422, detail="Cliente inexistente ou inativo.")
    if customer.company_code != company_code:
        raise HTTPException(
            status_code=422,
            detail="O cliente selecionado pertence a outra empresa emissora.",
        )


def _company_snapshot_payload(company: CommercialCompanyProfile) -> dict[str, str | None]:
    return {
        "company_code": company.company_code,
        "legal_name": company.legal_name,
        "trade_name": company.trade_name,
        "document": company.document,
        "state_registration": company.state_registration,
        "email": company.email,
        "phone": company.phone,
        "address": company.address,
        "city": company.city,
        "state": company.state,
    }


async def _ensure_rack_layout_available(
    db: AsyncSession,
    *,
    area_id: int,
    layout_row: int,
    layout_column: int,
    layout_span: int,
    exclude_rack_id: int | None = None,
) -> None:
    query = select(LaboratoryRack).where(
        LaboratoryRack.area_id == area_id,
        LaboratoryRack.is_active.is_(True),
        LaboratoryRack.layout_row == layout_row,
    )
    if exclude_rack_id is not None:
        query = query.where(LaboratoryRack.id != exclude_rack_id)
    rows = list((await db.scalars(query)).all())
    start = layout_column
    end = layout_column + layout_span - 1
    for row in rows:
        other_start = row.layout_column
        other_end = row.layout_column + row.layout_span - 1
        if start <= other_end and other_start <= end:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A posição visual escolhida conflita com a estante {row.code}. "
                    "Escolha outra linha/coluna ou ajuste a largura."
                ),
            )


async def _location_config_output(db: AsyncSession) -> LaboratoryLocationConfig:
    areas = list((await db.scalars(
        select(LaboratoryArea).order_by(LaboratoryArea.sort_order, LaboratoryArea.id)
    )).all())
    racks = list((await db.scalars(
        select(LaboratoryRack).order_by(LaboratoryRack.sort_order, LaboratoryRack.id)
    )).all())
    locations = list((await db.scalars(
        select(LaboratoryLocation).order_by(LaboratoryLocation.sort_order, LaboratoryLocation.id)
    )).all())
    area_map = {row.id: row for row in areas}
    rack_map = {row.id: row for row in racks}
    direct_by_area = {
        row.area_id: row.code
        for row in locations
        if row.rack_id is None and row.is_active
    }
    return LaboratoryLocationConfig(
        areas=[
            LaboratoryAreaOutput(
                id=row.id, code=row.code, name=row.name, sort_order=row.sort_order,
                is_active=row.is_active, direct_location_code=direct_by_area.get(row.id),
            )
            for row in areas
        ],
        racks=[
            LaboratoryRackOutput(
                id=row.id, area_id=row.area_id,
                area_code=area_map[row.area_id].code,
                area_name=area_map[row.area_id].name,
                code=row.code, name=row.name, position_prefix=row.position_prefix,
                rows=row.rows, columns=row.columns,
                layout_row=row.layout_row, layout_column=row.layout_column,
                layout_span=row.layout_span, sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in racks
        ],
        locations=[
            LaboratoryLocationConfigOutput(
                id=row.id, area_id=row.area_id,
                area_code=area_map[row.area_id].code,
                area_name=area_map[row.area_id].name,
                rack_id=row.rack_id,
                rack_code=rack_map[row.rack_id].code if row.rack_id else None,
                rack_name=rack_map[row.rack_id].name if row.rack_id else None,
                code=row.code, name=row.name, sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in locations
        ],
    )

def _workflow_code(kind: str, label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_") or "item"
    prefix = "custom" if kind == "status" else "flag"
    return f"{prefix}_{slug}"[:40].rstrip("_")


async def _workflow_option_by_code(
    db: AsyncSession,
    *,
    kind: str,
    code: str,
    active_only: bool = True,
) -> LaboratoryWorkflowOption | None:
    query = select(LaboratoryWorkflowOption).where(
        LaboratoryWorkflowOption.kind == kind,
        LaboratoryWorkflowOption.code == code,
    )
    if active_only:
        query = query.where(LaboratoryWorkflowOption.is_active.is_(True))
    return await db.scalar(query)


async def _set_work_order_substatus(
    db: AsyncSession,
    *,
    work_order: LaboratoryWorkOrder,
    code: str,
    active: bool,
    user_id: int | None,
) -> None:
    row = await db.scalar(
        select(LaboratoryWorkOrderSubstatus).where(
            LaboratoryWorkOrderSubstatus.work_order_id == work_order.id,
            LaboratoryWorkOrderSubstatus.code == code,
        )
    )
    if row is None:
        row = LaboratoryWorkOrderSubstatus(
            work_order_id=work_order.id,
            code=code,
            is_active=active,
            updated_by=user_id,
        )
        db.add(row)
    else:
        row.is_active = active
        row.updated_by = user_id


def _active_substatus_codes(work_order: LaboratoryWorkOrder) -> list[str]:
    return sorted(row.code for row in work_order.substatuses if row.is_active)


async def _work_order_or_404(db: AsyncSession, work_order_id: int) -> LaboratoryWorkOrder:
    work_order = await db.scalar(
        select(LaboratoryWorkOrder)
        .where(LaboratoryWorkOrder.id == work_order_id)
        .execution_options(populate_existing=True)
    )
    if not work_order:
        raise HTTPException(status_code=404, detail="OS não encontrada.")
    return work_order


def _to_work_order_output(
    work_order: LaboratoryWorkOrder,
    *,
    include_sensitive_values: bool,
) -> WorkOrderOutput:
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
        entry_invoice_2=work_order.entry_invoice_2,
        entry_invoice_3=work_order.entry_invoice_3,
        entry_invoice_access_key=work_order.entry_invoice_access_key,
        exit_invoice=work_order.exit_invoice,
        exit_invoice_2=work_order.exit_invoice_2,
        exit_invoice_3=work_order.exit_invoice_3,
        exit_invoice_access_key=work_order.exit_invoice_access_key,
        warranty_invoice=work_order.warranty_invoice,
        warranty_invoice_2=work_order.warranty_invoice_2,
        warranty_invoice_3=work_order.warranty_invoice_3,
        warranty_entry_invoice_1=work_order.warranty_entry_invoice_1,
        warranty_entry_invoice_2=work_order.warranty_entry_invoice_2,
        warranty_entry_invoice_3=work_order.warranty_entry_invoice_3,
        warranty_exit_invoice_1=work_order.warranty_exit_invoice_1,
        warranty_exit_invoice_2=work_order.warranty_exit_invoice_2,
        warranty_exit_invoice_3=work_order.warranty_exit_invoice_3,
        is_inactive=work_order.is_inactive,
        inactivation_reason=work_order.inactivation_reason,
        inactivated_at=work_order.inactivated_at,
        storage_location=work_order.storage_location,
        status=work_order.status,
        priority=work_order.priority,
        reported_defect=work_order.reported_defect,
        entry_condition=work_order.entry_condition,
        accessories_received=work_order.accessories_received,
        assigned_technician_id=work_order.assigned_technician_id,
        opened_at=work_order.opened_at,
        completed_at=work_order.completed_at,
        delivered_at=work_order.delivered_at,
        parts_cost=work_order.parts_cost if include_sensitive_values else None,
        quoted_value=work_order.quoted_value if include_sensitive_values else None,
        approved_value=work_order.approved_value if include_sensitive_values else None,
        internal_notes=work_order.internal_notes,
        customer_notes=work_order.customer_notes,
        substatuses=_active_substatus_codes(work_order),
        version=work_order.version,
        created_at=work_order.created_at,
        updated_at=work_order.updated_at,
    )


def _to_quote_output(quote: LaboratoryQuote, *, include_sensitive_values: bool) -> QuoteOutput:
    return QuoteOutput(
        id=quote.id,
        work_order_id=quote.work_order_id,
        revision=quote.revision,
        status=quote.status,
        service_code=quote.service_code,
        technical_report=quote.technical_report,
        services_description=quote.services_description,
        delivery_days=quote.delivery_days,
        billing_days=quote.billing_days,
        billing_terms=quote.billing_terms,
        warranty_months=quote.warranty_months,
        warranty_terms=quote.warranty_terms,
        payment_terms=quote.payment_terms,
        validity_days=quote.validity_days,
        return_condition=quote.return_condition,
        consumer_clause=quote.consumer_clause,
        supply_clause=quote.supply_clause,
        estimate_clause=quote.estimate_clause,
        discount_type=quote.discount_type,
        discount_value=quote.discount_value if include_sensitive_values else None,
        subtotal=quote.subtotal if include_sensitive_values else None,
        total=quote.total if include_sensitive_values else None,
        emitted_at=quote.emitted_at,
        created_at=quote.created_at,
        updated_at=quote.updated_at,
        photos=[
            QuotePhotoOutput(
                id=photo.id,
                document_id=photo.document_id,
                position=photo.position,
                caption=photo.caption,
                original_name=photo.document.original_name,
                mime_type=photo.document.mime_type,
            )
            for photo in quote.photos
        ],
        items=[
            {
                "id": item.id,
                "position": item.position,
                "description": item.description,
                "quantity": item.quantity,
                "unit_value": item.unit_value if include_sensitive_values else None,
            }
            for item in quote.items
        ],
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
    if new_status == "delivered" and work_order.delivered_at is None:
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
    latest, earliest = await work_order_period_range(db, company_code=company_code)
    reference = latest or date.today()
    first_year = earliest.year if earliest else reference.year
    years = list(range(reference.year, first_year - 1, -1))
    return {
        "latest_month": reference.month,
        "latest_year": reference.year,
        "years": years,
    }


@router.get("/reports/technician-production", response_model=TechnicianProductionReport)
async def technician_production_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    technician_id: int | None = Query(default=None, ge=1),
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    customer_id: int | None = Query(default=None, ge=1),
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="Data final deve ser igual ou posterior à data inicial.",
        )
    return await build_technician_production_report(
        db,
        start_date=start_date,
        end_date=end_date,
        technician_id=technician_id,
        company_code=company_code,
        customer_id=customer_id,
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.get("/summary", response_model=WorkOrderSummary)
async def summary(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    month: int | None = QUERY_MONTH,
    year: int | None = QUERY_YEAR,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    today = date.today()
    current_month_start = today.replace(day=1)
    current_month_end = (
        date(today.year + 1, 1, 1)
        if today.month == 12
        else date(today.year, today.month + 1, 1)
    )
    period_start, period_end = _period_bounds(year, month)
    counts = await work_order_summary_counts(
        db,
        company_code=company_code,
        opened_from=period_start,
        opened_before=period_end,
        completed_from=period_start or current_month_start,
        completed_before=period_end or current_month_end,
    )

    if not user_can_view_sensitive_values(user.role):
        counts["approved_total"] = None
        counts["awaiting_approval_total"] = None

    return WorkOrderSummary(**counts)




async def _painting_dispatch_or_404(
    db: AsyncSession,
    dispatch_id: int,
) -> LaboratoryMechanicalPaintingDispatch:
    row = await db.get(LaboratoryMechanicalPaintingDispatch, dispatch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Controle de pintura não encontrado.")
    return row


async def _painting_dispatch_output(
    db: AsyncSession,
    dispatch: LaboratoryMechanicalPaintingDispatch,
) -> PaintingDispatchOutput:
    items = list((await db.scalars(
        select(LaboratoryMechanicalPaintingItem)
        .where(LaboratoryMechanicalPaintingItem.dispatch_id == dispatch.id)
        .order_by(LaboratoryMechanicalPaintingItem.position, LaboratoryMechanicalPaintingItem.id)
    )).all())

    photo_rows = (await db.execute(
        select(LaboratoryMechanicalPaintingPhoto, LaboratoryDocument)
        .join(LaboratoryDocument, LaboratoryDocument.id == LaboratoryMechanicalPaintingPhoto.document_id)
        .where(LaboratoryMechanicalPaintingPhoto.dispatch_id == dispatch.id)
        .order_by(
            LaboratoryMechanicalPaintingPhoto.phase,
            LaboratoryMechanicalPaintingPhoto.position,
            LaboratoryMechanicalPaintingPhoto.id,
        )
    )).all()

    user_ids = {
        value for value in (dispatch.created_by, dispatch.sent_by, dispatch.returned_by)
        if value is not None
    }
    user_names = {}
    if user_ids:
        users = list((await db.execute(
            select(User.id, User.name).where(User.id.in_(user_ids))
        )).all())
        user_names = {row.id: row.name for row in users}

    return PaintingDispatchOutput(
        id=dispatch.id,
        work_order_id=dispatch.work_order_id,
        status=dispatch.status,
        provider=dispatch.provider,
        notes=dispatch.notes,
        sent_at=dispatch.sent_at,
        returned_at=dispatch.returned_at,
        created_by=dispatch.created_by,
        created_by_name=user_names.get(dispatch.created_by, "Usuário"),
        sent_by=dispatch.sent_by,
        sent_by_name=user_names.get(dispatch.sent_by) if dispatch.sent_by else None,
        returned_by=dispatch.returned_by,
        returned_by_name=user_names.get(dispatch.returned_by) if dispatch.returned_by else None,
        created_at=dispatch.created_at,
        updated_at=dispatch.updated_at,
        items=[
            PaintingItemOutput(
                id=item.id,
                position=item.position,
                description=item.description,
                returned=item.returned,
                return_note=item.return_note,
                returned_at=item.returned_at,
            )
            for item in items
        ],
        photos=[
            PaintingPhotoOutput(
                id=photo.id,
                document_id=document.id,
                phase=photo.phase,
                position=photo.position,
                caption=photo.caption,
                original_name=document.original_name,
                mime_type=document.mime_type,
                created_at=photo.created_at,
            )
            for photo, document in photo_rows
        ],
    )


async def _list_painting_dispatches_output(
    db: AsyncSession,
    work_order_id: int,
) -> list[PaintingDispatchOutput]:
    rows = list((await db.scalars(
        select(LaboratoryMechanicalPaintingDispatch)
        .where(LaboratoryMechanicalPaintingDispatch.work_order_id == work_order_id)
        .order_by(
            LaboratoryMechanicalPaintingDispatch.created_at.desc(),
            LaboratoryMechanicalPaintingDispatch.id.desc(),
        )
    )).all())
    return [await _painting_dispatch_output(db, row) for row in rows]


# --------------------------------------------------------- config master --


@router.get("/settings/companies", response_model=list[CompanyMasterOutput])
async def list_master_companies(
    include_inactive: bool = QUERY_INCLUDE_INACTIVE,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    query = select(CommercialCompanyProfile)
    if not include_inactive:
        query = query.where(CommercialCompanyProfile.is_active.is_(True))
    return list((await db.scalars(
        query.order_by(CommercialCompanyProfile.legal_name, CommercialCompanyProfile.id)
    )).all())


@router.post("/settings/companies", response_model=CompanyMasterOutput, status_code=status.HTTP_201_CREATED)
async def create_master_company(
    payload: CompanyMasterInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_master_management(user)
    exists_row = await db.scalar(
        select(CommercialCompanyProfile).where(
            CommercialCompanyProfile.company_code == payload.company_code
        )
    )
    if exists_row is not None:
        raise HTTPException(status_code=409, detail="Já existe uma empresa com este código interno.")
    row = CommercialCompanyProfile(**payload.model_dump(), is_active=True, created_by=user.id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/settings/companies/{company_id}", response_model=CompanyMasterOutput)
async def update_master_company(
    company_id: int,
    payload: CompanyMasterUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_master_management(user)
    row = await db.get(CommercialCompanyProfile, company_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/settings/locations", response_model=LaboratoryLocationConfig)
async def get_location_config(
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    return await _location_config_output(db)


@router.post("/settings/areas", response_model=LaboratoryAreaOutput, status_code=status.HTTP_201_CREATED)
async def create_location_area(
    payload: LaboratoryAreaInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_master_management(user)
    code = payload.code.strip().upper()
    if await db.scalar(select(LaboratoryArea.id).where(LaboratoryArea.code == code)):
        raise HTTPException(status_code=409, detail="Já existe uma ala com este código.")
    if await db.scalar(select(LaboratoryLocation.id).where(LaboratoryLocation.code == code)):
        raise HTTPException(status_code=409, detail="O código já é usado por uma localização.")
    row = LaboratoryArea(
        code=code, name=payload.name.strip(), sort_order=payload.sort_order,
        is_active=True, created_by=user.id,
    )
    db.add(row)
    await db.flush()
    direct_code = None
    if payload.direct_assignment:
        direct_code = code
        db.add(LaboratoryLocation(
            area_id=row.id, rack_id=None, code=direct_code,
            name=f"{payload.name.strip()} - Área geral",
            sort_order=1, is_active=True, created_by=user.id,
        ))
    await db.commit()
    await db.refresh(row)
    return LaboratoryAreaOutput(
        id=row.id, code=row.code, name=row.name, sort_order=row.sort_order,
        is_active=row.is_active, direct_location_code=direct_code,
    )


@router.put("/settings/areas/{area_id}", response_model=LaboratoryAreaOutput)
async def update_location_area(
    area_id: int,
    payload: LaboratoryAreaUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_master_management(user)
    row = await db.get(LaboratoryArea, area_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ala não encontrada.")
    if row.is_active and not payload.is_active:
        location_codes = list((await db.scalars(
            select(LaboratoryLocation.code).where(LaboratoryLocation.area_id == row.id)
        )).all())
        occupied = await db.scalar(
            select(func.count()).select_from(LaboratoryWorkOrder).where(
                LaboratoryWorkOrder.storage_location.in_(location_codes)
            )
        ) if location_codes else 0
        if occupied:
            raise HTTPException(
                status_code=409,
                detail="Não é possível inativar uma ala que possui equipamentos localizados.",
            )
    row.name = payload.name.strip()
    row.sort_order = payload.sort_order
    row.is_active = payload.is_active
    await db.commit()
    direct = await db.scalar(
        select(LaboratoryLocation.code).where(
            LaboratoryLocation.area_id == row.id,
            LaboratoryLocation.rack_id.is_(None),
            LaboratoryLocation.is_active.is_(True),
        ).limit(1)
    )
    return LaboratoryAreaOutput(
        id=row.id, code=row.code, name=row.name, sort_order=row.sort_order,
        is_active=row.is_active, direct_location_code=direct,
    )


@router.post("/settings/racks", response_model=LaboratoryRackOutput, status_code=status.HTTP_201_CREATED)
async def create_location_rack(
    payload: LaboratoryRackInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_master_management(user)
    area = await db.get(LaboratoryArea, payload.area_id)
    if area is None or not area.is_active:
        raise HTTPException(status_code=422, detail="Ala inexistente ou inativa.")
    code = payload.code.strip().upper()
    prefix = payload.position_prefix.strip().upper()
    if await db.scalar(select(LaboratoryRack.id).where(LaboratoryRack.code == code)):
        raise HTTPException(status_code=409, detail="Já existe uma estante com este código.")
    await _ensure_rack_layout_available(
        db,
        area_id=area.id,
        layout_row=payload.layout_row,
        layout_column=payload.layout_column,
        layout_span=payload.layout_span,
    )
    count = payload.rows * payload.columns
    generated_codes = [f"{prefix}{index}" for index in range(1, count + 1)]
    if any(len(value) > 8 for value in generated_codes):
        raise HTTPException(status_code=422, detail="As posições geradas excedem 8 caracteres.")
    existing = set((await db.scalars(
        select(LaboratoryLocation.code).where(LaboratoryLocation.code.in_(generated_codes))
    )).all())
    if existing:
        raise HTTPException(status_code=409, detail=f"Posições já cadastradas: {', '.join(sorted(existing))}")
    rack = LaboratoryRack(
        area_id=area.id, code=code, name=payload.name.strip(),
        position_prefix=prefix, rows=payload.rows, columns=payload.columns,
        layout_row=payload.layout_row, layout_column=payload.layout_column,
        layout_span=payload.layout_span,
        sort_order=payload.sort_order, is_active=True, created_by=user.id,
    )
    db.add(rack)
    await db.flush()
    for index, location_code in enumerate(generated_codes, start=1):
        db.add(LaboratoryLocation(
            area_id=area.id, rack_id=rack.id, code=location_code,
            name=f"Posição {location_code}", sort_order=index,
            is_active=True, created_by=user.id,
        ))
    await db.commit()
    await db.refresh(rack)
    return LaboratoryRackOutput(
        id=rack.id, area_id=area.id, area_code=area.code, area_name=area.name,
        code=rack.code, name=rack.name, position_prefix=rack.position_prefix,
        rows=rack.rows, columns=rack.columns,
        layout_row=rack.layout_row, layout_column=rack.layout_column,
        layout_span=rack.layout_span, sort_order=rack.sort_order,
        is_active=rack.is_active,
    )


@router.put("/settings/racks/{rack_id}", response_model=LaboratoryRackOutput)
async def update_location_rack(
    rack_id: int,
    payload: LaboratoryRackUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_master_management(user)
    rack = await db.get(LaboratoryRack, rack_id)
    if rack is None:
        raise HTTPException(status_code=404, detail="Estante não encontrada.")
    area = await db.get(LaboratoryArea, rack.area_id)
    if payload.is_active:
        await _ensure_rack_layout_available(
            db,
            area_id=rack.area_id,
            layout_row=payload.layout_row,
            layout_column=payload.layout_column,
            layout_span=payload.layout_span,
            exclude_rack_id=rack.id,
        )
    if rack.is_active and not payload.is_active:
        location_codes = list((await db.scalars(
            select(LaboratoryLocation.code).where(LaboratoryLocation.rack_id == rack.id)
        )).all())
        occupied = await db.scalar(
            select(func.count()).select_from(LaboratoryWorkOrder).where(
                LaboratoryWorkOrder.storage_location.in_(location_codes)
            )
        ) if location_codes else 0
        if occupied:
            raise HTTPException(
                status_code=409,
                detail="Não é possível inativar uma estante que possui equipamentos localizados.",
            )
    rack.name = payload.name.strip()
    rack.layout_row = payload.layout_row
    rack.layout_column = payload.layout_column
    rack.layout_span = payload.layout_span
    rack.sort_order = payload.sort_order
    rack.is_active = payload.is_active
    await db.commit()
    await db.refresh(rack)
    return LaboratoryRackOutput(
        id=rack.id, area_id=rack.area_id,
        area_code=area.code, area_name=area.name,
        code=rack.code, name=rack.name, position_prefix=rack.position_prefix,
        rows=rack.rows, columns=rack.columns,
        layout_row=rack.layout_row, layout_column=rack.layout_column,
        layout_span=rack.layout_span, sort_order=rack.sort_order,
        is_active=rack.is_active,
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
    await _active_company_or_422(db, payload.company_code)
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


def _require_technician_management(user: User) -> None:
    if user.role.strip().lower() not in {"super_admin", "admin", "gestao"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente ADM ou Gestão pode cadastrar, editar ou inativar técnicos.",
        )


def _normalized_technician_name(name: str) -> str:
    return " ".join(name.casefold().split())


async def _active_technician_with_name(
    db: AsyncSession,
    name: str,
    *,
    exclude_id: int | None = None,
) -> LaboratoryTechnician | None:
    normalized = _normalized_technician_name(name)
    rows = list((await db.scalars(
        select(LaboratoryTechnician).where(LaboratoryTechnician.is_active.is_(True))
    )).all())
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        if _normalized_technician_name(row.name) == normalized:
            return row
    return None



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
    rows = list((await db.scalars(query.order_by(LaboratoryTechnician.name, LaboratoryTechnician.id))).all())
    if include_inactive:
        return rows
    unique: dict[str, LaboratoryTechnician] = {}
    for technician in rows:
        unique.setdefault(_normalized_technician_name(technician.name), technician)
    return list(unique.values())


@router.post("/technicians", response_model=TechnicianOutput, status_code=status.HTTP_201_CREATED)
async def create_technician(
    payload: TechnicianInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_technician_management(user)
    await _active_company_or_422(db, payload.company_code)
    duplicate = await _active_technician_with_name(db, payload.name)
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe um técnico ativo com este nome: {duplicate.name}. Edite o cadastro existente.",
        )
    technician = LaboratoryTechnician(**payload.model_dump(), created_by=user.id)
    db.add(technician)
    await db.commit()
    await db.refresh(technician)
    return technician


@router.put("/technicians/{technician_id}", response_model=TechnicianOutput)
async def update_technician(
    technician_id: int,
    payload: TechnicianUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_technician_management(user)
    technician = await db.get(LaboratoryTechnician, technician_id)
    if not technician:
        raise HTTPException(status_code=404, detail="Técnico não encontrado.")
    duplicate = await _active_technician_with_name(db, payload.name, exclude_id=technician_id)
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe outro técnico ativo com este nome: {duplicate.name}.",
        )
    for field, value in payload.model_dump().items():
        setattr(technician, field, value)
    await db.commit()
    await db.refresh(technician)
    return technician


@router.delete("/technicians/{technician_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_technician(
    technician_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_technician_management(user)
    technician = await db.get(LaboratoryTechnician, technician_id)
    if not technician:
        raise HTTPException(status_code=404, detail="Técnico não encontrado.")
    technician.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------- workflow settings --


@router.get("/workflow-options", response_model=list[WorkflowOptionOutput])
async def list_workflow_options(
    include_inactive: bool = QUERY_INCLUDE_INACTIVE,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    query = select(LaboratoryWorkflowOption)
    if not include_inactive:
        query = query.where(LaboratoryWorkflowOption.is_active.is_(True))
    query = query.order_by(
        LaboratoryWorkflowOption.kind,
        LaboratoryWorkflowOption.sort_order,
        LaboratoryWorkflowOption.id,
    )
    return list((await db.scalars(query)).all())


@router.post(
    "/workflow-options",
    response_model=WorkflowOptionOutput,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_option(
    payload: WorkflowOptionCreate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_workflow_management(user)
    base_code = _workflow_code(payload.kind, payload.label)
    code = base_code
    suffix = 2
    while await _workflow_option_by_code(db, kind=payload.kind, code=code, active_only=False):
        tail = f"_{suffix}"
        code = f"{base_code[: 40 - len(tail)]}{tail}"
        suffix += 1

    option = LaboratoryWorkflowOption(
        kind=payload.kind,
        code=code,
        label=payload.label.strip(),
        sort_order=payload.sort_order,
        is_active=True,
        is_system=False,
        created_by=user.id,
    )
    db.add(option)
    await db.commit()
    await db.refresh(option)
    return option


@router.put("/workflow-options/{option_id}", response_model=WorkflowOptionOutput)
async def update_workflow_option(
    option_id: int,
    payload: WorkflowOptionUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_workflow_management(user)
    option = await db.get(LaboratoryWorkflowOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Status/substatus não encontrado.")
    option.label = payload.label.strip()
    option.sort_order = payload.sort_order
    option.is_active = payload.is_active
    await db.commit()
    await db.refresh(option)
    return option


@router.delete("/workflow-options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_workflow_option(
    option_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_workflow_management(user)
    option = await db.get(LaboratoryWorkflowOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Status/substatus não encontrado.")
    option.is_active = False
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
    include_inactive: bool = QUERY_INCLUDE_INACTIVE,
    month: int | None = QUERY_MONTH,
    year: int | None = QUERY_YEAR,
    user: User = CURRENT_USER_DEP,
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
        include_inactive=include_inactive and _can_override_work_order_status(user),
    )
    return WorkOrderPage(
        items=[
            _to_work_order_output(
                wo,
                include_sensitive_values=user_can_view_sensitive_values(user.role),
            )
            for wo in work_orders
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=total_pages(total, page_size),
    )


@router.get("/locations/next")
async def next_laboratory_location(
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    return {"location": await next_free_storage_location(db)}


@router.get("/locations/map", response_model=LaboratoryLocationMapOutput)
async def laboratory_location_map(
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    config = await _location_config_output(db)
    active_areas = {area.id: area for area in config.areas if area.is_active}
    active_racks = {
        rack.id: rack
        for rack in config.racks
        if rack.is_active and rack.area_id in active_areas
    }
    active_locations = [
        location
        for location in config.locations
        if location.is_active
        and location.area_id in active_areas
        and (location.rack_id is None or location.rack_id in active_racks)
    ]
    valid_codes = {location.code for location in active_locations}
    located_orders = (
        await db.execute(
            select(LaboratoryWorkOrder)
            .where(
                LaboratoryWorkOrder.storage_location.in_(valid_codes),
                LaboratoryWorkOrder.is_inactive.is_(False),
            )
            .order_by(LaboratoryWorkOrder.storage_location.asc(), LaboratoryWorkOrder.number.asc())
        )
    ).scalars().unique().all()
    grouped = group_work_orders_by_location(located_orders)

    located_ids = [work_order.id for work_order in located_orders]
    current_location_history: dict[int, LaboratoryLocationHistory] = {}
    if located_ids:
        history_rows = list((
            await db.scalars(
                select(LaboratoryLocationHistory)
                .where(
                    LaboratoryLocationHistory.work_order_id.in_(located_ids),
                    LaboratoryLocationHistory.released_at.is_(None),
                )
                .order_by(
                    LaboratoryLocationHistory.work_order_id,
                    LaboratoryLocationHistory.assigned_at.desc(),
                    LaboratoryLocationHistory.id.desc(),
                )
            )
        ).all())
        for history in history_rows:
            current_location_history.setdefault(history.work_order_id, history)

    now = datetime.now(UTC)
    slots: list[LaboratoryLocationSlotOutput] = []
    urgent_positions = 0
    urgent_work_orders = 0
    attention_positions = 0
    attention_work_orders = 0
    critical_positions = 0
    critical_work_orders = 0
    located_work_orders = 0
    for location in active_locations:
        occupants: list[LaboratoryLocationOccupantOutput] = []
        for work_order in grouped.get(location.code, []):
            equipment_label = (
                work_order.equipment.equipment_type
                or work_order.equipment.model
                or work_order.equipment.serial_number
                or "Equipamento"
            )
            history = current_location_history.get(work_order.id)
            assigned_at = history.assigned_at if history and history.location == location.code else None
            duration_seconds = location_dwell_seconds(assigned_at, now=now)
            dwell_level = location_dwell_level(duration_seconds)
            occupants.append(LaboratoryLocationOccupantOutput(
                work_order_id=work_order.id,
                work_order_number=work_order.number,
                customer_name=work_order.customer_name or "Sem cliente",
                equipment_label=equipment_label,
                status=work_order.status,
                priority=work_order.priority,
                location_assigned_at=assigned_at,
                location_duration_seconds=duration_seconds,
                dwell_level=dwell_level,
            ))
        has_urgent = any(item.priority == "urgent" for item in occupants)
        has_attention = any(item.dwell_level == "attention" for item in occupants)
        has_critical = any(item.dwell_level == "critical" for item in occupants)
        urgent_work_orders += sum(1 for item in occupants if item.priority == "urgent")
        attention_work_orders += sum(1 for item in occupants if item.dwell_level == "attention")
        critical_work_orders += sum(1 for item in occupants if item.dwell_level == "critical")
        located_work_orders += len(occupants)
        if has_urgent:
            urgent_positions += 1
        if has_attention:
            attention_positions += 1
        if has_critical:
            critical_positions += 1
        rack = active_racks.get(location.rack_id) if location.rack_id else None
        area = active_areas[location.area_id]
        first = occupants[0] if occupants else None
        slots.append(LaboratoryLocationSlotOutput(
            location=location.code,
            area_code=area.code,
            area_name=area.name,
            area_sort_order=area.sort_order,
            rack_code=rack.code if rack else None,
            rack_name=rack.name if rack else None,
            rack_sort_order=rack.sort_order if rack else 0,
            rack_rows=rack.rows if rack else 1,
            rack_columns=rack.columns if rack else 1,
            rack_layout_row=rack.layout_row if rack else 1,
            rack_layout_column=rack.layout_column if rack else 1,
            rack_layout_span=rack.layout_span if rack else 1,
            slot_number=location.sort_order,
            occupants=occupants,
            occupancy_count=len(occupants),
            has_urgent=has_urgent,
            has_attention=has_attention,
            has_critical=has_critical,
            max_location_duration_seconds=max(
                (item.location_duration_seconds for item in occupants),
                default=0,
            ),
            work_order_id=first.work_order_id if first else None,
            work_order_number=first.work_order_number if first else None,
            customer_name=first.customer_name if first else None,
            equipment_label=first.equipment_label if first else None,
            status=first.status if first else None,
            priority=first.priority if first else None,
        ))

    occupied_positions = sum(1 for slot in slots if slot.occupancy_count > 0)
    without_location = int(await db.scalar(
        select(func.count()).select_from(LaboratoryWorkOrder).where(
            LaboratoryWorkOrder.is_inactive.is_(False),
            or_(
                LaboratoryWorkOrder.storage_location.is_(None),
                LaboratoryWorkOrder.storage_location == "",
                ~LaboratoryWorkOrder.storage_location.in_(valid_codes),
            )
        )
    ) or 0)
    return LaboratoryLocationMapOutput(
        total_positions=len(slots),
        occupied_positions=occupied_positions,
        free_positions=len(slots) - occupied_positions,
        located_work_orders=located_work_orders,
        urgent_positions=urgent_positions,
        urgent_work_orders=urgent_work_orders,
        attention_positions=attention_positions,
        attention_work_orders=attention_work_orders,
        critical_positions=critical_positions,
        critical_work_orders=critical_work_orders,
        work_orders_without_location=without_location,
        slots=slots,
    )


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderOutput)
async def get_work_order(
    work_order_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    return _to_work_order_output(
        await _work_order_or_404(db, work_order_id),
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.post("/work-orders", response_model=WorkOrderOutput, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    payload: WorkOrderInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _active_company_or_422(db, payload.company_code)
    await _validate_customer_company(db, payload.customer_id, payload.company_code)
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
    try:
        await ensure_storage_location_available(db, payload.storage_location)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        entry_invoice_2=payload.entry_invoice_2,
        entry_invoice_3=payload.entry_invoice_3,
        entry_invoice_access_key=payload.entry_invoice_access_key,
        exit_invoice=payload.exit_invoice,
        exit_invoice_2=payload.exit_invoice_2,
        exit_invoice_3=payload.exit_invoice_3,
        exit_invoice_access_key=payload.exit_invoice_access_key,
        warranty_invoice=payload.warranty_invoice,
        warranty_invoice_2=payload.warranty_invoice_2,
        warranty_invoice_3=payload.warranty_invoice_3,
        warranty_entry_invoice_1=payload.warranty_entry_invoice_1,
        warranty_entry_invoice_2=payload.warranty_entry_invoice_2,
        warranty_entry_invoice_3=payload.warranty_entry_invoice_3,
        warranty_exit_invoice_1=payload.warranty_exit_invoice_1,
        warranty_exit_invoice_2=payload.warranty_exit_invoice_2,
        warranty_exit_invoice_3=payload.warranty_exit_invoice_3,
        storage_location=None,
        parts_cost=(payload.parts_cost or None) if user_can_view_sensitive_values(user.role) else None,
        quoted_value=(payload.quoted_value or None) if user_can_view_sensitive_values(user.role) else None,
        approved_value=(payload.approved_value or None) if user_can_view_sensitive_values(user.role) else None,
        internal_notes=payload.internal_notes,
        customer_notes=payload.customer_notes,
        created_by=user.id,
    )
    db.add(work_order)
    await db.flush()
    if payload.storage_location:
        await set_storage_location(db, work_order, payload.storage_location, user.id)
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
    return _to_work_order_output(
        await _work_order_or_404(db, work_order.id),
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.patch("/work-orders/{work_order_id}", response_model=WorkOrderOutput)
async def update_work_order(
    work_order_id: int,
    payload: WorkOrderUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    if work_order.is_inactive:
        raise HTTPException(status_code=409, detail="OS inativada não pode ser alterada.")
    if payload.company_code != work_order.company_code:
        from app.inventory.models import InventoryMovement
        inventory_linked = await db.scalar(select(InventoryMovement.id).where(
            InventoryMovement.work_order_id == work_order_id
        ).limit(1))
        if inventory_linked is not None:
            raise HTTPException(409, "Não é permitido alterar a empresa de uma O.S. com peças de estoque.")
        await _active_company_or_422(db, payload.company_code)
    await _validate_customer_company(db, payload.customer_id, payload.company_code)
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

    apply_work_order_update(
        work_order,
        payload,
        equipment_id=equipment.id,
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )
    try:
        await set_storage_location(db, work_order, payload.storage_location, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    work_order.version += 1

    # Impede que a edição manual da OS sobrescreva custos canônicos de estoque.
    from app.inventory.models import InventoryMovement
    inventory_linked = await db.scalar(select(InventoryMovement.id).where(
        InventoryMovement.work_order_id == work_order_id
    ).limit(1))
    if inventory_linked is not None:
        from app.purchasing.material_service import recalculate_work_order_parts_cost
        await recalculate_work_order_parts_cost(db, work_order_id)

    await db.commit()
    return _to_work_order_output(
        await _work_order_or_404(db, work_order.id),
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.post("/work-orders/{work_order_id}/inactivate", response_model=WorkOrderOutput)
async def inactivate_work_order(
    work_order_id: int,
    payload: InactivateWorkOrderInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_master_management(user)
    work_order = await _work_order_or_404(db, work_order_id)
    if work_order.is_inactive:
        raise HTTPException(status_code=409, detail="A OS já está inativada.")
    if work_order.version != payload.version:
        raise HTTPException(status_code=409, detail="A OS foi alterada. Recarregue antes de inativar.")
    linked_finance = await db.scalar(
        select(FinancialEntry.id).where(
            FinancialEntry.work_order_id == work_order_id,
            FinancialEntry.is_deleted.is_(False),
        ).limit(1)
    )
    if linked_finance is not None:
        raise HTTPException(status_code=409, detail="A OS possui lançamento financeiro ativo. Regularize-o antes de inativar.")
    from app.inventory.models import InventoryMovement
    from app.purchasing.material_models import MaterialRequest
    inventory_link = await db.scalar(select(InventoryMovement.id).where(
        InventoryMovement.work_order_id == work_order_id,
    ).limit(1))
    material_link = await db.scalar(select(MaterialRequest.id).where(
        MaterialRequest.work_order_id == work_order_id,
    ).limit(1))
    if inventory_link is not None or material_link is not None:
        raise HTTPException(status_code=409, detail=(
            "A OS possui movimentações ou solicitações de materiais. Regularize os vínculos "
            "de estoque e compras antes de inativar."
        ))
    reason = payload.reason.strip()
    if len(reason) < 10:
        raise HTTPException(status_code=422, detail="Informe um motivo com pelo menos 10 caracteres.")
    # A posição física fica livre, mas a movimentação anterior continua no histórico.
    if work_order.storage_location:
        await set_storage_location(db, work_order, None, user.id)
    work_order.is_inactive = True
    work_order.inactivated_at = datetime.now(UTC)
    work_order.inactivated_by = user.id
    work_order.inactivation_reason = reason
    work_order.version += 1
    db.add(LaboratoryStatusHistory(
        work_order_id=work_order.id,
        previous_status=work_order.status,
        new_status=work_order.status,
        note="OS inativada: " + reason,
        user_id=user.id,
    ))
    await db.commit()
    return _to_work_order_output(
        await _work_order_or_404(db, work_order.id),
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.post("/work-orders/{work_order_id}/status", response_model=WorkOrderOutput)
async def change_status(
    work_order_id: int,
    payload: StatusChangeInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    if work_order.is_inactive:
        raise HTTPException(status_code=409, detail="OS inativada não pode mudar de status.")
    if work_order.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail="Esta OS foi alterada por outra pessoa. Recarregue antes de aplicar o status.",
        )
    is_builtin_status = payload.status in WORK_ORDER_STATUSES
    if payload.status in BUSINESS_STATUS_TARGETS:
        configured_status = await _workflow_option_by_code(
            db,
            kind="status",
            code=payload.status,
            active_only=True,
        )
        if configured_status is None:
            raise HTTPException(status_code=422, detail="Status do Laboratório inválido ou inativo.")
    elif not is_builtin_status:
        custom_status = await _workflow_option_by_code(
            db,
            kind="status",
            code=payload.status,
            active_only=True,
        )
        if custom_status is None:
            raise HTTPException(status_code=422, detail="Status do Laboratório inválido ou inativo.")

    previous = work_order.status

    # O status do Laboratório é operacional e livre: qualquer usuário com acesso
    # ao módulo pode mover a O.S. entre status principais ativos. A rastreabilidade
    # é preservada pelo histórico de status, sem impor uma hierarquia artificial.
    if previous != payload.status:
        work_order.status = payload.status
        work_order.version += 1
        if payload.status in {"completed", "awaiting_pickup"} and work_order.completed_at is None:
            work_order.completed_at = datetime.now(UTC)
        work_order.is_cancelled = payload.status == "cancelled"
        db.add(
            LaboratoryStatusHistory(
                work_order_id=work_order.id,
                previous_status=previous,
                new_status=payload.status,
                note=payload.note,
                user_id=user.id,
            )
        )

        # Snapshot imutável da liberação técnica. O relatório futuro deve usar
        # este evento, não o técnico atualmente atribuído à O.S., pois a
        # atribuição pode mudar depois da liberação.
        if payload.status == "awaiting_pickup":
            technician = (
                await db.get(LaboratoryTechnician, work_order.assigned_technician_id)
                if work_order.assigned_technician_id is not None
                else None
            )
            db.add(
                LaboratoryReleaseEvent(
                    work_order_id=work_order.id,
                    technician_id=technician.id if technician else None,
                    technician_name=technician.name if technician else None,
                    released_at=datetime.now(UTC),
                    released_by_user_id=user.id,
                    previous_status=previous,
                )
            )

        await _sync_finance_on_status_change(db, work_order, previous, payload.status, user.id)
        if payload.status == "awaiting_quote" and previous != "awaiting_quote":
            await notify_roles(
                db,
                roles={"super_admin", "admin", "gestao"},
                category="quote",
                severity="warning",
                title=f"OS {work_order.number} · orçamento pendente",
                message=f"{work_order.customer_name} · {work_order.equipment_name}. A análise técnica foi concluída e a OS está preparando orçamento.",
                target=f"/laboratorio?os={work_order.id}&aba=quote",
                entity_type="laboratory_work_order",
                entity_id=work_order.id,
                work_order_id=work_order.id,
                exclude_user_id=user.id,
            )
        await db.commit()
    return _to_work_order_output(
        await _work_order_or_404(db, work_order.id),
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.post(
    "/work-orders/{work_order_id}/substatuses/{substatus_code}",
    response_model=WorkOrderOutput,
)
async def toggle_substatus(
    work_order_id: int,
    substatus_code: str,
    payload: SubstatusToggleInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    if work_order.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail="Esta OS foi alterada por outra pessoa. Recarregue antes de alterar o substatus.",
        )
    option = await _workflow_option_by_code(
        db,
        kind="substatus",
        code=substatus_code,
        active_only=True,
    )
    if option is None:
        raise HTTPException(status_code=404, detail="Substatus não encontrado ou inativo.")

    await _set_work_order_substatus(
        db,
        work_order=work_order,
        code=substatus_code,
        active=payload.active,
        user_id=user.id,
    )
    if payload.active and substatus_code == "awaiting_delivery" and work_order.completed_at is None:
        work_order.completed_at = datetime.now(UTC)
    if payload.active and substatus_code == "delivered" and work_order.delivered_at is None:
        work_order.delivered_at = datetime.now(UTC)
    work_order.version += 1
    db.add(
        LaboratoryAuditEvent(
            work_order_id=work_order.id,
            action="substatus_changed",
            description=(
                f"Substatus '{option.label}' "
                f"{'marcado' if payload.active else 'desmarcado'}."
            ),
            user_id=user.id,
        )
    )
    await db.commit()
    return _to_work_order_output(
        await _work_order_or_404(db, work_order.id),
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


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

    release_events = list((await db.scalars(
        select(LaboratoryReleaseEvent)
        .where(LaboratoryReleaseEvent.work_order_id == work_order_id)
        .order_by(LaboratoryReleaseEvent.id)
    )).all())
    release_iter = iter(release_events)

    result: list[StatusHistoryOutput] = []
    for row in rows:
        history = row.LaboratoryStatusHistory
        release_event = next(release_iter, None) if history.new_status == "awaiting_pickup" else None
        result.append(
            StatusHistoryOutput(
                id=history.id,
                previous_status=history.previous_status,
                new_status=history.new_status,
                note=history.note,
                user_id=history.user_id,
                user_name=row.name,
                created_at=history.created_at,
                release_event_id=release_event.id if release_event else None,
                release_technician_id=release_event.technician_id if release_event else None,
                release_technician_name=release_event.technician_name if release_event else None,
                release_released_at=release_event.released_at if release_event else None,
            )
        )
    return result


@router.get(
    "/work-orders/{work_order_id}/location-history",
    response_model=list[LocationHistoryOutput],
)
async def list_location_history(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    query = (
        select(LaboratoryLocationHistory, User.name)
        .join(User, User.id == LaboratoryLocationHistory.changed_by)
        .where(LaboratoryLocationHistory.work_order_id == work_order_id)
        .order_by(LaboratoryLocationHistory.assigned_at, LaboratoryLocationHistory.id)
    )
    now = datetime.now(UTC)
    rows = (await db.execute(query)).all()
    result: list[LocationHistoryOutput] = []
    for row in rows:
        history = row.LaboratoryLocationHistory
        end = history.released_at or now
        duration_seconds = max(0, int((end - history.assigned_at).total_seconds()))
        result.append(LocationHistoryOutput(
            id=history.id,
            location=history.location,
            assigned_at=history.assigned_at,
            released_at=history.released_at,
            changed_by=history.changed_by,
            changed_by_name=row.name,
            duration_seconds=duration_seconds,
            is_current=history.released_at is None,
        ))
    return result


# ------------------------------------------------------------------ label --


@router.get("/work-orders/{work_order_id}/label.pdf")
async def work_order_label_pdf(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    tracking_token = work_order.tracking_token or await _issue_tracking_token(db, work_order)
    pdf_bytes = await asyncio.to_thread(label_pdf, work_order, work_order.equipment, tracking_token)
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


# --------------------------------------------------------------- mechanics --


@router.get(
    "/work-orders/{work_order_id}/mechanics/painting",
    response_model=list[PaintingDispatchOutput],
)
async def list_mechanics_painting(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    return await _list_painting_dispatches_output(db, work_order_id)


@router.post(
    "/work-orders/{work_order_id}/mechanics/painting",
    response_model=PaintingDispatchOutput,
    status_code=status.HTTP_201_CREATED,
)
async def create_mechanics_painting(
    work_order_id: int,
    payload: PaintingDispatchCreate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    work_order = await _work_order_or_404(db, work_order_id)
    dispatch = LaboratoryMechanicalPaintingDispatch(
        work_order_id=work_order.id,
        status="draft",
        provider=payload.provider.strip() if payload.provider else None,
        notes=payload.notes.strip() if payload.notes else None,
        created_by=user.id,
    )
    db.add(dispatch)
    await db.flush()
    for position, description in enumerate(payload.items, start=1):
        db.add(LaboratoryMechanicalPaintingItem(
            dispatch_id=dispatch.id,
            position=position,
            description=description,
        ))
    db.add(LaboratoryAuditEvent(
        work_order_id=work_order.id,
        action="painting_dispatch_draft",
        description=f"Controle de saída para pintura externa criado com {len(payload.items)} item(ns).",
        user_id=user.id,
    ))
    await db.commit()
    await db.refresh(dispatch)
    return await _painting_dispatch_output(db, dispatch)


@router.post(
    "/mechanics/painting/{dispatch_id}/photos",
    response_model=PaintingPhotoOutput,
    status_code=status.HTTP_201_CREATED,
)
async def upload_mechanics_painting_photo(
    dispatch_id: int,
    file: UploadFile = REQUIRED_FILE,
    phase: str = QUERY_PAINT_PHASE,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    dispatch = await _painting_dispatch_or_404(db, dispatch_id)
    work_order = await _work_order_or_404(db, dispatch.work_order_id)
    if phase == "outbound" and dispatch.status != "draft":
        raise HTTPException(status_code=409, detail="Fotos da saída só podem ser anexadas antes do envio.")
    if phase == "return" and dispatch.status != "sent":
        raise HTTPException(status_code=409, detail="Fotos do retorno só podem ser anexadas enquanto a pintura aguarda retorno.")

    try:
        directory = resolve_laboratory_storage_path(
            UPLOAD_ROOT,
            Path(work_order.company_code) / work_order.number / "mecanica-pintura",
        )
        streamed = await persist_streamed_upload(
            file,
            directory=directory,
            max_size=MAX_UPLOAD_SIZE,
        )
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail="A imagem excede 15 MB.") from exc
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Armazenamento de imagens indisponível.",
        ) from exc

    if not streamed.mime_type.startswith("image/"):
        try:
            streamed.path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=415, detail="A evidência da pintura deve ser uma imagem.")

    document = LaboratoryDocument(
        work_order_id=work_order.id,
        category="pintura",
        original_name=file.filename or streamed.path.name,
        storage_path=str(streamed.path),
        mime_type=streamed.mime_type,
        size_bytes=streamed.size_bytes,
        checksum_sha256=streamed.checksum_sha256,
        uploaded_by=user.id,
    )
    await commit_laboratory_document(
        db,
        document,
        root=UPLOAD_ROOT,
        stored_path=streamed.path,
    )
    position = int(await db.scalar(
        select(func.count())
        .select_from(LaboratoryMechanicalPaintingPhoto)
        .where(
            LaboratoryMechanicalPaintingPhoto.dispatch_id == dispatch.id,
            LaboratoryMechanicalPaintingPhoto.phase == phase,
        )
    ) or 0) + 1
    photo = LaboratoryMechanicalPaintingPhoto(
        dispatch_id=dispatch.id,
        document_id=document.id,
        phase=phase,
        position=position,
    )
    db.add(photo)
    try:
        await db.commit()
        await db.refresh(photo)
    except Exception:
        await db.rollback()
        persisted_document = await db.get(LaboratoryDocument, document.id)
        if persisted_document is not None:
            await delete_laboratory_document_storage(db, persisted_document, root=UPLOAD_ROOT)
        raise
    return PaintingPhotoOutput(
        id=photo.id,
        document_id=document.id,
        phase=photo.phase,
        position=photo.position,
        caption=photo.caption,
        original_name=document.original_name,
        mime_type=document.mime_type,
        created_at=photo.created_at,
    )


@router.post(
    "/mechanics/painting/{dispatch_id}/send",
    response_model=PaintingDispatchOutput,
)
async def send_mechanics_painting(
    dispatch_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    dispatch = await _painting_dispatch_or_404(db, dispatch_id)
    if dispatch.status != "draft":
        raise HTTPException(status_code=409, detail="Somente um rascunho pode ser enviado para pintura.")

    item_count = int(await db.scalar(
        select(func.count())
        .select_from(LaboratoryMechanicalPaintingItem)
        .where(LaboratoryMechanicalPaintingItem.dispatch_id == dispatch.id)
    ) or 0)
    photo_count = int(await db.scalar(
        select(func.count())
        .select_from(LaboratoryMechanicalPaintingPhoto)
        .where(
            LaboratoryMechanicalPaintingPhoto.dispatch_id == dispatch.id,
            LaboratoryMechanicalPaintingPhoto.phase == "outbound",
        )
    ) or 0)
    if item_count == 0:
        raise HTTPException(status_code=422, detail="Informe ao menos uma peça antes da saída.")
    if photo_count == 0:
        raise HTTPException(
            status_code=422,
            detail="Anexe ao menos uma foto do material antes de confirmar a saída para pintura.",
        )

    dispatch.status = "sent"
    dispatch.sent_at = datetime.now(UTC)
    dispatch.sent_by = user.id
    db.add(LaboratoryAuditEvent(
        work_order_id=dispatch.work_order_id,
        action="painting_dispatch_sent",
        description=f"{item_count} peça(s)/parte(s) enviadas para pintura externa.",
        user_id=user.id,
    ))
    await db.commit()
    await db.refresh(dispatch)
    return await _painting_dispatch_output(db, dispatch)


@router.patch(
    "/mechanics/painting/items/{item_id}",
    response_model=PaintingItemOutput,
)
async def update_mechanics_painting_item(
    item_id: int,
    payload: PaintingItemUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    item = await db.get(LaboratoryMechanicalPaintingItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item da pintura não encontrado.")
    dispatch = await _painting_dispatch_or_404(db, item.dispatch_id)
    if dispatch.status != "sent":
        raise HTTPException(
            status_code=409,
            detail="A conferência de retorno só pode ser feita após a saída para pintura.",
        )
    item.returned = payload.returned
    item.return_note = payload.return_note.strip() if payload.return_note else None
    item.returned_at = datetime.now(UTC) if payload.returned else None
    await db.commit()
    await db.refresh(item)
    return PaintingItemOutput(
        id=item.id,
        position=item.position,
        description=item.description,
        returned=item.returned,
        return_note=item.return_note,
        returned_at=item.returned_at,
    )


@router.post(
    "/mechanics/painting/{dispatch_id}/return",
    response_model=PaintingDispatchOutput,
)
async def return_mechanics_painting(
    dispatch_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    dispatch = await _painting_dispatch_or_404(db, dispatch_id)
    if dispatch.status != "sent":
        raise HTTPException(status_code=409, detail="Este controle não está aguardando retorno.")

    pending = int(await db.scalar(
        select(func.count())
        .select_from(LaboratoryMechanicalPaintingItem)
        .where(
            LaboratoryMechanicalPaintingItem.dispatch_id == dispatch.id,
            LaboratoryMechanicalPaintingItem.returned.is_(False),
        )
    ) or 0)
    if pending:
        raise HTTPException(
            status_code=422,
            detail=f"Existem {pending} item(ns) sem conferência de retorno.",
        )

    dispatch.status = "returned"
    dispatch.returned_at = datetime.now(UTC)
    dispatch.returned_by = user.id
    db.add(LaboratoryAuditEvent(
        work_order_id=dispatch.work_order_id,
        action="painting_dispatch_returned",
        description="Retorno da pintura externa conferido integralmente.",
        user_id=user.id,
    ))
    await db.commit()
    await db.refresh(dispatch)
    return await _painting_dispatch_output(db, dispatch)


# ---------------------------------------------------------------- quotes ---


@router.get("/work-orders/{work_order_id}/quotes", response_model=list[QuoteOutput])
async def list_quotes(
    work_order_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    query = (
        select(LaboratoryQuote)
        .where(LaboratoryQuote.work_order_id == work_order_id)
        .order_by(LaboratoryQuote.revision.desc())
    )
    rows = list((await db.scalars(query)).all())
    include_values = user_can_create_quote(user.role, user.modules)
    return [_to_quote_output(item, include_sensitive_values=include_values) for item in rows]


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
    existing_draft = await db.scalar(
        select(LaboratoryQuote)
        .where(
            LaboratoryQuote.work_order_id == work_order_id,
            LaboratoryQuote.status == "draft",
            LaboratoryQuote.emitted_at.is_(None),
        )
        .order_by(LaboratoryQuote.revision.desc())
        .limit(1)
    )
    if existing_draft is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Já existe um rascunho editável para esta O.S. "
                "Abra o rascunho existente em vez de criar outra revisão."
            ),
        )

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
        billing_terms=payload.billing_terms,
        warranty_months=payload.warranty_months,
        warranty_terms=payload.warranty_terms,
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
    photo_docs = []
    if payload.photos:
        ids = [photo.document_id for photo in payload.photos]
        photo_docs = list((await db.scalars(
            select(LaboratoryDocument).where(
                LaboratoryDocument.id.in_(ids),
                LaboratoryDocument.work_order_id == work_order_id,
            )
        )).all())
        docs_by_id = {doc.id: doc for doc in photo_docs}
        if len(docs_by_id) != len(set(ids)) or any(not doc.mime_type.startswith("image/") for doc in photo_docs):
            raise HTTPException(status_code=422, detail="Fotos do laudo devem ser imagens desta O.S.")
        quote.photos = [
            LaboratoryQuotePhoto(
                position=index + 1,
                document_id=photo.document_id,
                caption=photo.caption,
            )
            for index, photo in enumerate(payload.photos)
        ]
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return _to_quote_output(quote, include_sensitive_values=True)


@router.post("/quotes/{quote_id}/revisions", response_model=QuoteOutput, status_code=status.HTTP_201_CREATED)
async def create_quote_revision(
    quote_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_quote_permission(user)
    source = await db.get(LaboratoryQuote, quote_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    if source.status != "emitted" and source.emitted_at is None:
        raise HTTPException(status_code=409, detail="A revisão de origem precisa estar emitida.")
    existing_draft = await db.scalar(select(LaboratoryQuote).where(
        LaboratoryQuote.work_order_id == source.work_order_id,
        LaboratoryQuote.status == "draft",
        LaboratoryQuote.emitted_at.is_(None),
    ))
    if existing_draft is not None:
        raise HTTPException(status_code=409, detail="Já existe um rascunho editável para esta O.S.")
    last_revision = await db.scalar(select(func.max(LaboratoryQuote.revision)).where(
        LaboratoryQuote.work_order_id == source.work_order_id
    ))
    clone = LaboratoryQuote(
        work_order_id=source.work_order_id,
        revision=(last_revision or source.revision) + 1,
        status="draft",
        service_code=source.service_code,
        technical_report=source.technical_report,
        services_description=source.services_description,
        delivery_days=source.delivery_days,
        billing_days=source.billing_days,
        billing_terms=source.billing_terms,
        warranty_months=source.warranty_months,
        warranty_terms=source.warranty_terms,
        payment_terms=source.payment_terms,
        validity_days=source.validity_days,
        return_condition=source.return_condition,
        consumer_clause=source.consumer_clause,
        supply_clause=source.supply_clause,
        estimate_clause=source.estimate_clause,
        discount_type=source.discount_type,
        discount_value=source.discount_value,
        subtotal=source.subtotal,
        total=source.total,
        created_by=user.id,
    )
    clone.items = [LaboratoryQuoteItem(
        position=item.position, description=item.description,
        quantity=item.quantity, unit_value=item.unit_value,
    ) for item in source.items]
    clone.photos = [LaboratoryQuotePhoto(
        position=photo.position, document_id=photo.document_id, caption=photo.caption,
    ) for photo in source.photos]
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return _to_quote_output(clone, include_sensitive_values=True)


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
        "service_code", "technical_report", "services_description", "delivery_days", "billing_days", "billing_terms",
        "warranty_months", "warranty_terms", "payment_terms", "validity_days", "return_condition", "consumer_clause",
        "supply_clause", "estimate_clause", "discount_type", "discount_value",
    ):
        setattr(quote, field, getattr(payload, field))
    quote.subtotal = subtotal
    quote.total = total
    quote.items = [
        LaboratoryQuoteItem(position=index + 1, **item.model_dump())
        for index, item in enumerate(payload.items)
    ]
    ids = [photo.document_id for photo in payload.photos]
    if ids:
        docs = list((await db.scalars(
            select(LaboratoryDocument).where(
                LaboratoryDocument.id.in_(ids),
                LaboratoryDocument.work_order_id == quote.work_order_id,
            )
        )).all())
        docs_by_id = {doc.id: doc for doc in docs}
        if len(docs_by_id) != len(set(ids)) or any(not doc.mime_type.startswith("image/") for doc in docs):
            raise HTTPException(status_code=422, detail="Fotos do laudo devem ser imagens desta O.S.")
    quote.photos = [
        LaboratoryQuotePhoto(position=index + 1, document_id=photo.document_id, caption=photo.caption)
        for index, photo in enumerate(payload.photos)
    ]
    await db.commit()
    await db.refresh(quote)
    return _to_quote_output(quote, include_sensitive_values=True)


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
    _require_quote_permission(user)

    if not preview and not (quote.technical_report or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Preencha o diagnóstico técnico / laudo antes de emitir o orçamento.",
        )

    company_profile = await db.scalar(
        select(CommercialCompanyProfile).where(
            CommercialCompanyProfile.company_code == work_order.company_code
        )
    )
    if company_profile is None:
        raise HTTPException(status_code=422, detail="Empresa emissora não cadastrada no Config Master.")

    if not preview and quote.emitted_at is None:
        quote.company_snapshot = json.dumps(
            _company_snapshot_payload(company_profile),
            ensure_ascii=False,
            sort_keys=True,
        )
        quote.emitted_at = datetime.now(UTC)
        quote.status = "emitted"
        quote_sent_option = await _workflow_option_by_code(
            db,
            kind="substatus",
            code="quote_sent",
            active_only=True,
        )
        if quote_sent_option is not None:
            await _set_work_order_substatus(
                db,
                work_order=work_order,
                code="quote_sent",
                active=True,
                user_id=user.id,
            )
        await db.commit()
        await db.refresh(quote)

    customer = await db.get(LaboratoryCustomer, work_order.customer_id) if work_order.customer_id else None
    photo_payload: list[tuple[str, str | None]] = []
    for photo in quote.photos:
        try:
            path = resolve_laboratory_storage_path(UPLOAD_ROOT, photo.document.storage_path)
        except ValueError:
            continue
        if path.exists() and photo.document.mime_type.startswith("image/"):
            photo_payload.append((str(path), photo.caption))
    company_payload = (
        json.loads(quote.company_snapshot)
        if quote.company_snapshot
        else _company_snapshot_payload(company_profile)
    )
    pdf_bytes = await asyncio.to_thread(
        quote_pdf,
        work_order,
        work_order.equipment,
        quote,
        customer,
        photo_payload,
        company_payload,
    )
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


@router.get(
    "/work-orders/{work_order_id}/documents",
    response_model=list[DocumentOutput],
)
async def list_documents(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    query = (
        select(LaboratoryDocument)
        .where(LaboratoryDocument.work_order_id == work_order_id)
        .order_by(LaboratoryDocument.created_at.desc(), LaboratoryDocument.id.desc())
    )
    return list((await db.scalars(query)).all())


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
    try:
        directory = resolve_laboratory_storage_path(
            UPLOAD_ROOT,
            Path(work_order.company_code) / work_order.number,
        )
        streamed = await persist_streamed_upload(
            file,
            directory=directory,
            max_size=MAX_UPLOAD_SIZE,
        )
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail="O arquivo excede 15 MB.") from exc
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Armazenamento de documentos indisponível. Verifique o volume /app/storage da API.",
        ) from exc
    target = streamed.path

    document = LaboratoryDocument(
        work_order_id=work_order.id,
        category=category,
        original_name=file.filename or target.name,
        storage_path=str(target),
        mime_type=streamed.mime_type,
        size_bytes=streamed.size_bytes,
        checksum_sha256=streamed.checksum_sha256,
        uploaded_by=user.id,
    )
    await commit_laboratory_document(
        db,
        document,
        root=UPLOAD_ROOT,
        stored_path=target,
    )
    return document


@router.get("/documents/{document_id}/preview")
async def preview_document(
    document_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    document = await db.get(LaboratoryDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    try:
        path = resolve_laboratory_storage_path(UPLOAD_ROOT, document.storage_path)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Caminho de armazenamento inválido.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    safe_name = quote(document.original_name)
    return FileResponse(
        path,
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
    linked_quote_photo = await db.scalar(
        select(LaboratoryQuotePhoto.id).where(LaboratoryQuotePhoto.document_id == document_id).limit(1)
    )
    if linked_quote_photo is not None:
        raise HTTPException(
            status_code=409,
            detail="Esta imagem está vinculada a uma revisão de orçamento e não pode ser excluída.",
        )
    try:
        await delete_laboratory_document_storage(db, document, root=UPLOAD_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Caminho de armazenamento inválido.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ------------------------------------------------------- material requests ---

from app.purchasing.material_models import MaterialRequest, MaterialRequestEvent
from app.purchasing.material_schemas import MaterialRequestCreate, MaterialRequestOutput
from app.purchasing.material_service import event as material_event, next_material_request_code, output_rows


@router.get("/work-orders/{work_order_id}/materials", response_model=list[MaterialRequestOutput])
async def list_material_requests_for_work_order(
    work_order_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    await _work_order_or_404(db, work_order_id)
    rows = list((await db.scalars(
        select(MaterialRequest)
        .where(MaterialRequest.work_order_id == work_order_id)
        .order_by(MaterialRequest.created_at.desc())
    )).all())
    return await output_rows(
        db,
        rows,
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


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
        **payload.model_dump(include={
            "inventory_destination", "inventory_item_id", "inventory_name", "inventory_mode",
            "inventory_serial", "inventory_category", "inventory_format_id",
        }),
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
    return (await output_rows(
        db,
        [request],
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    ))[0]
