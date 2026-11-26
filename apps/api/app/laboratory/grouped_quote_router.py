"""Orçamentos conjuntos persistentes, sem alterar os orçamentos individuais."""
import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, noload

from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.commercial.models import CommercialCompanyProfile
from app.core.db import get_db
from app.laboratory.grouped_quote_pdf import grouped_quote_pdf
from app.laboratory.grouped_quote_schemas import (
    GroupedQuoteCreate, GroupedQuoteEmit, GroupedQuoteItemInput,
    GroupedQuoteOutput, GroupedQuoteTerms, GroupedQuoteUpdate,
)
from app.laboratory.grouped_quote_totals import grouped_totals
from app.laboratory.models import (
    LaboratoryCustomer, LaboratoryGroupedQuote, LaboratoryGroupedQuoteItem,
    LaboratoryGroupedQuoteWorkOrder, LaboratoryQuoteGroup, LaboratoryWorkOrder,
)
from app.laboratory.router import (
    _company_snapshot_payload, _require_quote_permission,
    _set_work_order_substatus, _workflow_option_by_code,
)
from app.notifications.events import work_order_activity

router = APIRouter(prefix="/laboratory/grouped-quotes", dependencies=[Depends(require_module("laboratorio"))])
CURRENT_USER = Depends(current_user)
DATABASE = Depends(get_db)


async def _orders(db: AsyncSession, ids: list[int], *, lock: bool = False):
    query = (select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.id.in_(ids))
             .options(noload("*"), joinedload(LaboratoryWorkOrder.equipment))
             .order_by(LaboratoryWorkOrder.id).execution_options(populate_existing=True))
    if lock:
        # A mesma ordem do faturamento em lote evita locks inversos entre OS.
        query = query.with_for_update(of=LaboratoryWorkOrder)
    rows = {row.id: row for row in (await db.scalars(query)).all()}
    if len(rows) != len(ids):
        raise HTTPException(404, "Uma das OS selecionadas não foi encontrada.")
    return rows


async def _validate_members(db, ids, *, group=None, lock=False):
    rows = await _orders(db, ids, lock=lock)
    first = rows[ids[0]]
    if first.customer_id is None:
        raise HTTPException(422, "Vincule todas as OS ao mesmo cliente cadastrado antes de agrupá-las.")
    for order in rows.values():
        if order.is_cancelled or order.is_inactive:
            raise HTTPException(409, f"A OS {order.number} está cancelada ou inativa.")
        if order.customer_id != first.customer_id or order.company_code != first.company_code:
            raise HTTPException(422, "Um orçamento conjunto deve conter somente OS do mesmo cliente e da mesma empresa emissora.")
    if group and (first.customer_id != group.customer_id or first.company_code != group.company_code):
        raise HTTPException(422, "Mantenha o cliente e a empresa emissora originais do conjunto; crie outro orçamento para outro cliente.")
    customer = await db.get(LaboratoryCustomer, first.customer_id, populate_existing=True)
    if customer is None or not customer.is_active or customer.company_code != first.company_code:
        raise HTTPException(422, "O cliente do conjunto não está ativo na empresa emissora.")
    company = await db.scalar(select(CommercialCompanyProfile).where(
        CommercialCompanyProfile.company_code == first.company_code,
        CommercialCompanyProfile.is_active.is_(True),
    ))
    if company is None:
        raise HTTPException(422, "Empresa emissora inexistente ou inativa no Config Master.")
    return rows, customer, company


async def _locked_quote(db, quote_id: int, *, write: bool):
    group_id = await db.scalar(select(LaboratoryGroupedQuote.group_id).where(LaboratoryGroupedQuote.id == quote_id))
    if group_id is None:
        raise HTTPException(404, "Orçamento conjunto não encontrado.")
    # Toda alteração da família (edição, exclusão, revisão e emissão) usa o mesmo
    # lock; a leitura individual mantém cabeçalho, itens e versão consistentes.
    await db.scalar(select(LaboratoryQuoteGroup).where(LaboratoryQuoteGroup.id == group_id)
                    .with_for_update(read=not write).execution_options(populate_existing=True))
    quote = await db.scalar(select(LaboratoryGroupedQuote).where(LaboratoryGroupedQuote.id == quote_id)
                            .execution_options(populate_existing=True))
    if quote is None:
        raise HTTPException(404, "Orçamento conjunto não encontrado.")
    return quote


