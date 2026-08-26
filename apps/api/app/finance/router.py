from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload, validate_upload
from app.customers.models import CustomerBillingProfile
from app.finance.models import FinancialAuditEvent, FinancialEntry, FinancialTransfer
from app.laboratory.models import LaboratoryStatusHistory, LaboratoryWorkOrder
from app.notifications.service import notify_modules
from app.finance.schemas import (
    AuditOutput,
    CompanyCode,
    DateBasis,
    EntryStatus,
    EntryType,
    FinanceSummary,
    BillingChecklistItem,
    BillingReadiness,
    FinanceWorkOrderOption,
    FinancialEntryInput,
    FinancialEntryOutput,
    FinancialEntryUpdate,
    SettlementInput,
    TransferInput,
    TransferOutput,
)
from app.finance.service import build_finance_summary
from app.finance.storage import persist_attachment

router = APIRouter(prefix="/finance", dependencies=[Depends(require_module("financeiro"))])
UPLOAD_ROOT = Path(settings.storage_root) / "finance"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

CURRENT_USER_DEP = Depends(current_user)
DB_DEP = Depends(get_db)
QUERY_COMPANY_CODE = Query(default=None)
QUERY_CONSOLIDATED = Query(default=False)
QUERY_YEAR = Query(default=None, ge=2000, le=2100)
QUERY_MONTH = Query(default=None, ge=1, le=12)
QUERY_ENTRY_TYPE = Query(default=None)
QUERY_ENTRY_STATUS = Query(default=None, alias="status")
QUERY_SEARCH = Query(default=None, max_length=100)
QUERY_START_DATE = Query(default=None)
QUERY_END_DATE = Query(default=None)
QUERY_DATE_BASIS = Query(default="posting")
QUERY_OPTIONAL_INT = Query(default=None)
REQUIRED_FILE = File(...)


def _snapshot(entry: FinancialEntry) -> dict:
    fields = (
        "entry_type", "company_code", "invoice_type", "series", "nfse_number", "nfe_number",
        "counterparty_name", "description",
        "amount", "issue_date", "posting_date", "due_date", "settlement_date",
        "status", "bank_name",
        "expense_kind", "document_number", "payment_code", "notes", "attachment_name", "work_order_id",
    )
    result = {}
    for field in fields:
        value = getattr(entry, field)
        result[field] = str(value) if value is not None else None
    return result


def _audit(
    entry: FinancialEntry,
    action: str,
    description: str,
    user_id: int,
    before=None,
    after=None,
):
    return FinancialAuditEvent(
        entity_type="financial_entry", entity_id=entry.id, action=action, description=description,
        user_id=user_id, before_data=before, after_data=after,
    )


async def _entry_or_404(db: AsyncSession, entry_id: int) -> FinancialEntry:
    entry = await db.get(FinancialEntry, entry_id)
    if not entry or entry.is_deleted:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    return entry


async def _work_order_or_404(db: AsyncSession, work_order_id: int) -> LaboratoryWorkOrder:
    work_order = await db.get(LaboratoryWorkOrder, work_order_id)
    if not work_order or work_order.is_cancelled:
        raise HTTPException(status_code=404, detail="OS não encontrada ou cancelada.")
    return work_order


async def _billing_readiness(db: AsyncSession, work_order: LaboratoryWorkOrder) -> BillingReadiness:
    profile = await db.get(CustomerBillingProfile, work_order.customer_id) if work_order.customer_id else None
    items: list[BillingChecklistItem] = []

    def add(key: str, label: str, required: bool, evidence_type: str, configured_value: str | None = None):
        items.append(BillingChecklistItem(
            key=key, label=label, required=required, evidence_type=evidence_type,
            configured_value=configured_value,
        ))

    if profile:
        add("purchase_order", "PO / pedido de compra informado", profile.requires_purchase_order, "text")
        add("customer_order", "OS / pedido do cliente informado", profile.requires_customer_order, "text")
        add("measurement", "Medição informada", profile.requires_measurement, "text")
        add("service_report", "Laudo / relatório de serviço conferido", profile.requires_service_report, "boolean")
        add("portal", "Nota lançada no portal do cliente", bool(profile.portal_url), "boolean", profile.portal_url)
        add("invoice_email", "Envio para o e-mail de faturamento confirmado", bool(profile.invoice_email), "boolean", profile.invoice_email)
        add("xml_email", "Envio do XML para o destinatário correto confirmado", bool(profile.xml_email), "boolean", profile.xml_email)
    else:
        add("profile", "Cliente sem procedimento de faturamento configurado", False, "warning")

    return BillingReadiness(
        work_order_id=work_order.id,
        work_order_number=work_order.number,
        customer_id=work_order.customer_id,
        customer_name=work_order.customer_name,
        approved_value=work_order.approved_value,
        portal_url=profile.portal_url if profile else None,
        invoice_email=profile.invoice_email if profile else None,
        xml_email=profile.xml_email if profile else None,
        billing_instructions=profile.billing_instructions if profile else None,
        financial_notes=profile.financial_notes if profile else None,
        items=items,
    )


