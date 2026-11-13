from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload
from app.core.upload_stream import UploadTooLarge, persist_streamed_upload
from app.customers.models import CustomerBillingProfile
from app.finance.alerts import finance_alert_fingerprint
from app.finance.idempotency import finance_request_fingerprint
from app.finance.installment_edit import (
    INDIVIDUAL_FIELDS as GROUPED_INSTALLMENT_INDIVIDUAL_FIELDS,
    PROTECTED_FIELDS as GROUPED_INSTALLMENT_PROTECTED_FIELDS,
    SHARED_FIELDS as GROUPED_INSTALLMENT_SHARED_FIELDS,
    apply_values as apply_grouped_values,
    changed_fields as grouped_changed_fields,
    total_from_installments,
    values_for as grouped_values_for,
)
from app.finance.models import (
    FinancialAccount,
    FinancialAlertAcknowledgment,
    FinancialAuditEvent,
    FinancialEntry,
    FinancialObligation,
    FinancialPeriodClosure,
    FinancialTransfer,
)
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
    WorkOrderReceivablesOutput,
    FinancialEntryInput,
    FinancialEntryOutput,
    FinancialEntryPage,
    FinancialEntryUpdate,
    FinancialAlertAcknowledgmentInput,
    FinancialAlertAcknowledgmentOutput,
    FinancialObligationInput,
    FinancialScheduleUpdate,
    FinancialObligationOutput,
    FinancialPeriodAction,
    FinancialPeriodClosureOutput,
    SettlementInput,
    TransferInput,
    TransferOutput,
)
from app.finance.reporting import (
    company_report_label,
    finance_report_filename,
    generate_finance_pdf,
    generate_finance_xlsx,
)
from app.finance.service import build_finance_summary
from app.finance.receivables import summarize_receivables

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
QUERY_PAGE = Query(default=1, ge=1)
QUERY_PAGE_SIZE = Query(default=50, ge=10, le=200)
QUERY_OVERDUE = Query(default=False)
REQUIRED_FILE = File(...)
IDEMPOTENCY_KEY_HEADER = Header(default=None, alias="Idempotency-Key", max_length=128)


def _snapshot(entry: FinancialEntry) -> dict:
    fields = (
        "obligation_id", "installment_number",
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


async def _validate_entry_account_company(
    db: AsyncSession, payload: FinancialEntryInput | FinancialEntryUpdate
) -> None:
    if payload.account_id is None:
        return

    account = await db.get(FinancialAccount, payload.account_id)
    if not account:
        raise HTTPException(status_code=422, detail="Conta financeira não encontrada.")
    if account.company_code != payload.company_code:
        raise HTTPException(
            status_code=422,
            detail="A conta financeira pertence a outra empresa do grupo.",
        )


async def _validate_obligation_account_company(
    db: AsyncSession, payload: FinancialObligationInput
) -> None:
    if payload.account_id is None:
        return

    account = await db.get(FinancialAccount, payload.account_id)
    if not account:
        raise HTTPException(status_code=422, detail="Conta financeira não encontrada.")
    if account.company_code != payload.company_code:
        raise HTTPException(
            status_code=422,
            detail="A conta financeira pertence a outra empresa do grupo.",
        )


def _require_finance_manager(user: User) -> None:
    if user.role.strip().lower() not in {"gestao", "super_admin"}:
        raise HTTPException(
            status_code=403,
            detail="Somente o perfil Gestão pode administrar o fechamento financeiro.",
        )


async def _assert_period_open(db: AsyncSession, company_code: str, posting_date: date) -> None:
    closure = await db.scalar(
        select(FinancialPeriodClosure).where(
            FinancialPeriodClosure.company_code == company_code,
            FinancialPeriodClosure.year == posting_date.year,
            FinancialPeriodClosure.month == posting_date.month,
            FinancialPeriodClosure.is_closed.is_(True),
        )
    )
    if closure:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A competência {posting_date.month:02d}/{posting_date.year} está fechada "
                "para esta empresa. Reabra o período antes de alterar movimentos."
            ),
        )