def _output(quote, orders=None, *, customer_name=None):
    if quote.document_snapshot is not None:
        # As identidades e os valores da revisão emitida não acompanham edições
        # posteriores da OS, do equipamento, do cliente ou da empresa emissora.
        return GroupedQuoteOutput.model_validate(quote.document_snapshot["quote"])
    orders = orders or {}
    members = []
    for member in quote.work_orders:
        order = orders[member.work_order_id]
        members.append({
            "id": order.id, "number": order.number, "equipment_id": order.equipment_id,
            "equipment_type": order.equipment.equipment_type,
            "manufacturer": order.equipment.manufacturer, "model": order.equipment.model,
            "equipment_serial": order.equipment_serial, "reported_defect": order.reported_defect,
            "opened_at": order.opened_at, "entry_invoice": order.entry_invoice, "version": order.version,
            "subtotal": member.subtotal, "discount_amount": member.discount_amount, "total": member.total,
        })
    return GroupedQuoteOutput(**quote.content, id=quote.id, group_id=quote.group_id,
        code=quote.group.code, revision=quote.revision, status=quote.status, version=quote.version,
        company_code=quote.group.company_code, customer_id=quote.group.customer_id,
        customer_name=customer_name or quote.group.customer_name,
        work_order_ids=[row.work_order_id for row in quote.work_orders], work_orders=members,
        items=[{"id": row.id, "position": row.position, "work_order_id": row.work_order_id,
                "description": row.description, "quantity": row.quantity, "unit_value": row.unit_value}
               for row in quote.items],
        subtotal=quote.subtotal, discount_amount=quote.discount_amount, total=quote.total,
        emitted_at=quote.emitted_at, created_at=quote.created_at, updated_at=quote.updated_at)


async def _live_output(db, quote):
    if quote.document_snapshot is not None:
        return _output(quote)
    return _output(quote, await _orders(db, [row.work_order_id for row in quote.work_orders]))


async def _replace_rows(db, quote, ids, items, terms):
    subtotal, discount, total, amounts = grouped_totals(ids, items, terms)
    # Itens referenciam a composição por chave composta. Excluí-los primeiro e
    # inserir a composição antes dos itens também funciona com autoflush=False.
    quote.items.clear()
    await db.flush()
    quote.work_orders.clear()
    await db.flush()
    quote.work_orders = [LaboratoryGroupedQuoteWorkOrder(work_order_id=key, position=position, **amounts[key])
                         for position, key in enumerate(ids, 1)]
    await db.flush()
    quote.items = [LaboratoryGroupedQuoteItem(work_order_id=item.work_order_id, position=position,
                   description=item.description, quantity=item.quantity, unit_value=item.unit_value)
                   for position, item in enumerate(items, 1)]
    quote.content = terms.model_dump(mode="json")
    quote.subtotal, quote.discount_amount, quote.total = subtotal, discount, total
    await db.flush()


def _draft_version(quote, version):
    if quote.status != "draft":
        raise HTTPException(409, "Esta revisão já foi emitida. Crie uma nova revisão para alterá-la.")
    if quote.version != version:
        raise HTTPException(409, "O orçamento foi alterado por outra operação. Recarregue antes de salvar.")


def _pdf_response(quote, content, *, preview):
    disposition = "inline" if preview else "attachment"
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'{disposition}; filename="orcamento-conjunto-{quote.group.code}-r{quote.revision:02d}.pdf"',
        "Cache-Control": "private, no-store",
    })


async def _stored_pdf(db, quote):
    content = await db.scalar(select(LaboratoryGroupedQuote.pdf_content).where(LaboratoryGroupedQuote.id == quote.id))
    if not content or hashlib.sha256(content).hexdigest() != quote.pdf_sha256:
        raise HTTPException(409, "O arquivo histórico deste orçamento está indisponível. Solicite verificação antes de emitir outra revisão.")
    return content


