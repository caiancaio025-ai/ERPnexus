from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance.models import FinancialEntry
from app.laboratory.models import (
    LaboratoryEquipment,
    LaboratoryReleaseEvent,
    LaboratoryWorkOrder,
)
from app.laboratory.schemas import (
    TechnicianProductionBreakdown,
    TechnicianProductionPartItem,
    TechnicianProductionReport,
    TechnicianProductionRow,
    TechnicianProductionSummary,
)
from app.inventory.models import InventoryItem, InventoryMovement
from app.purchasing.material_models import MaterialRequest
from app.purchasing.material_service import MATERIAL_COST_STATUSES


REPORT_TIMEZONE = ZoneInfo("America/Recife")
ZERO = Decimal("0")


def _period_utc(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """Convert inclusive Recife business dates into a half-open UTC interval."""
    local_start = datetime.combine(start_date, time.min, tzinfo=REPORT_TIMEZONE)
    local_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=REPORT_TIMEZONE)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _money(value: object | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _gross_margin_percent(
    invoiced_total: Decimal | None,
    gross_result: Decimal | None,
) -> Decimal | None:
    if invoiced_total is None or gross_result is None or invoiced_total == ZERO:
        return None
    return (gross_result / invoiced_total) * Decimal("100")


def _equipment_label(
    equipment_type: str | None,
    manufacturer: str | None,
    model: str | None,
    serial: str | None,
) -> str:
    parts = [part.strip() for part in (equipment_type, manufacturer, model) if part and part.strip()]
    return " · ".join(parts) or serial or "Equipamento"


async def build_technician_production_report(
    db: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    technician_id: int | None,
    company_code: str | None,
    customer_id: int | None,
    include_sensitive_values: bool,
) -> TechnicianProductionReport:
    """
    Report grain: one row per work order.

    If the same work order enters "Liberado" more than once inside the selected
    period, the most recent release event in that period is the event credited
    to the report row. `release_event_count` remains available to expose how
    many release actions actually happened without double-counting equipment.
    """
    if end_date < start_date:
        raise ValueError("Data final deve ser igual ou posterior à data inicial.")

    start_utc, end_utc = _period_utc(start_date, end_date)

    ranked_releases = (
        select(
            LaboratoryReleaseEvent.id.label("release_event_id"),
            LaboratoryReleaseEvent.work_order_id.label("work_order_id"),
            LaboratoryReleaseEvent.technician_id.label("technician_id"),
            LaboratoryReleaseEvent.technician_name.label("technician_name"),
            LaboratoryReleaseEvent.released_at.label("released_at"),
            func.row_number()
            .over(
                partition_by=LaboratoryReleaseEvent.work_order_id,
                order_by=(
                    LaboratoryReleaseEvent.released_at.desc(),
                    LaboratoryReleaseEvent.id.desc(),
                ),
            )
            .label("release_rank"),
        )
        .where(
            LaboratoryReleaseEvent.released_at >= start_utc,
            LaboratoryReleaseEvent.released_at < end_utc,
        )
        .subquery("ranked_releases")
    )

    conditions = [
        ranked_releases.c.release_rank == 1,
        LaboratoryWorkOrder.is_cancelled.is_(False),
        LaboratoryWorkOrder.is_inactive.is_(False),
    ]
    if technician_id is not None:
        conditions.append(ranked_releases.c.technician_id == technician_id)
    if company_code:
        conditions.append(LaboratoryWorkOrder.company_code == company_code)
    if customer_id is not None:
        conditions.append(LaboratoryWorkOrder.customer_id == customer_id)

    release_stmt = (
        select(
            ranked_releases.c.release_event_id,
            ranked_releases.c.technician_id,
            ranked_releases.c.technician_name,
            ranked_releases.c.released_at,
            LaboratoryWorkOrder.id.label("work_order_id"),
            LaboratoryWorkOrder.number.label("work_order_number"),
            LaboratoryWorkOrder.company_code,
            LaboratoryWorkOrder.customer_id,
            LaboratoryWorkOrder.customer_name,
            LaboratoryWorkOrder.equipment_id,
            LaboratoryWorkOrder.equipment_serial,
            LaboratoryWorkOrder.parts_cost.label("canonical_parts_cost"),
            LaboratoryEquipment.equipment_type,
            LaboratoryEquipment.manufacturer,
            LaboratoryEquipment.model,
        )
        .join(
            LaboratoryWorkOrder,
            LaboratoryWorkOrder.id == ranked_releases.c.work_order_id,
        )
        .join(
            LaboratoryEquipment,
            LaboratoryEquipment.id == LaboratoryWorkOrder.equipment_id,
        )
        .where(*conditions)
        .order_by(ranked_releases.c.released_at.desc(), LaboratoryWorkOrder.id.desc())
    )
    release_rows = list((await db.execute(release_stmt)).all())

    event_conditions = [
        LaboratoryReleaseEvent.released_at >= start_utc,
        LaboratoryReleaseEvent.released_at < end_utc,
        LaboratoryWorkOrder.is_cancelled.is_(False),
        LaboratoryWorkOrder.is_inactive.is_(False),
    ]
    if technician_id is not None:
        event_conditions.append(LaboratoryReleaseEvent.technician_id == technician_id)
    if company_code:
        event_conditions.append(LaboratoryWorkOrder.company_code == company_code)
    if customer_id is not None:
        event_conditions.append(LaboratoryWorkOrder.customer_id == customer_id)

    release_event_count = int(
        await db.scalar(
            select(func.count(LaboratoryReleaseEvent.id))
            .join(
                LaboratoryWorkOrder,
                LaboratoryWorkOrder.id == LaboratoryReleaseEvent.work_order_id,
            )
            .where(*event_conditions)
        )
        or 0
    )

    work_order_ids = [int(row.work_order_id) for row in release_rows]
    finance_by_work_order: dict[int, tuple[Decimal, Decimal, Decimal]] = {}
    parts_by_work_order: dict[int, list[TechnicianProductionPartItem]] = defaultdict(list)

    # Monetary data is not queried at all for roles without sensitive-value access.
    if include_sensitive_values and work_order_ids:
        finance_rows = (
            await db.execute(
                select(
                    FinancialEntry.work_order_id,
                    func.coalesce(func.sum(FinancialEntry.amount), 0).label("invoiced_total"),
                    func.coalesce(
                        func.sum(
                            case(
                                (FinancialEntry.status == "received", FinancialEntry.amount),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("received_total"),
                    func.coalesce(
                        func.sum(
                            case(
                                (FinancialEntry.status == "pending", FinancialEntry.amount),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("receivable_total"),
                )
                .where(
                    FinancialEntry.work_order_id.in_(work_order_ids),
                    FinancialEntry.entry_type == "income",
                    FinancialEntry.is_deleted.is_(False),
                    FinancialEntry.status != "cancelled",
                )
                .group_by(FinancialEntry.work_order_id)
            )
        ).all()
        finance_by_work_order = {
            int(row.work_order_id): (
                _money(row.invoiced_total),
                _money(row.received_total),
                _money(row.receivable_total),
            )
            for row in finance_rows
            if row.work_order_id is not None
        }

        stocked_request = exists(select(InventoryMovement.id).where(
            InventoryMovement.material_request_id == MaterialRequest.id,
            InventoryMovement.kind == "receipt",
        ))
        material_rows = list((
            await db.scalars(
                select(MaterialRequest)
                .where(
                    MaterialRequest.work_order_id.in_(work_order_ids),
                    MaterialRequest.status.in_(MATERIAL_COST_STATUSES),
                    MaterialRequest.unit_cost.is_not(None),
                    ~stocked_request,
                )
                .order_by(
                    MaterialRequest.work_order_id,
                    MaterialRequest.id,
                )
            )
        ).all())

        for material in material_rows:
            if material.work_order_id is None:
                continue
            quantity = int(material.quantity or 0)
            unit_cost = _money(material.unit_cost)
            parts_by_work_order[int(material.work_order_id)].append(
                TechnicianProductionPartItem(
                    material_request_id=int(material.id),
                    code=material.code,
                    item_name=material.item_name,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    subtotal=unit_cost * quantity,
                    status=material.status,
                )
            )

        stock_rows = (await db.execute(
            select(InventoryMovement, InventoryItem.name, InventoryItem.stock_code)
            .join(InventoryItem, InventoryItem.id == InventoryMovement.item_id)
            .where(
                InventoryMovement.work_order_id.in_(work_order_ids),
                InventoryMovement.kind.in_(("issue", "return")),
            )
            .order_by(InventoryMovement.id)
        )).all()
        # Custo histórico de cada retirada e devolução; não somar a compra
        # recebida em estoque com a utilização posterior da peça na OS.
        for movement, item_name, stock_code in stock_rows:
            signed_qty = movement.quantity if movement.kind == "issue" else -movement.quantity
            unit_cost = _money(movement.unit_cost)
            parts_by_work_order[int(movement.work_order_id)].append(
                TechnicianProductionPartItem(
                    material_request_id=None,
                    code=stock_code,
                    item_name=item_name,
                    quantity=signed_qty,
                    unit_cost=unit_cost,
                    subtotal=unit_cost * signed_qty,
                    status="retirada_estoque" if signed_qty > 0 else "devolucao_estoque",
                )
            )

    items: list[TechnicianProductionRow] = []
    for row in release_rows:
        wo_id = int(row.work_order_id)
        invoiced = received = receivable = parts_cost = gross = None
        if include_sensitive_values:
            invoiced, received, receivable = finance_by_work_order.get(
                wo_id, (ZERO, ZERO, ZERO)
            )
            parts_cost = _money(row.canonical_parts_cost)
            gross = invoiced - parts_cost

        items.append(
            TechnicianProductionRow(
                release_event_id=int(row.release_event_id),
                released_at=row.released_at,
                technician_id=row.technician_id,
                technician_name=row.technician_name,
                work_order_id=wo_id,
                work_order_number=row.work_order_number,
                company_code=row.company_code,
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                equipment_id=int(row.equipment_id),
                equipment_label=_equipment_label(
                    row.equipment_type,
                    row.manufacturer,
                    row.model,
                    row.equipment_serial,
                ),
                equipment_serial=row.equipment_serial,
                invoiced_total=invoiced,
                received_total=received,
                receivable_total=receivable,
                parts_cost=parts_cost,
                parts=parts_by_work_order.get(wo_id, []) if include_sensitive_values else [],
                gross_result=gross,
                gross_margin_percent=_gross_margin_percent(invoiced, gross),
            )
        )

    released_count = len(items)
    if include_sensitive_values:
        invoiced_total = sum((item.invoiced_total or ZERO for item in items), ZERO)
        received_total = sum((item.received_total or ZERO for item in items), ZERO)
        receivable_total = sum((item.receivable_total or ZERO for item in items), ZERO)
        parts_cost_total = sum((item.parts_cost or ZERO for item in items), ZERO)
        gross_result = invoiced_total - parts_cost_total
        gross_margin_percent = _gross_margin_percent(invoiced_total, gross_result)
        average_invoice = invoiced_total / released_count if released_count else ZERO
        average_parts_cost = parts_cost_total / released_count if released_count else ZERO
    else:
        invoiced_total = received_total = receivable_total = None
        parts_cost_total = gross_result = gross_margin_percent = None
        average_invoice = average_parts_cost = None

    grouped: dict[tuple[int | None, str | None], list[TechnicianProductionRow]] = defaultdict(list)
    for item in items:
        grouped[(item.technician_id, item.technician_name)].append(item)

    by_technician: list[TechnicianProductionBreakdown] = []
    for (group_technician_id, group_technician_name), group_items in grouped.items():
        group_invoiced = group_received = group_receivable = group_parts = group_gross = None
        if include_sensitive_values:
            group_invoiced = sum(
                (item.invoiced_total or ZERO for item in group_items), ZERO
            )
            group_received = sum(
                (item.received_total or ZERO for item in group_items), ZERO
            )
            group_receivable = sum(
                (item.receivable_total or ZERO for item in group_items), ZERO
            )
            group_parts = sum((item.parts_cost or ZERO for item in group_items), ZERO)
            group_gross = group_invoiced - group_parts
            group_margin = _gross_margin_percent(group_invoiced, group_gross)
        else:
            group_margin = None

        by_technician.append(
            TechnicianProductionBreakdown(
                technician_id=group_technician_id,
                technician_name=group_technician_name,
                released_equipment_count=len(group_items),
                invoiced_total=group_invoiced,
                received_total=group_received,
                receivable_total=group_receivable,
                parts_cost_total=group_parts,
                gross_result=group_gross,
                gross_margin_percent=group_margin,
            )
        )

    by_technician.sort(
        key=lambda item: (
            -(item.released_equipment_count),
            (item.technician_name or "Sem técnico").casefold(),
        )
    )

    return TechnicianProductionReport(
        start_date=start_date,
        end_date=end_date,
        sensitive_values_visible=include_sensitive_values,
        summary=TechnicianProductionSummary(
            released_equipment_count=released_count,
            release_event_count=release_event_count,
            invoiced_total=invoiced_total,
            received_total=received_total,
            receivable_total=receivable_total,
            parts_cost_total=parts_cost_total,
            gross_result=gross_result,
            gross_margin_percent=gross_margin_percent,
            average_invoice=average_invoice,
            average_parts_cost=average_parts_cost,
        ),
        by_technician=by_technician,
        items=items,
    )
