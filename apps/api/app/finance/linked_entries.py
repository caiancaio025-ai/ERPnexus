"""Criação/edição atômica de uma receita com várias OS, sem duplicar títulos."""
import hashlib
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select

from app.finance.billing_batches import assert_work_order_version, lock_billing_batch, outgoing_invoice_number, outgoing_invoice_slot
from app.finance.idempotency import finance_request_fingerprint
from app.finance.installment_edit import INDIVIDUAL_FIELDS, SHARED_FIELDS
from app.finance.models import FinancialAuditEvent, FinancialEntry, FinancialObligation
from app.finance.period_locks import lock_entry_periods
from app.finance.schemas import BillingConfirmation, FinancialWorkOrderAllocationInput
from app.finance.work_order_links import (
    aggregate_allocations, allocation_snapshot, assert_links_editable, assert_versions, closed_periods,
    entry_outputs, link_lock_reason, lock_scope, order_rows, registered_totals, replace_allocations,
)

AUXILIARY_FIELDS = {"work_order_id", "work_order_version", "work_orders", "billing_confirmation", "exit_invoice",
                    "version", "obligation_version", "obligation_total_amount"}


def _router():
    # Os helpers de conformidade e auditoria existentes continuam sendo a regra
    # única, sem introduzir importação circular na carga dos routers.
    from app.finance import router
    return router


def confirmation_data(value):
    data = BillingConfirmation.model_validate(value or {}).model_dump(mode="json")
    # Formulários enviam texto vazio para campos históricos nulos. Essa
    # equivalência não representa alteração do checklist nem apaga evidências.
    return {key: (item.strip() or None) if isinstance(item, str) else item for key, item in data.items()}


def selection_changed(specs, previous):
    if {row.work_order_id: row.amount for row in specs} != {key: row["amount"] for key, row in previous.items()}:
        return True
    for row in specs:
        if row.billing_confirmation is not None:
            old = (previous[row.work_order_id].get("billing_compliance") or {}).get("confirmation")
            if confirmation_data(row.billing_confirmation) != confirmation_data(old):
                return True
    return False


async def validate_selection(db, specs, *, total, company_code, previous=None, entries=(), orders=None, exit_invoice=None):
    previous = previous or {}
    if not specs:
        return {}, {}
    if sum((row.amount for row in specs), Decimal("0.00")) != total:
        raise HTTPException(422, "A soma do rateio por OS deve ser igual ao total do faturamento, não apenas ao valor da parcela aberta.")
    if len(specs) * max(1, len(entries)) > 1000:
        raise HTTPException(422, "O rateio pode ter no máximo 1.000 combinações de OS e parcelas.")
    ids = sorted(row.work_order_id for row in specs)
    orders = orders if orders is not None else await order_rows(db, ids, lock=True)
    selected = {key: orders[key] for key in ids if key in orders}
    if len(selected) != len(ids):
        raise HTTPException(422, "Uma das OS selecionadas não foi encontrada.")
    if any(row.company_code != company_code for row in selected.values()):
        raise HTTPException(422, "Todas as OS devem pertencer à empresa da receita.")
    if len(selected) > 1:
        customers = {row.customer_id for row in selected.values()}
        if None in customers or len(customers) != 1:
            raise HTTPException(422, "Selecione OS do mesmo cliente cadastrado para o faturamento conjunto.")
    totals_elsewhere = await registered_totals(db, ids, exclude_entry_ids=[row.id for row in entries if hasattr(row, "id")])
    result = {}
    finance = _router()
    for spec in specs:
        order = selected[spec.work_order_id]
        prior = previous.get(order.id)
        increased = prior is None or spec.amount > prior["amount"]
        if (increased or exit_invoice) and (order.is_cancelled or order.is_inactive):
            raise HTTPException(409, f"A OS {order.number} está cancelada ou inativa.")
        if increased or exit_invoice:
            assert_work_order_version(order, spec.version)
        if increased and order.approved_value is not None:
            remaining = order.approved_value - totals_elsewhere.get(order.id, Decimal("0.00"))
            if spec.amount > remaining:
                raise HTTPException(409, f"O valor da OS {order.number} excede o saldo faturável de R$ {remaining:.2f}.")
        if exit_invoice:
            outgoing_invoice_slot(order, exit_invoice)
        compliance = (prior or {}).get("billing_compliance")
        supplied = spec.billing_confirmation
        changed_confirmation = supplied is not None and confirmation_data(supplied) != confirmation_data((compliance or {}).get("confirmation"))
        if increased or changed_confirmation:
            confirmation = supplied or BillingConfirmation.model_validate((compliance or {}).get("confirmation") or {})
            compliance = await finance._validate_billing_confirmation(db, order, confirmation)
        result[order.id] = {"work_order_id": order.id, "amount": spec.amount, "billing_compliance": compliance}
    return result, selected