async def _validate_billing_confirmation(db: AsyncSession, work_order: LaboratoryWorkOrder, confirmation) -> dict:
    readiness = await _billing_readiness(db, work_order)
    data = confirmation.model_dump() if confirmation else {}
    missing: list[str] = []
    required = {item.key for item in readiness.items if item.required}

    checks = {
        "purchase_order": bool((data.get("purchase_order_number") or "").strip()),
        "customer_order": bool((data.get("customer_order_number") or "").strip()),
        "measurement": bool((data.get("measurement_reference") or "").strip()),
        "service_report": bool(data.get("service_report_confirmed")),
        "portal": bool(data.get("portal_submitted")),
        "invoice_email": bool(data.get("invoice_email_confirmed")),
        "xml_email": bool(data.get("xml_email_confirmed")),
    }
    label_by_key = {item.key: item.label for item in readiness.items}
    for key in required:
        if not checks.get(key, False):
            missing.append(label_by_key.get(key, key))
    if missing:
        raise HTTPException(
            status_code=422,
            detail="Faturamento bloqueado. Conclua: " + "; ".join(missing),
        )

    return {
        "status": "complete",
        "validated_at": datetime.now(UTC).isoformat(),
        "work_order_number": work_order.number,
        "customer_name": work_order.customer_name,
        "profile_snapshot": readiness.model_dump(mode="json"),
        "confirmation": data,
    }


async def _mark_work_order_invoiced(
    db: AsyncSession, work_order: LaboratoryWorkOrder, user_id: int, entry: FinancialEntry
) -> None:
    previous = work_order.status
    if previous != "invoiced":
        work_order.status = "invoiced"
        work_order.invoiced_at = datetime.now(UTC)
        work_order.version += 1
        db.add(LaboratoryStatusHistory(
            work_order_id=work_order.id,
            previous_status=previous,
            new_status="invoiced",
            note=f"Faturamento sincronizado automaticamente pelo Financeiro (lançamento #{entry.id}).",
            user_id=user_id,
        ))
        await notify_modules(
            db,
            modules={"laboratorio", "financeiro"},
            category="billing",
            severity="success",
            title=f"{work_order.number} faturada",
            message=f"Receita de R$ {entry.amount:,.2f} registrada. O status do Laboratório foi atualizado para Faturado.",
            target=f"/laboratorio?os={work_order.id}",
            entity_type="financial_entry",
            entity_id=entry.id,
            work_order_id=work_order.id,
            amount=entry.amount,
        )


@router.get("/work-orders", response_model=list[FinanceWorkOrderOption])
async def finance_work_orders(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    search: str | None = QUERY_SEARCH,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    query = select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.is_cancelled.is_(False))
    if company_code:
        query = query.where(LaboratoryWorkOrder.company_code == company_code)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(
            LaboratoryWorkOrder.number.ilike(term),
            LaboratoryWorkOrder.customer_name.ilike(term),
            LaboratoryWorkOrder.equipment_serial.ilike(term),
        ))
    rows = list((await db.scalars(query.order_by(LaboratoryWorkOrder.id.desc()).limit(150))).all())
    return [FinanceWorkOrderOption(
        id=item.id,
        number=item.number,
        company_code=item.company_code,
        customer_name=item.customer_name,
        equipment_label=item.equipment.model or item.equipment.equipment_type or item.equipment_serial or "Equipamento",
        status=item.status,
        approved_value=item.approved_value,
    ) for item in rows]