async def _obligation_output(
    db: AsyncSession,
    obligation: FinancialObligation,
) -> FinancialObligationOutput:
    installments = list(
        (
            await db.scalars(
                select(FinancialEntry)
                .where(
                    FinancialEntry.obligation_id == obligation.id,
                    FinancialEntry.is_deleted.is_(False),
                )
                .order_by(FinancialEntry.installment_number.asc())
            )
        ).all()
    )
    return FinancialObligationOutput(
        id=obligation.id,
        entry_type=obligation.entry_type,
        company_code=obligation.company_code,
        nfse_number=obligation.nfse_number,
        nfe_number=obligation.nfe_number,
        document_number=obligation.document_number,
        counterparty_name=obligation.counterparty_name,
        description=obligation.description,
        total_amount=obligation.total_amount,
        installment_count=obligation.installment_count,
        work_order_id=obligation.work_order_id,
        created_at=obligation.created_at,
        installments=[
            FinancialEntryOutput.model_validate(item)
            for item in installments
        ],
    )


def _block_grouped_entry_delete(entry: FinancialEntry) -> None:
    if entry.obligation_id is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Parcela vinculada a uma obrigação financeira não pode ser "
                "excluída individualmente."
            ),
        )


def _validate_grouped_installment_update(
    entry: FinancialEntry,
    payload: FinancialEntryUpdate,
) -> None:
    protected_changes = grouped_changed_fields(
        entry,
        payload,
        GROUPED_INSTALLMENT_PROTECTED_FIELDS,
    )
    if protected_changes:
        raise HTTPException(
            status_code=409,
            detail=(
                "Empresa, tipo do lançamento e vínculo da O.S. permanecem protegidos "
                "nas parcelas de uma obrigação financeira."
            ),
        )


async def _update_grouped_installment(
    db: AsyncSession,
    entry: FinancialEntry,
    payload: FinancialEntryUpdate,
    user: User,
) -> None:
    _validate_grouped_installment_update(entry, payload)

    await _assert_period_open(db, entry.company_code, entry.posting_date)
    if payload.posting_date != entry.posting_date:
        await _assert_period_open(db, entry.company_code, payload.posting_date)

    obligation = await db.get(FinancialObligation, entry.obligation_id)
    if obligation is None:
        raise HTTPException(
            status_code=409,
            detail="Obrigação financeira vinculada à parcela não foi encontrada.",
        )

    siblings = list(
        (
            await db.scalars(
                select(FinancialEntry)
                .where(
                    FinancialEntry.obligation_id == entry.obligation_id,
                    FinancialEntry.is_deleted.is_(False),
                )
                .order_by(FinancialEntry.installment_number.asc())
            )
        ).all()
    )
    if not any(item.id == entry.id for item in siblings):
        siblings.append(entry)

    shared_values = grouped_values_for(
        payload,
        GROUPED_INSTALLMENT_SHARED_FIELDS,
    )
    individual_values = grouped_values_for(
        payload,
        GROUPED_INSTALLMENT_INDIVIDUAL_FIELDS,
    )

    for sibling in siblings:
        sibling_before = _snapshot(sibling)
        apply_grouped_values(sibling, shared_values)
        if sibling.id == entry.id:
            apply_grouped_values(sibling, individual_values)
        sibling_after = _snapshot(sibling)

        if sibling_after != sibling_before:
            db.add(
                _audit(
                    sibling,
                    "updated",
                    (
                        f"Parcela {sibling.installment_number} atualizada pela edição "
                        f"da obrigação financeira #{entry.obligation_id}"
                    ),
                    user.id,
                    sibling_before,
                    sibling_after,
                )
            )

    for field, value in shared_values.items():
        if hasattr(obligation, field):
            setattr(obligation, field, value)

    obligation.total_amount = total_from_installments(siblings)
    db.add(obligation)


async def _work_order_or_404(db: AsyncSession, work_order_id: int) -> LaboratoryWorkOrder:
    work_order = await db.get(LaboratoryWorkOrder, work_order_id)
    if not work_order or work_order.is_cancelled or work_order.is_inactive:
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