async def _creation_replay(db, payload, key, model):
    key = (key or "").strip()
    if not key:
        raise HTTPException(422, "Informe Idempotency-Key para salvar o faturamento com segurança.")
    fingerprint = finance_request_fingerprint(payload)
    lock = hashlib.sha256(f"finance-linked:{model.__tablename__}:{key}".encode()).hexdigest()
    await lock_billing_batch(db, lock)
    existing = await db.scalar(select(model).where(model.idempotency_key == key))
    if existing is not None and existing.idempotency_fingerprint != fingerprint:
        raise HTTPException(409, "A mesma chave de envio foi reutilizada com dados diferentes.")
    return key, fingerprint, existing


async def _sync_orders(db, user, entries, totals, orders, previous, exit_invoice):
    finance = _router()
    for key in sorted(totals):
        increased = key not in previous or totals[key]["amount"] > previous[key]["amount"]
        if increased or exit_invoice:
            await finance._mark_work_order_invoiced(db, orders[key], user.id,
                SimpleNamespace(id=entries[0].id, amount=totals[key]["amount"]),
                exit_invoice=exit_invoice, increment_version=increased)


async def create_entry_with_links(db, user, payload, key):
    finance = _router()
    key, fingerprint, existing = await _creation_replay(db, payload, key, FinancialEntry)
    if existing is not None:
        return (await entry_outputs(db, [existing]))[0]
    await finance._validate_entry_account_company(db, payload)
    invoice = outgoing_invoice_number(payload) if payload.work_orders else None
    totals, orders = await validate_selection(db, payload.work_orders or [], total=payload.amount,
        company_code=payload.company_code, exit_invoice=invoice)
    await finance._assert_period_open(db, payload.company_code, payload.posting_date)
    entry = FinancialEntry(**payload.model_dump(exclude=AUXILIARY_FIELDS), version=1, status="pending",
        idempotency_key=key, idempotency_fingerprint=fingerprint, created_by=user.id)
    db.add(entry)
    await db.flush()
    await replace_allocations(db, [entry], totals)
    await _sync_orders(db, user, [entry], totals, orders, {}, invoice)
    db.add(finance._audit(entry, "created", f"Receita criada: {entry.description}"[:280], user.id,
                         after={**finance._snapshot(entry), "work_orders": allocation_snapshot(totals)}))
    await finance.notify_activity(db, actor=user, activity_module="financeiro", action="finance_entry_created",
        title=f"Lançamento financeiro · {entry.description}", message=f"{user.name} registrou um lançamento financeiro.",
        target="/financeiro", entity_type="financial_entry", entity_id=entry.id, work_order_id=entry.work_order_id)
    await db.flush()
    output = (await entry_outputs(db, [entry]))[0]
    await db.commit()
    return output