@router.get("/work-orders/{work_order_id}/billing-readiness", response_model=BillingReadiness)
async def billing_readiness(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    return await _billing_readiness(db, await _work_order_or_404(db, work_order_id))


@router.get("/summary", response_model=FinanceSummary)
async def summary(
    response: Response,
    company_code: CompanyCode | None = QUERY_COMPANY_CODE, consolidated: bool = QUERY_CONSOLIDATED,
    year: int | None = QUERY_YEAR, month: int | None = QUERY_MONTH,
    start_date: date | None = QUERY_START_DATE, end_date: date | None = QUERY_END_DATE,
    date_basis: DateBasis = QUERY_DATE_BASIS,
    _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP,
):
    response.headers["Cache-Control"] = "no-store"
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="Data final deve ser igual ou posterior à data inicial.")
    return await build_finance_summary(
        db, company_code, consolidated, year, month, start_date, end_date, date_basis
    )


@router.get("/entries", response_model=list[FinancialEntryOutput])
async def list_entries(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE, consolidated: bool = QUERY_CONSOLIDATED,
    entry_type: EntryType | None = QUERY_ENTRY_TYPE,
    entry_status: EntryStatus | None = QUERY_ENTRY_STATUS,
    year: int | None = QUERY_YEAR, month: int | None = QUERY_MONTH,
    start_date: date | None = QUERY_START_DATE, end_date: date | None = QUERY_END_DATE,
    date_basis: DateBasis = QUERY_DATE_BASIS,
    search: str | None = QUERY_SEARCH,
    _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP,
):
    query = select(FinancialEntry).where(FinancialEntry.is_deleted.is_(False))
    if company_code and not consolidated:
        query = query.where(FinancialEntry.company_code == company_code)
    if entry_type:
        query = query.where(FinancialEntry.entry_type == entry_type)
    if entry_status:
        query = query.where(FinancialEntry.status == entry_status)
    date_column = {
        "posting": FinancialEntry.posting_date,
        "issue": FinancialEntry.issue_date,
        "due": FinancialEntry.due_date,
        "settlement": FinancialEntry.settlement_date,
    }[date_basis]
    if start_date or end_date:
        if start_date and end_date and end_date < start_date:
            raise HTTPException(status_code=422, detail="Data final deve ser igual ou posterior à data inicial.")
        query = query.where(date_column.is_not(None))
        if start_date:
            query = query.where(date_column >= start_date)
        if end_date:
            query = query.where(date_column <= end_date)
    elif year:
        query = query.where(date_column.is_not(None), date_column >= date(year, month or 1, 1))
        end = date(year + 1, 1, 1) if not month or month == 12 else date(year, month + 1, 1)
        query = query.where(date_column < end)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(
            FinancialEntry.description.ilike(term), FinancialEntry.counterparty_name.ilike(term),
            FinancialEntry.series.ilike(term),
            FinancialEntry.document_number.ilike(term),
            FinancialEntry.nfse_number.ilike(term),
            FinancialEntry.nfe_number.ilike(term), FinancialEntry.bank_name.ilike(term),
        ))
    ordered = query.order_by(
        date_column.desc(),
        FinancialEntry.id.desc(),
    ).limit(5000)
    return list((await db.scalars(ordered)).all())


@router.get("/date-bounds")
async def date_bounds(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE, consolidated: bool = QUERY_CONSOLIDATED,
    date_basis: DateBasis = QUERY_DATE_BASIS,
    _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP,
):
    date_column = {
        "posting": FinancialEntry.posting_date,
        "issue": FinancialEntry.issue_date,
        "due": FinancialEntry.due_date,
        "settlement": FinancialEntry.settlement_date,
    }[date_basis]
    conditions = [FinancialEntry.is_deleted.is_(False), date_column.is_not(None)]
    if company_code and not consolidated:
        conditions.append(FinancialEntry.company_code == company_code)
    row = (await db.execute(
        select(func.min(date_column), func.max(date_column), func.count(FinancialEntry.id)).where(*conditions)
    )).one()
    return {"min_date": row[0], "max_date": row[1], "count": int(row[2] or 0), "date_basis": date_basis}


