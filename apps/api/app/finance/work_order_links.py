"""Vínculos e rateio de OS dentro dos títulos financeiros existentes."""
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, exists, func, select, union_all
from sqlalchemy.orm import joinedload, noload

from app.finance.models import FinancialEntry, FinancialEntryWorkOrder, FinancialObligation, FinancialPeriodClosure
from app.finance.period_locks import lock_entry_periods
from app.finance.schemas import FinancialEntryOutput, FinancialWorkOrderAllocationOutput
from app.laboratory.models import LaboratoryWorkOrder

CENT = Decimal("0.01")


def allocation_rows():
    """Rateios novos e vínculos históricos, sem contar o mesmo título duas vezes."""
    explicit = select(FinancialEntryWorkOrder.entry_id, FinancialEntryWorkOrder.work_order_id,
                      FinancialEntryWorkOrder.amount, FinancialEntryWorkOrder.billing_compliance)
    legacy = select(FinancialEntry.id.label("entry_id"), FinancialEntry.work_order_id,
                    FinancialEntry.amount, FinancialEntry.billing_compliance).where(
        FinancialEntry.work_order_id.is_not(None),
        ~exists(select(FinancialEntryWorkOrder.entry_id).where(FinancialEntryWorkOrder.entry_id == FinancialEntry.id)),
    )
    return union_all(explicit, legacy).subquery("effective_financial_os_allocations")


async def raw_allocations(db, entry_ids):
    if not entry_ids:
        return {}
    rows = allocation_rows()
    result = {key: [] for key in entry_ids}
    for row in (await db.execute(select(rows).where(rows.c.entry_id.in_(entry_ids)))).mappings():
        result[row["entry_id"]].append(dict(row))
    return result


def aggregate_allocations(allocations, entries):
    totals = {}
    for entry in entries:
        for row in allocations.get(entry.id, []):
            key = row["work_order_id"]
            if key not in totals:
                totals[key] = {**row, "amount": Decimal("0.00")}
            totals[key]["amount"] += row["amount"]
    return totals


def allocation_amounts(rows):
    return {row["work_order_id"]: row["amount"] for row in rows}


def apportion(total, weights):
    """Maior resto em centavos; empate segue a ordem estável dos IDs/parcelas."""
    cents = int(total * 100)
    weights = [int(value * 100) for value in weights]
    if cents < 0 or any(value < 0 for value in weights):
        raise HTTPException(422, "Não é possível ratear um valor negativo.")
    if not weights:
        return []
    weight_sum = sum(weights)
    if not weight_sum:
        if cents:
            raise HTTPException(422, "Informe valores por OS para distribuir o total.")
        return [Decimal("0.00")] * len(weights)
    division = [divmod(cents * value, weight_sum) for value in weights]
    result = [whole for whole, _ in division]
    remaining = cents - sum(result)
    for index in sorted(range(len(weights)), key=lambda index: (-division[index][1], index))[:remaining]:
        result[index] += 1
    return [(Decimal(value) / 100).quantize(CENT) for value in result]


def allocation_matrix(row_amounts, column_amounts):
    """Preserva o total de cada OS e de cada parcela; células zero são válidas."""
    if sum(row_amounts, Decimal("0")) != sum(column_amounts, Decimal("0")):
        raise HTTPException(422, "A soma dos valores por OS deve ser igual ao total das parcelas.")
    balances = list(row_amounts)
    result = [[] for _ in balances]
    for amount in column_amounts:
        portions = apportion(amount, balances)
        for index, portion in enumerate(portions):
            result[index].append(portion)
            balances[index] -= portion
    return result


def rescale_allocations(totals, total):
    keys = sorted(totals)
    if not keys:
        return {}
    if total < len(keys) * CENT:
        raise HTTPException(422, "O total precisa reservar ao menos R$ 0,01 para cada OS vinculada.")
    amounts = apportion(total, [totals[key]["amount"] for key in keys])
    if any(value == 0 for value in amounts):
        rest = apportion(total - len(keys) * CENT, [totals[key]["amount"] for key in keys])
        amounts = [value + CENT for value in rest]
    return {key: {**totals[key], "amount": amount} for key, amount in zip(keys, amounts, strict=True)}