async def create_obligation_with_links(db, user, payload, key):
    finance = _router()
    key, fingerprint, existing = await _creation_replay(db, payload, key, FinancialObligation)
    if existing is not None:
        return await finance._obligation_output(db, existing)
    await finance._validate_obligation_account_company(db, payload)
    invoice = outgoing_invoice_number(payload) if payload.work_orders else None
    totals, orders = await validate_selection(db, payload.work_orders or [], total=payload.total_amount,
        company_code=payload.company_code, entries=payload.installments, exit_invoice=invoice)
    await finance._assert_period_open(db, payload.company_code, payload.posting_date)
    common = payload.model_dump(exclude=AUXILIARY_FIELDS | {"installments", "total_amount"})
    obligation = FinancialObligation(**common, total_amount=payload.total_amount, installment_count=len(payload.installments),
        work_order_id=next(iter(totals)) if len(totals) == 1 else None, version=1,
        idempotency_key=key, idempotency_fingerprint=fingerprint, created_by=user.id)
    db.add(obligation)
    await db.flush()
    entries = [FinancialEntry(**{**common, "notes": spec.notes or payload.notes},
        obligation_id=obligation.id, installment_number=spec.installment_number, amount=spec.amount,
        due_date=spec.due_date, payment_code=spec.payment_code, status="pending", version=1, created_by=user.id)
        for spec in sorted(payload.installments, key=lambda spec: spec.installment_number)]
    db.add_all(entries)
    await db.flush()
    await replace_allocations(db, entries, totals)
    await _sync_orders(db, user, entries, totals, orders, {}, invoice)
    for entry in entries:
        db.add(finance._audit(entry, "created", f"Parcela {entry.installment_number} criada: {entry.description}"[:280],
                             user.id, after=finance._snapshot(entry)))
    db.add(FinancialAuditEvent(entity_type="financial_obligation", entity_id=obligation.id, action="created",
        description="Faturamento criado com rateio por OS, sem duplicar receitas", user_id=user.id,
        after_data={"total_amount": str(obligation.total_amount), "work_orders": allocation_snapshot(totals)}))
    await db.flush()
    output = await finance._obligation_output(db, obligation)
    await db.commit()
    return output