@router.get("/closures", response_model=list[FinancialPeriodClosureOutput])
async def list_period_closures(
    company_code: CompanyCode = Query(...),
    year: int = Query(..., ge=2000, le=2100),
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    return list((await db.scalars(
        select(FinancialPeriodClosure).where(
            FinancialPeriodClosure.company_code == company_code,
            FinancialPeriodClosure.year == year,
        ).order_by(FinancialPeriodClosure.month)
    )).all())


@router.post("/closures/close", response_model=FinancialPeriodClosureOutput)
async def close_financial_period(
    payload: FinancialPeriodAction,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_finance_manager(user)
    existing = await db.scalar(select(FinancialPeriodClosure).where(
        FinancialPeriodClosure.company_code == payload.company_code,
        FinancialPeriodClosure.year == payload.year,
        FinancialPeriodClosure.month == payload.month,
    ))
    if existing and existing.is_closed:
        raise HTTPException(status_code=409, detail="Esta competência já está fechada.")
    summary_data = await build_finance_summary(
        db, payload.company_code, False, payload.year, payload.month, None, None, "posting"
    )
    snapshot = {
        "period_income": summary_data.period_income, "period_expense": summary_data.period_expense,
        "period_result": summary_data.period_result, "settled_income": summary_data.settled_income,
        "settled_expense": summary_data.settled_expense, "pending_income": summary_data.pending_income,
        "pending_expense": summary_data.pending_expense, "overdue_income": summary_data.overdue_income,
        "overdue_expense": summary_data.overdue_expense, "period_entry_count": summary_data.period_entry_count,
    }
    now = datetime.now(UTC)
    if existing:
        closure = existing
        closure.is_closed = True
        closure.snapshot_data = snapshot
        closure.closed_by = user.id
        closure.closed_at = now
        closure.reopened_by = None
        closure.reopened_at = None
    else:
        closure = FinancialPeriodClosure(
            company_code=payload.company_code, year=payload.year, month=payload.month,
            is_closed=True, snapshot_data=snapshot, closed_by=user.id, closed_at=now,
        )
        db.add(closure)
        await db.flush()
    db.add(FinancialAuditEvent(
        entity_type="financial_period_closure", entity_id=closure.id, action="closed",
        description=f"Competência {payload.month:02d}/{payload.year} fechada", user_id=user.id,
        after_data=snapshot,
    ))
    await db.commit()
    await db.refresh(closure)
    return closure


@router.post("/closures/reopen", response_model=FinancialPeriodClosureOutput)
async def reopen_financial_period(
    payload: FinancialPeriodAction,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    _require_finance_manager(user)
    closure = await db.scalar(select(FinancialPeriodClosure).where(
        FinancialPeriodClosure.company_code == payload.company_code,
        FinancialPeriodClosure.year == payload.year,
        FinancialPeriodClosure.month == payload.month,
    ))
    if not closure or not closure.is_closed:
        raise HTTPException(status_code=409, detail="Esta competência não está fechada.")
    closure.is_closed = False
    closure.reopened_by = user.id
    closure.reopened_at = datetime.now(UTC)
    db.add(FinancialAuditEvent(
        entity_type="financial_period_closure", entity_id=closure.id, action="reopened",
        description=f"Competência {payload.month:02d}/{payload.year} reaberta", user_id=user.id,
        before_data=closure.snapshot_data,
    ))
    await db.commit()
    await db.refresh(closure)
    return closure


@router.post("/alerts/{entry_id}/acknowledge", response_model=FinancialAlertAcknowledgmentOutput)
async def acknowledge_finance_alert(
    entry_id: int,
    payload: FinancialAlertAcknowledgmentInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    entry = await _entry_or_404(db, entry_id)
    if entry.status != "pending":
        raise HTTPException(status_code=409, detail="Somente títulos pendentes possuem alerta ativo.")
    today = date.today()
    if entry.due_date > today + timedelta(days=7):
        raise HTTPException(status_code=422, detail="O título ainda não está na janela de alerta.")
    fingerprint = finance_alert_fingerprint(
        due_date=entry.due_date, amount=entry.amount, status=entry.status
    )
    existing = await db.scalar(select(FinancialAlertAcknowledgment).where(
        FinancialAlertAcknowledgment.entry_id == entry.id,
        FinancialAlertAcknowledgment.fingerprint == fingerprint,
    ))
    if existing:
        return existing
    ack = FinancialAlertAcknowledgment(
        entry_id=entry.id, fingerprint=fingerprint, note=payload.note, acknowledged_by=user.id
    )
    db.add(ack)
    await db.flush()
    db.add(FinancialAuditEvent(
        entity_type="financial_entry", entity_id=entry.id, action="alert_acknowledged",
        description=f"Alerta financeiro reconhecido: {entry.description}", user_id=user.id,
        after_data={"fingerprint": fingerprint, "note": payload.note},
    ))
    await db.commit()
    await db.refresh(ack)
    return ack


@router.get("/work-orders", response_model=list[FinanceWorkOrderOption])
async def finance_work_orders(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    search: str | None = QUERY_SEARCH,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    query = select(LaboratoryWorkOrder).where(
        LaboratoryWorkOrder.is_cancelled.is_(False),
        LaboratoryWorkOrder.is_inactive.is_(False),
    )
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


@router.get("/work-orders/{work_order_id}/receivables", response_model=WorkOrderReceivablesOutput)
async def work_order_receivables(
    work_order_id: int,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    """Busca todas as receitas da OS, mesmo em competências/vencimentos distintos.

    Valores são apurados exclusivamente a partir dos títulos ativos da própria OS,
    para não confundir a soma do contrato com o saldo efetivamente recebido.
    """
    order = await db.get(LaboratoryWorkOrder, work_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="OS não encontrada.")
    installments = list((await db.scalars(
        select(FinancialEntry).where(
            FinancialEntry.work_order_id == order.id,
            FinancialEntry.entry_type == "income",
            FinancialEntry.is_deleted.is_(False),
            FinancialEntry.status.in_(("pending", "received")),
        ).order_by(FinancialEntry.due_date, FinancialEntry.installment_number, FinancialEntry.id)
    )).all())
    approved = order.approved_value
    amounts = summarize_receivables(installments, approved)
    return WorkOrderReceivablesOutput(
        work_order_id=order.id,
        work_order_number=order.number,
        company_code=order.company_code,
        customer_name=order.customer_name,
        approved_value=approved,
        **amounts,
        installments=[FinancialEntryOutput.model_validate(item) for item in installments],
    )


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


async def _report_entries(
    db: AsyncSession,
    company_code: CompanyCode | None,
    consolidated: bool,
    year: int | None,
    month: int | None,
    start_date: date | None,
    end_date: date | None,
    date_basis: DateBasis,
) -> list[FinancialEntry]:
    conditions = [FinancialEntry.is_deleted.is_(False)]
    if company_code and not consolidated:
        conditions.append(FinancialEntry.company_code == company_code)

    date_column = {
        "posting": FinancialEntry.posting_date,
        "issue": FinancialEntry.issue_date,
        "due": FinancialEntry.due_date,
        "settlement": FinancialEntry.settlement_date,
    }[date_basis]

    if start_date or end_date:
        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="Data final deve ser igual ou posterior à data inicial.",
            )
        conditions.append(date_column.is_not(None))
        if start_date:
            conditions.append(date_column >= start_date)
        if end_date:
            conditions.append(date_column <= end_date)
    elif year:
        conditions.extend([
            date_column.is_not(None),
            date_column >= date(year, month or 1, 1),
        ])
        report_end = (
            date(year + 1, 1, 1)
            if not month or month == 12
            else date(year, month + 1, 1)
        )
        conditions.append(date_column < report_end)

    return list(
        (
            await db.scalars(
                select(FinancialEntry)
                .where(*conditions)
                .order_by(date_column.asc(), FinancialEntry.id.asc())
            )
        ).all()
    )


async def _build_report_payload(
    db: AsyncSession,
    company_code: CompanyCode | None,
    consolidated: bool,
    year: int | None,
    month: int | None,
    start_date: date | None,
    end_date: date | None,
    date_basis: DateBasis,
):
    summary_data = await build_finance_summary(
        db,
        company_code,
        consolidated,
        year,
        month,
        start_date,
        end_date,
        date_basis,
    )
    entries = await _report_entries(
        db,
        company_code,
        consolidated,
        year,
        month,
        start_date,
        end_date,
        date_basis,
    )
    return summary_data, entries


@router.get("/reports/pdf")
async def finance_report_pdf(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    consolidated: bool = QUERY_CONSOLIDATED,
    year: int | None = QUERY_YEAR,
    month: int | None = QUERY_MONTH,
    start_date: date | None = QUERY_START_DATE,
    end_date: date | None = QUERY_END_DATE,
    date_basis: DateBasis = QUERY_DATE_BASIS,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    summary_data, entries = await _build_report_payload(
        db,
        company_code,
        consolidated,
        year,
        month,
        start_date,
        end_date,
        date_basis,
    )
    content = generate_finance_pdf(
        summary_data,
        entries,
        company_label=company_report_label(company_code, consolidated),
    )
    filename = finance_report_filename(
        "pdf",
        company_code,
        consolidated,
        summary_data.period_end,
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/reports/xlsx")
async def finance_report_xlsx(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE,
    consolidated: bool = QUERY_CONSOLIDATED,
    year: int | None = QUERY_YEAR,
    month: int | None = QUERY_MONTH,
    start_date: date | None = QUERY_START_DATE,
    end_date: date | None = QUERY_END_DATE,
    date_basis: DateBasis = QUERY_DATE_BASIS,
    _: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    summary_data, entries = await _build_report_payload(
        db,
        company_code,
        consolidated,
        year,
        month,
        start_date,
        end_date,
        date_basis,
    )
    content = generate_finance_xlsx(
        summary_data,
        entries,
        company_label=company_report_label(company_code, consolidated),
    )
    filename = finance_report_filename(
        "xlsx",
        company_code,
        consolidated,
        summary_data.period_end,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/entries", response_model=FinancialEntryPage)
async def list_entries(
    company_code: CompanyCode | None = QUERY_COMPANY_CODE, consolidated: bool = QUERY_CONSOLIDATED,
    entry_type: EntryType | None = QUERY_ENTRY_TYPE,
    entry_status: EntryStatus | None = QUERY_ENTRY_STATUS,
    overdue: bool = QUERY_OVERDUE,
    year: int | None = QUERY_YEAR, month: int | None = QUERY_MONTH,
    start_date: date | None = QUERY_START_DATE, end_date: date | None = QUERY_END_DATE,
    date_basis: DateBasis = QUERY_DATE_BASIS,
    search: str | None = QUERY_SEARCH,
    page: int = QUERY_PAGE, page_size: int = QUERY_PAGE_SIZE,
    _: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP,
):
    if overdue and entry_status and entry_status != "pending":
        raise HTTPException(status_code=422, detail="Filtro de atraso só pode ser combinado com status pendente.")

    conditions = [FinancialEntry.is_deleted.is_(False)]
    if company_code and not consolidated:
        conditions.append(FinancialEntry.company_code == company_code)
    if entry_type:
        conditions.append(FinancialEntry.entry_type == entry_type)
    if entry_status:
        conditions.append(FinancialEntry.status == entry_status)
    if overdue:
        conditions.extend([FinancialEntry.status == "pending", FinancialEntry.due_date < date.today()])

    date_column = {
        "posting": FinancialEntry.posting_date,
        "issue": FinancialEntry.issue_date,
        "due": FinancialEntry.due_date,
        "settlement": FinancialEntry.settlement_date,
    }[date_basis]
    if start_date or end_date:
        if start_date and end_date and end_date < start_date:
            raise HTTPException(status_code=422, detail="Data final deve ser igual ou posterior à data inicial.")
        conditions.append(date_column.is_not(None))
        if start_date:
            conditions.append(date_column >= start_date)
        if end_date:
            conditions.append(date_column <= end_date)
    elif year:
        conditions.extend([date_column.is_not(None), date_column >= date(year, month or 1, 1)])
        end = date(year + 1, 1, 1) if not month or month == 12 else date(year, month + 1, 1)
        conditions.append(date_column < end)

    if search:
        term = f"%{search.strip()}%"
        work_order_ids = select(LaboratoryWorkOrder.id).where(LaboratoryWorkOrder.number.ilike(term))
        conditions.append(or_(
            FinancialEntry.description.ilike(term), FinancialEntry.counterparty_name.ilike(term),
            FinancialEntry.series.ilike(term),
            FinancialEntry.document_number.ilike(term),
            FinancialEntry.nfse_number.ilike(term),
            FinancialEntry.nfe_number.ilike(term), FinancialEntry.bank_name.ilike(term),
            FinancialEntry.work_order_id.in_(work_order_ids),
        ))

    total = int(await db.scalar(
        select(func.count()).select_from(FinancialEntry).where(*conditions)
    ) or 0)
    pages = (total + page_size - 1) // page_size if total else 0
    resolved_page = min(page, max(pages, 1))
    offset = (resolved_page - 1) * page_size
    ordered = (
        select(FinancialEntry)
        .where(*conditions)
        .order_by(date_column.desc(), FinancialEntry.id.desc())
        .limit(page_size)
        .offset(offset)
    )
    items = list((await db.scalars(ordered)).all())
    return FinancialEntryPage(
        items=items, page=resolved_page, page_size=page_size, total=total, pages=pages
    )


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


@router.post(
    "/obligations",
    response_model=FinancialObligationOutput,
    status_code=status.HTTP_201_CREATED,
)
async def create_obligation(
    payload: FinancialObligationInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
    idempotency_key: str | None = IDEMPOTENCY_KEY_HEADER,
):
    normalized_key = idempotency_key.strip() if idempotency_key else None
    fingerprint = finance_request_fingerprint(payload) if normalized_key else None

    if normalized_key:
        existing = await db.scalar(
            select(FinancialObligation)
            .where(FinancialObligation.idempotency_key == normalized_key)
            .limit(1)
        )
        if existing:
            if existing.idempotency_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="A mesma chave de envio foi reutilizada com dados diferentes.",
                )
            return await _obligation_output(db, existing)

    await _validate_obligation_account_company(db, payload)
    await _assert_period_open(db, payload.company_code, payload.posting_date)

    work_order = None
    billing_compliance = None
    if payload.entry_type == "income" and payload.work_order_id:
        work_order = await _work_order_or_404(db, payload.work_order_id)
        if work_order.company_code != payload.company_code:
            raise HTTPException(
                status_code=422,
                detail="A OS pertence a outra empresa do grupo.",
            )
        billing_compliance = await _validate_billing_confirmation(
            db,
            work_order,
            payload.billing_confirmation,
        )

    obligation = FinancialObligation(
        entry_type=payload.entry_type,
        company_code=payload.company_code,
        invoice_type=payload.invoice_type,
        series=payload.series,
        nfse_number=payload.nfse_number,
        nfe_number=payload.nfe_number,
        counterparty_name=payload.counterparty_name,
        description=payload.description,
        total_amount=payload.total_amount,
        installment_count=len(payload.installments),
        issue_date=payload.issue_date,
        posting_date=payload.posting_date,
        bank_name=payload.bank_name,
        expense_kind=payload.expense_kind,
        account_id=payload.account_id,
        category_id=payload.category_id,
        document_number=payload.document_number,
        notes=payload.notes,
        work_order_id=payload.work_order_id,
        idempotency_key=normalized_key,
        idempotency_fingerprint=fingerprint,
        created_by=user.id,
    )
    db.add(obligation)

    try:
        await db.flush()

        created_entries: list[FinancialEntry] = []
        for installment in sorted(
            payload.installments,
            key=lambda item: item.installment_number,
        ):
            entry = FinancialEntry(
                obligation_id=obligation.id,
                installment_number=installment.installment_number,
                entry_type=payload.entry_type,
                company_code=payload.company_code,
                invoice_type=payload.invoice_type,
                series=payload.series,
                nfse_number=payload.nfse_number,
                nfe_number=payload.nfe_number,
                counterparty_name=payload.counterparty_name,
                description=payload.description,
                amount=installment.amount,
                issue_date=payload.issue_date,
                posting_date=payload.posting_date,
                due_date=installment.due_date,
                status="pending",
                bank_name=payload.bank_name,
                expense_kind=payload.expense_kind,
                account_id=payload.account_id,
                category_id=payload.category_id,
                        document_number=payload.document_number,
                payment_code=installment.payment_code,
                notes=installment.notes or payload.notes,
                billing_compliance=billing_compliance,
                work_order_id=payload.work_order_id,
                created_by=user.id,
            )
            db.add(entry)
            created_entries.append(entry)

        await db.flush()
    except IntegrityError:
        await db.rollback()
        if normalized_key:
            existing = await db.scalar(
                select(FinancialObligation)
                .where(FinancialObligation.idempotency_key == normalized_key)
                .limit(1)
            )
            if existing:
                if existing.idempotency_fingerprint != fingerprint:
                    raise HTTPException(
                        status_code=409,
                        detail="A mesma chave de envio foi reutilizada com dados diferentes.",
                    )
                return await _obligation_output(db, existing)
        raise

    for entry in created_entries:
        db.add(
            _audit(
                entry,
                "created",
                (
                    f"Parcela {entry.installment_number}/"
                    f"{obligation.installment_count} criada: {entry.description}"
                ),
                user.id,
                after=_snapshot(entry),
            )
        )

    db.add(
        FinancialAuditEvent(
            entity_type="financial_obligation",
            entity_id=obligation.id,
            action="created",
            description=(
                f"Obrigação criada com {obligation.installment_count} parcela(s): "
                f"{obligation.description}"
            ),
            user_id=user.id,
            after_data={
                "company_code": obligation.company_code,
                "entry_type": obligation.entry_type,
                "total_amount": str(obligation.total_amount),
                "installment_count": obligation.installment_count,
                "nfse_number": obligation.nfse_number,
                "nfe_number": obligation.nfe_number,
                "document_number": obligation.document_number,
                "work_order_id": obligation.work_order_id,
            },
        )
    )

    if work_order is not None and created_entries:
        await _mark_work_order_invoiced(
            db,
            work_order,
            user.id,
            created_entries[0],
        )

    await db.commit()
    await db.refresh(obligation)
    return await _obligation_output(db, obligation)


async def _editable_income_obligation(db: AsyncSession, obligation_id: int):
    obligation = await db.scalar(select(FinancialObligation).where(
        FinancialObligation.id == obligation_id,
    ).with_for_update())
    if obligation is None or obligation.entry_type != "income":
        raise HTTPException(status_code=404, detail="Parcelamento de receita não encontrado.")
    entries = list((await db.scalars(select(FinancialEntry).where(
        FinancialEntry.obligation_id == obligation_id,
        FinancialEntry.is_deleted.is_(False),
    ).order_by(FinancialEntry.installment_number.asc()).with_for_update())).all())
    if not entries:
        raise HTTPException(status_code=409, detail="Parcelamento sem parcelas ativas.")
    if any(item.status != "pending" or item.settlement_date is not None for item in entries):
        raise HTTPException(status_code=409, detail="Reorganização ou exclusão bloqueada: existe parcela baixada. Estorne primeiro, se permitido.")
    await _assert_period_open(db, obligation.company_code, obligation.posting_date)
    for item in entries:
        await _assert_period_open(db, item.company_code, item.posting_date)
    return obligation, entries


@router.get("/obligations/{obligation_id}", response_model=FinancialObligationOutput)
async def get_obligation(obligation_id: int, user: User = CURRENT_USER_DEP, db: AsyncSession = DB_DEP):
    obligation = await db.get(FinancialObligation, obligation_id)
    if obligation is None:
        raise HTTPException(status_code=404, detail="Parcelamento não encontrado.")
    return await _obligation_output(db, obligation)


@router.put("/obligations/{obligation_id}/schedule", response_model=FinancialObligationOutput)
async def update_obligation_schedule(
    obligation_id: int,
    payload: FinancialScheduleUpdate,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    obligation, entries = await _editable_income_obligation(db, obligation_id)
    # Retirar a numeração temporariamente evita colisão da constraint UNIQUE quando
    # uma parcela é excluída e outra passa a ocupar seu número anterior.
    before = [{"id": item.id, "number": item.installment_number, "amount": str(item.amount),
               "due_date": str(item.due_date)} for item in entries]
    for item in entries:
        item.installment_number = None
    await db.flush()
    ordered = sorted(payload.installments, key=lambda item: item.installment_number)
    original_by_id = {item.id: item for item in entries}
    used_ids: set[int] = set()
    for spec in ordered:
        if spec.entry_id is not None:
            if spec.entry_id not in original_by_id or spec.entry_id in used_ids:
                raise HTTPException(status_code=422, detail="Identificador de parcela inválido ou repetido.")
            used_ids.add(spec.entry_id)
            item = original_by_id[spec.entry_id]
            old = _snapshot(item)
            item.installment_number = spec.installment_number
            item.amount = spec.amount
            item.due_date = spec.due_date
            item.payment_code = spec.payment_code
            item.notes = spec.notes
            db.add(_audit(item, "updated", f"Parcela {spec.installment_number} reorganizada", user.id, old, _snapshot(item)))
        else:
            item = FinancialEntry(
                obligation_id=obligation.id,
                installment_number=spec.installment_number,
                entry_type=obligation.entry_type,
                company_code=obligation.company_code,
                invoice_type=obligation.invoice_type,
                series=obligation.series,
                nfse_number=obligation.nfse_number,
                nfe_number=obligation.nfe_number,
                counterparty_name=obligation.counterparty_name,
                description=obligation.description,
                amount=spec.amount, issue_date=obligation.issue_date,
                posting_date=obligation.posting_date, due_date=spec.due_date,
                status="pending", bank_name=obligation.bank_name,
                expense_kind=obligation.expense_kind, account_id=obligation.account_id,
                category_id=obligation.category_id, document_number=obligation.document_number,
                payment_code=spec.payment_code, notes=spec.notes,
                billing_compliance=entries[0].billing_compliance,
                work_order_id=obligation.work_order_id, created_by=user.id,
            )
            db.add(item)
            await db.flush()
            db.add(_audit(item, "created", "Parcela adicionada ao parcelamento", user.id, after=_snapshot(item)))
    for removed in (item for item in entries if item.id not in used_ids):
        previous = _snapshot(removed)
        removed.is_deleted = True
        removed.deleted_at = datetime.now(UTC)
        db.add(_audit(removed, "deleted", "Parcela removida do parcelamento", user.id, before=previous))
    obligation.installment_count = len(ordered)
    obligation.total_amount = payload.total_amount
    db.add(FinancialAuditEvent(
        entity_type="financial_obligation", entity_id=obligation.id, action="updated",
        description="Cronograma do parcelamento de receita alterado",
        user_id=user.id, before_data={"installments": before},
        after_data={"total_amount": str(payload.total_amount), "installment_count": len(ordered)},
    ))
    await db.commit()
    return await _obligation_output(db, obligation)


@router.delete("/obligations/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income_obligation(
    obligation_id: int,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
):
    obligation, entries = await _editable_income_obligation(db, obligation_id)
    for item in entries:
        before = _snapshot(item)
        item.is_deleted = True
        item.deleted_at = datetime.now(UTC)
        item.installment_number = None
        db.add(_audit(item, "deleted", "Exclusão do parcelamento da receita", user.id, before=before))
    db.add(FinancialAuditEvent(
        entity_type="financial_obligation", entity_id=obligation.id,
        action="deleted", description="Parcelamento de receita excluído (histórico preservado)",
        user_id=user.id, before_data={"amount": str(obligation.total_amount), "active_count": len(entries)},
    ))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/entries", response_model=FinancialEntryOutput, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: FinancialEntryInput,
    user: User = CURRENT_USER_DEP,
    db: AsyncSession = DB_DEP,
    idempotency_key: str | None = IDEMPOTENCY_KEY_HEADER,
):
    normalized_key = idempotency_key.strip() if idempotency_key else None
    fingerprint = finance_request_fingerprint(payload) if normalized_key else None

    if normalized_key:
        existing = await db.scalar(
            select(FinancialEntry).where(FinancialEntry.idempotency_key == normalized_key).limit(1)
        )
        if existing:
            if existing.idempotency_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="A mesma chave de envio foi reutilizada com dados diferentes.",
                )
            return existing

    await _validate_entry_account_company(db, payload)
    await _assert_period_open(db, payload.company_code, payload.posting_date)

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

    entry = FinancialEntry(
        **data,
        work_order_id=work_order_id,
        billing_compliance=billing_compliance,
        idempotency_key=normalized_key,
        idempotency_fingerprint=fingerprint,
        status="pending",
        created_by=user.id,
    )
    db.add(entry)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        if normalized_key:
            existing = await db.scalar(
                select(FinancialEntry).where(FinancialEntry.idempotency_key == normalized_key).limit(1)
            )
            if existing:
                if existing.idempotency_fingerprint != fingerprint:
                    raise HTTPException(
                        status_code=409,
                        detail="A mesma chave de envio foi reutilizada com dados diferentes.",
                    )
                return existing
        raise
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
    await _validate_entry_account_company(db, payload)

    if entry.obligation_id is not None:
        await _update_grouped_installment(db, entry, payload, user)
    else:
        before = _snapshot(entry)
        await _assert_period_open(db, entry.company_code, entry.posting_date)
        await _assert_period_open(db, payload.company_code, payload.posting_date)
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
    _block_grouped_entry_delete(entry)
    await _assert_period_open(db, entry.company_code, entry.posting_date)
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
    await _assert_period_open(db, entry.company_code, entry.posting_date)
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
    await _assert_period_open(db, entry.company_code, entry.posting_date)
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
    previous_path = Path(entry.attachment_path) if entry.attachment_path else None
    try:
        streamed = await persist_streamed_upload(
            file,
            directory=UPLOAD_ROOT / entry.company_code,
            filename_prefix=f"{entry.id}-",
            max_size=MAX_UPLOAD_SIZE,
        )
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail="O arquivo excede o limite de 10 MB.") from exc
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="Armazenamento de anexos indisponível. Verifique o volume /app/storage da API.",
        ) from exc
    target = streamed.path

    before = _snapshot(entry)
    entry.attachment_name, entry.attachment_path, entry.attachment_mime = (
        file.filename or target.name,
        str(target),
        streamed.mime_type,
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
