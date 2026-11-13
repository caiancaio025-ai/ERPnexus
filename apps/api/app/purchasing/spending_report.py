from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.laboratory.models import LaboratoryWorkOrder
from app.purchasing.material_models import MaterialRequest
from app.purchasing.material_service import MATERIAL_COST_STATUSES
from app.purchasing.models import PurchaseOrder
from app.purchasing.schemas import (
    PurchaseSpendingBreakdown,
    PurchaseSpendingItem,
    PurchaseSpendingMonth,
    PurchaseSpendingReport,
    PurchaseSpendingSummary,
)

REPORT_TIMEZONE = ZoneInfo("America/Recife")
ZERO = Decimal("0.00")


def _money(value: Decimal | int | float | None) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _material_period_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, time.min, tzinfo=REPORT_TIMEZONE).astimezone(UTC)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=REPORT_TIMEZONE).astimezone(UTC)
    return start, end


async def build_purchase_spending_report(
    db: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    company_code: str | None = None,
    supplier: str | None = None,
) -> PurchaseSpendingReport:
    """Consolida os dois fluxos reais de compra do NEXUS.

    PurchaseOrder é o registro canônico das compras lançadas diretamente no
    módulo de Compras. MaterialRequest é o registro canônico das compras de
    materiais originadas por solicitação (O.S. ou avulsa). Os fluxos não têm
    chave relacional comum; por isso cada linha mantém explicitamente sua
    origem e não existe deduplicação heurística.
    """

    if end_date < start_date:
        raise ValueError("A data final não pode ser anterior à data inicial.")

    items: list[PurchaseSpendingItem] = []

    # Compras lançadas diretamente: todo pedido não cancelado e não excluído
    # é um compromisso de compra já registrado com purchase_date e valor total.
    purchase_query = select(PurchaseOrder).where(
        PurchaseOrder.is_deleted.is_(False),
        PurchaseOrder.status != "cancelled",
        PurchaseOrder.purchase_date >= start_date,
        PurchaseOrder.purchase_date <= end_date,
    )
    if company_code:
        purchase_query = purchase_query.where(PurchaseOrder.company_code == company_code)
    if supplier:
        purchase_query = purchase_query.where(PurchaseOrder.supplier_name.ilike(f"%{supplier.strip()}%"))

    purchases = list((await db.scalars(
        purchase_query.order_by(PurchaseOrder.purchase_date, PurchaseOrder.id)
    )).all())

    linked_work_order_ids = {
        item.laboratory_work_order_id
        for item in purchases
        if item.laboratory_work_order_id is not None
    }

    # Material requests only become actual spend at "purchased" or later.
    material_start, material_end = _material_period_bounds(start_date, end_date)
    material_query = select(MaterialRequest).where(
        MaterialRequest.status.in_(MATERIAL_COST_STATUSES),
        MaterialRequest.unit_cost.is_not(None),
        MaterialRequest.purchased_at.is_not(None),
        MaterialRequest.purchased_at >= material_start,
        MaterialRequest.purchased_at < material_end,
    )
    if company_code:
        material_query = material_query.where(MaterialRequest.company_code == company_code)
    if supplier:
        material_query = material_query.where(MaterialRequest.supplier_name.ilike(f"%{supplier.strip()}%"))

    materials = list((await db.scalars(
        material_query.order_by(MaterialRequest.purchased_at, MaterialRequest.id)
    )).all())

    linked_work_order_ids.update(
        item.work_order_id for item in materials if item.work_order_id is not None
    )

    work_orders = {}
    if linked_work_order_ids:
        work_orders = {
            item.id: item
            for item in (await db.scalars(
                select(LaboratoryWorkOrder).where(
                    LaboratoryWorkOrder.id.in_(linked_work_order_ids)
                )
            )).all()
        }

    for purchase in purchases:
        work_order = work_orders.get(purchase.laboratory_work_order_id)
        items.append(
            PurchaseSpendingItem(
                source="purchase_order",
                source_id=purchase.id,
                code=purchase.code,
                company_code=purchase.company_code,
                purchase_date=purchase.purchase_date,
                supplier_name=purchase.supplier_name,
                item_name=purchase.product_name,
                quantity=purchase.quantity,
                amount=_money(purchase.total_amount),
                status=purchase.status,
                work_order_id=purchase.laboratory_work_order_id,
                work_order_number=work_order.number if work_order else None,
                customer_name=(
                    work_order.customer_name
                    if work_order
                    else purchase.client_destination
                ),
                equipment_serial=(
                    work_order.equipment_serial
                    if work_order and work_order.equipment_serial
                    else purchase.equipment_serial
                ),
                purchase_reference=purchase.invoice_number or purchase.code,
            )
        )

    for material in materials:
        work_order = work_orders.get(material.work_order_id)
        purchased_date = material.purchased_at.astimezone(REPORT_TIMEZONE).date()
        items.append(
            PurchaseSpendingItem(
                source="material_request",
                source_id=material.id,
                code=material.code,
                company_code=material.company_code,
                purchase_date=purchased_date,
                supplier_name=material.supplier_name or "Fornecedor não informado",
                item_name=material.item_name,
                quantity=material.quantity,
                amount=_money(material.unit_cost) * Decimal(material.quantity or 0),
                status=material.status,
                work_order_id=material.work_order_id,
                work_order_number=work_order.number if work_order else None,
                customer_name=work_order.customer_name if work_order else None,
                equipment_serial=work_order.equipment_serial if work_order else None,
                purchase_reference=material.purchase_reference,
            )
        )

    items.sort(key=lambda item: (item.purchase_date, item.code), reverse=True)

    purchase_order_total = sum(
        (item.amount for item in items if item.source == "purchase_order"),
        ZERO,
    )
    material_request_total = sum(
        (item.amount for item in items if item.source == "material_request"),
        ZERO,
    )
    total_spent = purchase_order_total + material_request_total

    by_supplier_amount: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_supplier_count: dict[str, int] = defaultdict(int)
    by_source_amount: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_source_count: dict[str, int] = defaultdict(int)
    by_month_amount: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_month_count: dict[str, int] = defaultdict(int)

    for item in items:
        supplier_name = item.supplier_name or "Fornecedor não informado"
        by_supplier_amount[supplier_name] += item.amount
        by_supplier_count[supplier_name] += 1
        by_source_amount[item.source] += item.amount
        by_source_count[item.source] += 1
        month_key = item.purchase_date.strftime("%Y-%m")
        by_month_amount[month_key] += item.amount
        by_month_count[month_key] += 1

    by_supplier = [
        PurchaseSpendingBreakdown(
            key=key,
            label=key,
            count=by_supplier_count[key],
            amount=amount,
        )
        for key, amount in sorted(
            by_supplier_amount.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )
    ]
    by_source = [
        PurchaseSpendingBreakdown(
            key=key,
            label=(
                "Pedidos de compra"
                if key == "purchase_order"
                else "Solicitações de material"
            ),
            count=by_source_count[key],
            amount=amount,
        )
        for key, amount in sorted(
            by_source_amount.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )
    ]
    by_month = [
        PurchaseSpendingMonth(
            month=key,
            count=by_month_count[key],
            amount=by_month_amount[key],
        )
        for key in sorted(by_month_amount)
    ]

    return PurchaseSpendingReport(
        start_date=start_date,
        end_date=end_date,
        company_code=company_code,
        summary=PurchaseSpendingSummary(
            purchase_count=len(items),
            total_spent=_money(total_spent),
            purchase_order_total=_money(purchase_order_total),
            material_request_total=_money(material_request_total),
            average_purchase=_money(total_spent / len(items)) if items else ZERO,
        ),
        by_supplier=by_supplier,
        by_source=by_source,
        by_month=by_month,
        items=items,
    )