async def order_rows(db, ids, *, lock=False):
    if not ids:
        return {}
    query = select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.id.in_(ids)).order_by(LaboratoryWorkOrder.id)
    query = query.options(noload("*"), joinedload(LaboratoryWorkOrder.equipment)).execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update(of=LaboratoryWorkOrder)
    return {row.id: row for row in (await db.scalars(query)).all()}


@dataclass
class FinancialScope:
    entry: FinancialEntry | None
    obligation: FinancialObligation | None
    entries: list
    allocations: dict
    orders: dict


async def lock_scope(db, *, entry_id=None, obligation_id=None, additional_ids=()):
    entry = await db.get(FinancialEntry, entry_id) if entry_id is not None else None
    if entry_id is not None and (entry is None or entry.is_deleted):
        raise HTTPException(404, "Lançamento não encontrado.")
    obligation_id = obligation_id or (entry.obligation_id if entry else None)
    query = select(FinancialEntry).where(FinancialEntry.is_deleted.is_(False))
    query = query.where(FinancialEntry.obligation_id == obligation_id) if obligation_id else query.where(FinancialEntry.id == entry_id)
    query = query.order_by(FinancialEntry.id)
    initial = list((await db.scalars(query)).all())
    allocations = await raw_allocations(db, [row.id for row in initial])
    ids = set(additional_ids) | {row["work_order_id"] for rows in allocations.values() for row in rows}
    # Laboratório também bloqueia OS antes de atualizar títulos ao cancelar.
    # Todos os fluxos de edição/baixa/cronograma mantêm essa mesma ordem.
    orders = await order_rows(db, sorted(ids), lock=True)
    obligation = None
    if obligation_id:
        obligation = await db.scalar(select(FinancialObligation).where(FinancialObligation.id == obligation_id)
                                     .with_for_update().execution_options(populate_existing=True))
        if obligation is None:
            raise HTTPException(404, "Obrigação financeira não encontrada.")
    entries = list((await db.scalars(query.with_for_update().execution_options(populate_existing=True))).all())
    if not entries:
        raise HTTPException(404, "Lançamento ou parcelamento não encontrado.")
    current = await raw_allocations(db, [row.id for row in entries])
    current_ids = {row["work_order_id"] for rows in current.values() for row in rows}
    if not current_ids.issubset(ids):
        raise HTTPException(409, "Os vínculos foram alterados por outra operação. Recarregue o lançamento.")
    selected = next((row for row in entries if row.id == entry_id), None)
    if entry_id is not None and selected is None:
        raise HTTPException(409, "O lançamento foi removido. Recarregue o Financeiro.")
    return FinancialScope(selected, obligation, entries, current, orders)


def assert_versions(scope, version, obligation_version=None, *, required=False):
    if scope.entry is not None:
        if required and version is None:
            raise HTTPException(422, "Informe a versão atual do lançamento para alterar os vínculos.")
        if version is not None and version != scope.entry.version:
            raise HTTPException(409, "O lançamento foi alterado por outra operação. Recarregue antes de salvar.")
    if scope.obligation is not None:
        if required and obligation_version is None:
            raise HTTPException(422, "Informe a versão atual do parcelamento para alterar os vínculos.")
        if obligation_version is not None and obligation_version != scope.obligation.version:
            raise HTTPException(409, "O parcelamento foi alterado por outra operação. Recarregue antes de salvar.")


async def closed_periods(db, entries):
    companies = {row.company_code for row in entries}
    if not companies:
        return set()
    rows = (await db.execute(select(FinancialPeriodClosure.company_code, FinancialPeriodClosure.year, FinancialPeriodClosure.month)
                            .where(FinancialPeriodClosure.company_code.in_(companies), FinancialPeriodClosure.is_closed.is_(True)))).all()
    return set(rows)


def link_lock_reason(entries, closures):
    if any(row.entry_type != "income" for row in entries):
        return "Vínculos de OS são permitidos somente em receitas."
    if any(row.status != "pending" or row.settlement_date is not None for row in entries):
        return "Vínculos e rateios bloqueados: existe receita ou parcela baixada/cancelada. Estorne a baixa antes de alterar as OS."
    if any((row.company_code, row.posting_date.year, row.posting_date.month) in closures for row in entries):
        return "Vínculos e rateios bloqueados: existe parcela em competência fechada. Reabra o período antes de alterar as OS."
    return None