@router.get("/entries/{entry_id}", response_model=FinancialEntryOutput)
async def get_entry(entry_id: int, _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP):
    return await _entry_or_404(db, entry_id)


@router.post("/entries", response_model=FinancialEntryOutput, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: FinancialEntryInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    data = payload.model_dump(exclude={"billing_confirmation"})
    work_order_id = data.pop("work_order_id", None)
    work_order = None
    billing_compliance = None

    if payload.entry_type == "income" and work_order_id:
        work_order = await _work_order_or_404(db, work_order_id)
        if work_order.company_code != payload.company_code:
            raise HTTPException(status_code=422, detail="A OS pertence a outra empresa do grupo.")
        billing_compliance = await _validate_billing_confirmation(
            db, work_order, payload.billing_confirmation
        )
        duplicated = await db.scalar(
            select(FinancialEntry.id).where(
                FinancialEntry.work_order_id == work_order_id,
                FinancialEntry.entry_type == "income",
                FinancialEntry.is_deleted.is_(False),
            ).limit(1)
        )
        if duplicated:
            raise HTTPException(
                status_code=409,
                detail=f"A {work_order.number} já possui uma receita vinculada (lançamento #{duplicated}).",
            )

    entry = FinancialEntry(
        **data,
        work_order_id=work_order_id,
        billing_compliance=billing_compliance,
        status="pending",
        created_by=user.id,
    )
    db.add(entry)
    await db.flush()
    if work_order is not None:
        await _mark_work_order_invoiced(db, work_order, user.id, entry)
    db.add(
        _audit(
            entry,
            "created",
            f"Lançamento criado: {entry.description}",
            user.id,
            after=_snapshot(entry),
        )
    )
    await db.commit()
    await db.refresh(entry)
    return entry


@router.put("/entries/{entry_id}", response_model=FinancialEntryOutput)
async def update_entry(
    entry_id: int,
    payload: FinancialEntryUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    entry = await _entry_or_404(db, entry_id)
    before = _snapshot(entry)
    data = payload.model_dump(exclude={"billing_confirmation"})
    work_order_id = data.pop("work_order_id", None)
    work_order = None
    if payload.entry_type == "income" and work_order_id:
        work_order = await _work_order_or_404(db, work_order_id)
        if work_order.company_code != payload.company_code:
            raise HTTPException(status_code=422, detail="A OS pertence a outra empresa do grupo.")
        entry.billing_compliance = await _validate_billing_confirmation(
            db, work_order, payload.billing_confirmation
        )
    elif payload.entry_type != "income":
        entry.billing_compliance = None
    entry.work_order_id = work_order_id
    for field, value in data.items():
        setattr(entry, field, value)
    if work_order is not None:
        await _mark_work_order_invoiced(db, work_order, user.id, entry)
    db.add(
        _audit(
            entry,
            "updated",
            f"Lançamento editado: {entry.description}",
            user.id,
            before,
            _snapshot(entry),
        )
    )
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: int, user: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP):
    entry = await _entry_or_404(db, entry_id)
    before = _snapshot(entry)
    entry.is_deleted = True
    entry.deleted_at = datetime.now(UTC)
    db.add(
        _audit(
            entry,
            "deleted",
            f"Lançamento excluído: {entry.description}",
            user.id,
            before=before,
        )
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/entries/{entry_id}/settle", response_model=FinancialEntryOutput)
async def settle_entry(
    entry_id: int,
    payload: SettlementInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    entry = await _entry_or_404(db, entry_id)
    before = _snapshot(entry)
    entry.status = "received" if entry.entry_type == "income" else "paid"
    entry.settlement_date = payload.settlement_date
    db.add(
        _audit(
            entry,
            "settled",
            f"Baixa realizada: {entry.description}",
            user.id,
            before,
            _snapshot(entry),
        )
    )
    await db.commit()
    await db.refresh(entry)
    return entry


@router.post("/entries/{entry_id}/unsettle", response_model=FinancialEntryOutput)
async def unsettle_entry(entry_id: int, user: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP):
    entry = await _entry_or_404(db, entry_id)
    before = _snapshot(entry)
    entry.status = "pending"
    entry.settlement_date = None
    db.add(
        _audit(
            entry,
            "settlement_reversed",
            f"Baixa desfeita: {entry.description}",
            user.id,
            before,
            _snapshot(entry),
        )
    )
    await db.commit()
    await db.refresh(entry)
    return entry


@router.post("/entries/{entry_id}/attachment", response_model=FinancialEntryOutput)
async def upload_attachment(
    entry_id: int,
    file: UploadFile = REQUIRED_FILE,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    entry = await _entry_or_404(db, entry_id)
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="O arquivo excede o limite de 10 MB.")
    try:
        detected = validate_upload(content, file.filename, file.content_type)
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    previous_path = Path(entry.attachment_path) if entry.attachment_path else None
    try:
        target = persist_attachment(
            UPLOAD_ROOT,
            company_code=entry.company_code,
            entry_id=entry.id,
            extension=detected.extension,
            content=content,
        )
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="Armazenamento de anexos indisponível. Verifique o volume /app/storage da API.",
        ) from exc

    before = _snapshot(entry)
    entry.attachment_name, entry.attachment_path, entry.attachment_mime = (
        file.filename or target.name,
        str(target),
        detected.mime_type,
    )
    db.add(
        _audit(
            entry,
            "attachment_added",
            f"Anexo incluído: {file.filename}",
            user.id,
            before,
            _snapshot(entry),
        )
    )
    try:
        await db.commit()
        await db.refresh(entry)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    if previous_path and previous_path != target:
        try:
            previous_path.unlink(missing_ok=True)
        except OSError:
            # A troca já foi confirmada no banco; falha de limpeza do arquivo
            # antigo não deve invalidar o anexo novo.
            pass
    return entry


@router.get("/entries/{entry_id}/attachment")
async def download_attachment(entry_id: int, _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP):
    entry = await _entry_or_404(db, entry_id)
    if not entry.attachment_path or not Path(entry.attachment_path).is_file():
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    return FileResponse(
        entry.attachment_path,
        media_type=entry.attachment_mime,
        filename=entry.attachment_name,
    )


@router.get("/entries/{entry_id}/attachment/preview")
async def preview_attachment(entry_id: int, _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP):
    entry = await _entry_or_404(db, entry_id)
    if not entry.attachment_path or not Path(entry.attachment_path).is_file():
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    safe_name = quote(entry.attachment_name or "anexo")
    return FileResponse(
        entry.attachment_path,
        media_type=entry.attachment_mime or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{safe_name}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/audit", response_model=list[AuditOutput])
async def list_audit(
    year: int | None = QUERY_OPTIONAL_INT, month: int | None = QUERY_OPTIONAL_INT,
    start_date: date | None = QUERY_START_DATE, end_date: date | None = QUERY_END_DATE,
    _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP,
):
    query = select(FinancialAuditEvent, User.name).join(
        User,
        User.id == FinancialAuditEvent.user_id,
    )
    if start_date or end_date:
        if start_date:
            query = query.where(FinancialAuditEvent.created_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=UTC))
        if end_date:
            query = query.where(FinancialAuditEvent.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC))
    elif year:
        start = datetime(year, month or 1, 1, tzinfo=UTC)
        if not month or month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=UTC)
        else:
            end = datetime(year, month + 1, 1, tzinfo=UTC)
        query = query.where(
            FinancialAuditEvent.created_at >= start,
            FinancialAuditEvent.created_at < end,
        )
    ordered = query.order_by(FinancialAuditEvent.created_at.desc()).limit(500)
    rows = (await db.execute(ordered)).all()
    return [AuditOutput(
        id=e.id, entity_type=e.entity_type, entity_id=e.entity_id, action=e.action,
        description=e.description, user_id=e.user_id, user_name=name,
        before_data=e.before_data, after_data=e.after_data, created_at=e.created_at,
    ) for e, name in rows]


@router.post("/transfers", response_model=TransferOutput, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    payload: TransferInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    transfer = FinancialTransfer(**payload.model_dump(), created_by=user.id)
    db.add(transfer)
    await db.flush()
    db.add(
        FinancialAuditEvent(
            entity_type="financial_transfer",
            entity_id=transfer.id,
            action="created",
            description=f"Remanejamento registrado: {transfer.reason}",
            user_id=user.id,
        )
    )
    await db.commit()
    await db.refresh(transfer)
    return transfer