async def update_entry_with_links(db, user, entry_id, payload):
    finance = _router()
    specs = payload.work_orders
    extra_ids = [row.work_order_id for row in specs] if specs is not None else ([payload.work_order_id] if payload.work_order_id else [])
    scope = await lock_scope(db, entry_id=entry_id, additional_ids=extra_ids)
    entry, obligation = scope.entry, scope.obligation
    assert_versions(scope, payload.version, payload.obligation_version, required=specs is not None)
    effective_account = payload.account_id if "account_id" in payload.model_fields_set else entry.account_id
    await finance._validate_entry_account_company(db, SimpleNamespace(account_id=effective_account, company_code=payload.company_code))
    await lock_entry_periods(db, scope.entries)
    await finance._assert_period_open(db, entry.company_code, entry.posting_date)
    await finance._assert_period_open(db, payload.company_code, payload.posting_date)
    previous = aggregate_allocations(scope.allocations, scope.entries)
    total = sum((row.amount for row in scope.entries), Decimal("0.00")) - entry.amount + payload.amount
    if obligation:
        if payload.entry_type != entry.entry_type or payload.company_code != entry.company_code:
            raise HTTPException(409, "Empresa e tipo permanecem protegidos nas parcelas do faturamento.")
        if specs is not None:
            if payload.obligation_total_amount is None:
                raise HTTPException(422, "Informe o valor total do parcelamento para validar o rateio das OS.")
            if payload.obligation_total_amount != total:
                raise HTTPException(409, "O total do parcelamento mudou. Recarregue os valores antes de distribuir entre as OS.")
        elif "work_order_id" in payload.model_fields_set and payload.work_order_id != entry.work_order_id:
            raise HTTPException(409, "Para alterar as OS do parcelamento, use a lista de vínculos do faturamento.")
    elif specs is None and "work_order_id" in payload.model_fields_set and payload.work_order_id != entry.work_order_id:
        if payload.work_order_id is not None and payload.work_order_id not in scope.orders:
            raise HTTPException(422, "A OS selecionada não foi encontrada.")
        specs = [] if payload.work_order_id is None else [FinancialWorkOrderAllocationInput(
            work_order_id=payload.work_order_id, amount=payload.amount,
            version=payload.work_order_version or scope.orders[payload.work_order_id].version,
            billing_confirmation=payload.billing_confirmation)]
    if payload.entry_type != "income" and previous:
        specs = []
    changed = specs is not None and selection_changed(specs, previous)
    amount_changed = payload.amount != entry.amount
    reason = link_lock_reason(scope.entries, await closed_periods(db, scope.entries))
    if (changed or (amount_changed and previous)) and reason:
        raise HTTPException(409, reason)
    if amount_changed and entry.status != "pending":
        raise HTTPException(409, "O valor de um lançamento baixado não pode ser alterado. Estorne a baixa primeiro.")
    if specs is None and amount_changed and previous:
        if len(previous) > 1:
            raise HTTPException(422, "Informe o rateio atualizado das OS ao alterar o valor do faturamento.")
        key = next(iter(previous))
        specs = [FinancialWorkOrderAllocationInput(work_order_id=key, amount=total,
            version=payload.work_order_version or scope.orders[key].version, billing_confirmation=payload.billing_confirmation)]
        changed = True
    invoice_changed = bool((payload.exit_invoice or "").strip()) or any(getattr(entry, key) != getattr(payload, key) for key in ("nfse_number", "nfe_number"))
    resulting_selection = specs if specs is not None else previous
    invoice = outgoing_invoice_number(payload) if resulting_selection and (invoice_changed or changed) and not reason else None
    if invoice and not changed and not any(outgoing_invoice_slot(scope.orders[key], invoice) for key in previous):
        invoice = None  # A mesma NF já registrada não reaplica estado/versão nas OS.
    if payload.exit_invoice and reason:
        raise HTTPException(409, "A sincronização de NF nas OS está bloqueada enquanto houver baixa ou competência fechada.")
    totals = previous
    if specs is not None and (changed or invoice):
        totals, _ = await validate_selection(db, specs, total=total, company_code=payload.company_code,
            previous=previous, entries=scope.entries, orders=scope.orders, exit_invoice=invoice)
    elif invoice and previous:
        legacy_specs = [FinancialWorkOrderAllocationInput(work_order_id=key, amount=row["amount"],
                        version=payload.work_order_version or scope.orders[key].version) for key, row in previous.items()]
        totals, _ = await validate_selection(db, legacy_specs, total=total, company_code=payload.company_code,
            previous=previous, entries=scope.entries, orders=scope.orders, exit_invoice=invoice)
    if totals and any(scope.orders[key].company_code != payload.company_code for key in totals):
        raise HTTPException(422, "A empresa da receita deve corresponder às OS vinculadas.")
    before_rows = {row.id: finance._snapshot(row) for row in scope.entries}
    if obligation:
        shared = {key: getattr(payload, key) for key in SHARED_FIELDS}
        for row in scope.entries:
            if any(getattr(row, key) != value for key, value in shared.items()):
                await finance._assert_period_open(db, row.company_code, row.posting_date)
            for key, value in shared.items():
                setattr(row, key, value)
        for key in INDIVIDUAL_FIELDS:
            if key in {"account_id", "category_id"} and key not in payload.model_fields_set:
                continue
            setattr(entry, key, getattr(payload, key))
        for key, value in shared.items():
            setattr(obligation, key, value)
        obligation.total_amount = total
        obligation.version += 1
    else:
        for key, value in payload.model_dump(exclude=AUXILIARY_FIELDS).items():
            if key in {"account_id", "category_id"} and key not in payload.model_fields_set:
                continue
            setattr(entry, key, value)
    if changed or (amount_changed and previous):
        await assert_links_editable(db, scope.entries)
        await replace_allocations(db, scope.entries, totals)
        if obligation:
            obligation.work_order_id = next(iter(totals)) if len(totals) == 1 else None
    for row in scope.entries:
        row.version += 1
        after = finance._snapshot(row)
        if row is entry or after != before_rows[row.id]:
            db.add(finance._audit(row, "updated", f"Lançamento editado: {row.description}"[:280], user.id,
                {**before_rows[row.id], "work_orders": allocation_snapshot(previous)},
                {**after, "work_orders": allocation_snapshot(totals)}))
    if obligation and changed:
        db.add(FinancialAuditEvent(entity_type="financial_obligation", entity_id=obligation.id,
            action="work_orders_updated", description="Vínculos e rateio das OS alterados sem recriar as parcelas", user_id=user.id,
            before_data={"work_orders": allocation_snapshot(previous)}, after_data={"work_orders": allocation_snapshot(totals)}))
    if (changed or invoice) and not reason:
        await _sync_orders(db, user, scope.entries, totals, scope.orders, previous, invoice)
    await finance.notify_activity(db, actor=user, activity_module="financeiro", action="finance_entry_updated",
        title=f"Lançamento financeiro · {entry.description}", message=f"{user.name} alterou um lançamento financeiro.",
        target="/financeiro", entity_type="financial_entry", entity_id=entry.id, work_order_id=entry.work_order_id)
    await db.flush()
    output = (await entry_outputs(db, [entry]))[0]
    await db.commit()
    return output