async def assert_links_editable(db, entries):
    await lock_entry_periods(db, entries)
    reason = link_lock_reason(entries, await closed_periods(db, entries))
    if reason:
        raise HTTPException(409, reason)


def link_output(row, orders):
    order = orders[row["work_order_id"]]
    compliance = row.get("billing_compliance") or {}
    return FinancialWorkOrderAllocationOutput(
        work_order_id=order.id, work_order_number=order.number, company_code=order.company_code,
        customer_id=order.customer_id, customer_name=order.customer_name,
        equipment_label=order.equipment.model or order.equipment.equipment_type or order.equipment_serial or "Equipamento",
        amount=row["amount"], version=order.version, approved_value=order.approved_value,
        exit_invoice=order.exit_invoice, exit_invoice_2=order.exit_invoice_2, exit_invoice_3=order.exit_invoice_3,
        billing_confirmation=compliance.get("confirmation"),
    )


async def entry_outputs(db, entries, *, work_order_id=None):
    if not entries:
        return []
    obligation_ids = {row.obligation_id for row in entries if row.obligation_id is not None}
    siblings = list((await db.scalars(select(FinancialEntry).where(FinancialEntry.obligation_id.in_(obligation_ids),
                     FinancialEntry.is_deleted.is_(False)))).all()) if obligation_ids else []
    all_entries = {row.id: row for row in siblings}
    all_entries.update({row.id: row for row in entries})
    allocations = await raw_allocations(db, list(all_entries))
    orders = await order_rows(db, {row["work_order_id"] for rows in allocations.values() for row in rows})
    obligations = {row.id: row for row in (await db.scalars(select(FinancialObligation).where(
                   FinancialObligation.id.in_(obligation_ids)))).all()} if obligation_ids else {}
    closures = await closed_periods(db, list(all_entries.values()))
    output = []
    for entry in entries:
        scope = [row for row in siblings if row.obligation_id == entry.obligation_id] if entry.obligation_id else [entry]
        reason = link_lock_reason(scope, closures)
        data = FinancialEntryOutput.model_validate(entry)
        data.work_orders = [link_output(row, orders) for row in sorted(allocations[entry.id], key=lambda row: row["work_order_id"]) if row["work_order_id"] in orders]
        data.work_order_links_editable, data.work_order_links_lock_reason = reason is None, reason
        if work_order_id is not None:
            data.work_order_amount = next((row.amount for row in data.work_orders if row.work_order_id == work_order_id), Decimal("0.00"))
        obligation = obligations.get(entry.obligation_id)
        if obligation is not None:
            data.obligation_version, data.obligation_total_amount = obligation.version, obligation.total_amount
            totals = aggregate_allocations(allocations, scope)
            data.obligation_work_orders = [link_output(totals[key], orders) for key in sorted(totals) if key in orders]
        output.append(data)
    return output


async def registered_totals(db, ids, *, exclude_entry_ids=()):
    if not ids:
        return {}
    rows = allocation_rows()
    query = select(rows.c.work_order_id, func.sum(rows.c.amount)).join(FinancialEntry, FinancialEntry.id == rows.c.entry_id).where(
        rows.c.work_order_id.in_(ids), FinancialEntry.entry_type == "income", FinancialEntry.is_deleted.is_(False),
        FinancialEntry.status.in_(("pending", "received")),
    )
    if exclude_entry_ids:
        query = query.where(FinancialEntry.id.not_in(exclude_entry_ids))
    return dict((await db.execute(query.group_by(rows.c.work_order_id))).all())


async def replace_allocations(db, entries, totals):
    ids = [row.id for row in entries]
    await db.execute(delete(FinancialEntryWorkOrder).where(FinancialEntryWorkOrder.entry_id.in_(ids)))
    keys = sorted(totals)
    matrix = allocation_matrix([totals[key]["amount"] for key in keys], [entry.amount for entry in entries]) if keys else []
    for column, entry in enumerate(entries):
        entry.work_order_id = keys[0] if len(keys) == 1 else None
        for row, key in enumerate(keys):
            db.add(FinancialEntryWorkOrder(entry_id=entry.id, work_order_id=key, amount=matrix[row][column],
                                          billing_compliance=totals[key].get("billing_compliance")))
    await db.flush()


def allocation_snapshot(totals):
    return [{"work_order_id": key, "amount": str(totals[key]["amount"])} for key in sorted(totals)]