async def _render(snapshot):
    try:
        return await asyncio.to_thread(grouped_quote_pdf, snapshot)
    except Exception as exc:
        raise HTTPException(422, "Não foi possível gerar o PDF do conjunto. Confira os textos do orçamento; o rascunho continua disponível.") from exc


def _snapshot(output, company, customer, issued_at):
    return {"quote": output.model_dump(mode="json"), "company": _company_snapshot_payload(company),
            "customer": {key: getattr(customer, key) for key in (
                "id", "legal_name", "trade_name", "document", "state_registration", "phone", "email",
                "postal_code", "address", "address_number", "complement", "district", "city", "state")},
            "issued_at": issued_at.isoformat()}


@router.post("", response_model=GroupedQuoteOutput, status_code=201)
async def create_grouped_quote(payload: GroupedQuoteCreate, user: User = CURRENT_USER, db: AsyncSession = DATABASE,
                               idempotency_key: str = Header(alias="Idempotency-Key", max_length=128)):
    _require_quote_permission(user)
    fingerprint = hashlib.sha256(json.dumps(payload.model_dump(mode="json"), sort_keys=True,
                                            ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(422, "A chave da operação deve ter de 8 a 128 letras, números ou separadores ._:-.")
    lock_key = int.from_bytes(hashlib.sha256(f"lab-group:{user.id}:{idempotency_key}".encode()).digest()[:8], "big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    prior = await db.scalar(select(LaboratoryQuoteGroup).where(
        LaboratoryQuoteGroup.created_by == user.id, LaboratoryQuoteGroup.creation_key == idempotency_key))
    if prior is not None:
        if prior.creation_fingerprint != fingerprint:
            raise HTTPException(409, "Esta chave já foi usada com outro conteúdo. Recarregue antes de criar outro conjunto.")
        original_id = await db.scalar(select(LaboratoryGroupedQuote.id).where(
            LaboratoryGroupedQuote.group_id == prior.id).order_by(LaboratoryGroupedQuote.revision).limit(1))
        if original_id is None:
            raise HTTPException(409, "O rascunho desta operação já foi excluído. Inicie uma nova criação.")
        return await _live_output(db, await _locked_quote(db, original_id, write=False))
    orders, customer, _company = await _validate_members(db, payload.work_order_ids, lock=True)
    terms = GroupedQuoteTerms.model_validate(payload.model_dump())
    items = payload.items or [GroupedQuoteItemInput(work_order_id=key, description="SERVIÇO DE MANUTENÇÃO E REPARO",
                             quantity=Decimal("1"), unit_value=orders[key].quoted_value or Decimal("0"))
                             for key in payload.work_order_ids]
    group = LaboratoryQuoteGroup(code=f"OC-TMP-{uuid4().hex}", company_code=customer.company_code,
        customer_id=customer.id, customer_name=customer.legal_name, creation_key=idempotency_key,
        creation_fingerprint=fingerprint, created_by=user.id)
    db.add(group)
    await db.flush()
    group.code = f"OC-{group.id:06d}"
    quote = LaboratoryGroupedQuote(group=group, revision=1, version=1, status="draft",
        content=terms.model_dump(mode="json"), created_by=user.id, work_orders=[], items=[])
    db.add(quote)
    await db.flush()
    await _replace_rows(db, quote, payload.work_order_ids, items, terms)
    output = _output(quote, orders)
    await db.commit()
    return output


@router.get("", response_model=list[GroupedQuoteOutput])
async def list_grouped_quotes(work_order_id: int | None = Query(default=None, gt=0),
    group_id: int | None = Query(default=None, gt=0), company_code: str | None = Query(default=None, max_length=40),
    search: str | None = Query(default=None, max_length=120), limit: int = Query(default=100, ge=1, le=200),
    user: User = CURRENT_USER, db: AsyncSession = DATABASE):
    _require_quote_permission(user)
    query = select(LaboratoryGroupedQuote).join(LaboratoryQuoteGroup)
    if work_order_id is not None:
        query = query.where(LaboratoryGroupedQuote.work_orders.any(LaboratoryGroupedQuoteWorkOrder.work_order_id == work_order_id))
    if group_id is not None:
        query = query.where(LaboratoryGroupedQuote.group_id == group_id)
    if company_code is not None:
        query = query.where(LaboratoryQuoteGroup.company_code == company_code)
    if search and search.strip():
        term = f"%{search.strip()}%"
        matching_orders = select(LaboratoryWorkOrder.id).where(or_(
            LaboratoryWorkOrder.number.ilike(term), LaboratoryWorkOrder.equipment_serial.ilike(term)))
        query = query.where(or_(LaboratoryQuoteGroup.code.ilike(term), LaboratoryQuoteGroup.customer_name.ilike(term),
                               LaboratoryGroupedQuote.content["title"].as_string().ilike(term),
                               LaboratoryGroupedQuote.work_orders.any(LaboratoryGroupedQuoteWorkOrder.work_order_id.in_(matching_orders))))
    # Compartilhar o lock da família mantém itens e versão coerentes durante o
    # carregamento selectin, inclusive quando a lista é usada para abrir edição.
    query = query.order_by(LaboratoryGroupedQuote.group_id.desc(), LaboratoryGroupedQuote.revision.desc()).limit(limit)
    query = query.with_for_update(read=True, of=LaboratoryQuoteGroup)
    rows = list((await db.scalars(query)).all())
    ids = sorted({member.work_order_id for quote in rows if quote.document_snapshot is None for member in quote.work_orders})
    orders = await _orders(db, ids) if ids else {}
    return [_output(quote, orders) for quote in rows]


@router.get("/{quote_id}", response_model=GroupedQuoteOutput)
async def get_grouped_quote(quote_id: int, user: User = CURRENT_USER, db: AsyncSession = DATABASE):
    _require_quote_permission(user)
    return await _live_output(db, await _locked_quote(db, quote_id, write=False))


@router.put("/{quote_id}", response_model=GroupedQuoteOutput)
async def update_grouped_quote(quote_id: int, payload: GroupedQuoteUpdate, user: User = CURRENT_USER, db: AsyncSession = DATABASE):
    _require_quote_permission(user)
    quote = await _locked_quote(db, quote_id, write=True)
    _draft_version(quote, payload.version)
    orders, customer, _company = await _validate_members(db, payload.work_order_ids, group=quote.group, lock=True)
    supplied = payload.model_dump(mode="json", include=set(GroupedQuoteTerms.model_fields) & payload.model_fields_set)
    try:
        terms = GroupedQuoteTerms.model_validate({**quote.content, **supplied})
    except ValidationError as exc:
        # Campos omitidos conservam o valor anterior. A validação precisa ser
        # repetida depois do merge (por exemplo, tipo percentual já salvo).
        raise HTTPException(422, "Condições comerciais inválidas. Confira o desconto, os prazos e a garantia.") from exc
    await _replace_rows(db, quote, payload.work_order_ids, payload.items, terms)
    quote.version += 1
    await db.flush()
    output = _output(quote, orders, customer_name=customer.legal_name)
    await db.commit()
    return output


@router.delete("/{quote_id}", status_code=204)
async def delete_grouped_quote(quote_id: int, version: int = Query(ge=1), user: User = CURRENT_USER, db: AsyncSession = DATABASE):
    _require_quote_permission(user)
    quote = await _locked_quote(db, quote_id, write=True)
    _draft_version(quote, version)
    await db.execute(delete(LaboratoryGroupedQuote).where(LaboratoryGroupedQuote.id == quote.id))
    await db.commit()
    return Response(status_code=204)


@router.post("/{quote_id}/revisions", response_model=GroupedQuoteOutput, status_code=201)
async def revise_grouped_quote(quote_id: int, user: User = CURRENT_USER, db: AsyncSession = DATABASE):
    _require_quote_permission(user)
    source = await _locked_quote(db, quote_id, write=True)
    draft = await db.scalar(select(LaboratoryGroupedQuote).where(
        LaboratoryGroupedQuote.group_id == source.group_id, LaboratoryGroupedQuote.status == "draft"))
    if draft is not None:
        return await _live_output(db, draft)
    latest = await db.scalar(select(func.max(LaboratoryGroupedQuote.revision)).where(LaboratoryGroupedQuote.group_id == source.group_id))
    quote = LaboratoryGroupedQuote(group=source.group, revision=(latest or 0) + 1, version=1, status="draft",
        content=dict(source.content), created_by=user.id, work_orders=[], items=[])
    db.add(quote)
    await db.flush()
    ids = [row.work_order_id for row in source.work_orders]
    items = [GroupedQuoteItemInput(work_order_id=row.work_order_id, description=row.description,
             quantity=row.quantity, unit_value=row.unit_value) for row in source.items]
    await _replace_rows(db, quote, ids, items, GroupedQuoteTerms.model_validate(source.content))
    output = await _live_output(db, quote)
    await db.commit()
    return output


@router.get("/{quote_id}/pdf")
async def preview_grouped_quote(quote_id: int, preview: bool = Query(default=True),
                                user: User = CURRENT_USER, db: AsyncSession = DATABASE):
    _require_quote_permission(user)
    quote = await _locked_quote(db, quote_id, write=False)
    if quote.status == "emitted":
        return _pdf_response(quote, await _stored_pdf(db, quote), preview=preview)
    ids = [row.work_order_id for row in quote.work_orders]
    orders, customer, company = await _validate_members(db, ids, group=quote.group)
    snapshot = _snapshot(_output(quote, orders, customer_name=customer.legal_name), company, customer, datetime.now(UTC))
    return _pdf_response(quote, await _render(snapshot), preview=preview)


@router.post("/{quote_id}/emit")
async def emit_grouped_quote(quote_id: int, payload: GroupedQuoteEmit, user: User = CURRENT_USER, db: AsyncSession = DATABASE):
    _require_quote_permission(user)
    quote = await _locked_quote(db, quote_id, write=True)
    if quote.status == "emitted":
        # Retry de resposta perdida devolve exatamente o documento já emitido,
        # sem incrementar versões nem reaplicar valores nas OS.
        return _pdf_response(quote, await _stored_pdf(db, quote), preview=False)
    _draft_version(quote, payload.version)
    if not (quote.content.get("technical_report") or "").strip():
        raise HTTPException(422, "Preencha o diagnóstico técnico / laudo antes de emitir o orçamento conjunto.")
    ids = [row.work_order_id for row in quote.work_orders]
    orders, customer, company = await _validate_members(db, ids, group=quote.group, lock=True)
    issued_at = datetime.now(UTC)
    output = _output(quote, orders, customer_name=customer.legal_name)
    output.status, output.version, output.emitted_at, output.updated_at = "emitted", quote.version + 1, issued_at, issued_at
    for member in output.work_orders:
        member.version += 1
    snapshot = _snapshot(output, company, customer, issued_at)
    content = await _render(snapshot)
    quote.status, quote.emitted_at, quote.updated_at = "emitted", issued_at, issued_at
    quote.version += 1
    quote.document_snapshot, quote.pdf_content, quote.pdf_sha256 = snapshot, content, hashlib.sha256(content).hexdigest()
    sent = await _workflow_option_by_code(db, kind="substatus", code="quote_sent")
    for member in quote.work_orders:
        order = orders[member.work_order_id]
        order.quoted_value = member.total
        order.version += 1
        if sent is not None:
            await _set_work_order_substatus(db, work_order=order, code="quote_sent", active=True, user_id=user.id)
        await work_order_activity(db, actor=user, work_order=order, module="orcamentos", action="grouped_quote_issued",
            title=f"Orçamento conjunto emitido · {quote.group.code}",
            message=f"{user.name} emitiu {quote.group.code}, revisão {quote.revision}, incluindo a OS {order.number}.", severity="success")
    await db.flush()
    await db.commit()
    return _pdf_response(quote, content, preview=False)
