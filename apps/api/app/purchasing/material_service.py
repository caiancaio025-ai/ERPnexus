from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.laboratory.models import LaboratoryWorkOrder
from app.purchasing.material_models import MaterialRequest, MaterialRequestEvent
from app.purchasing.material_schemas import MaterialRequestOutput

STATUS_TRANSITIONS: dict[str, set[str]] = {
    "awaiting_approval": {"approved", "rejected", "cancelled"},
    "approved": {"purchasing", "cancelled"},
    "rejected": {"awaiting_approval", "cancelled"},
    "purchasing": {"purchased", "cancelled"},
    "purchased": {"in_transit", "received", "cancelled"},
    "in_transit": {"received", "cancelled"},
    "received": {"delivered_to_lab"},
    "delivered_to_lab": set(),
    "cancelled": set(),
}

# Somente uma compra efetivamente realizada (e seus estados posteriores)
# compõe o custo de material da O.S. Solicitações em aprovação/compra não são custo.
MATERIAL_COST_STATUSES = {"purchased", "in_transit", "received", "delivered_to_lab"}


async def next_material_request_code(db: AsyncSession) -> str:
    prefix = f"SC-{date.today().year}-"
    latest = await db.scalar(
        select(MaterialRequest.code)
        .where(MaterialRequest.code.like(f"{prefix}%"))
        .order_by(MaterialRequest.id.desc())
        .limit(1)
    )
    sequence = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{sequence:04d}"


def validate_transition(previous: str, target: str) -> None:
    if previous == target:
        return
    if target not in STATUS_TRANSITIONS.get(previous, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Transição de '{previous}' para '{target}' não permitida.",
        )


def apply_status_timestamps(request: MaterialRequest, previous: str, target: str, user_id: int) -> None:
    now = datetime.now(UTC)
    if target == "approved" and previous != "approved":
        request.approved_by = user_id
        request.approved_at = now
    if target == "purchased" and previous != "purchased":
        request.purchased_at = now
    if target == "received" and previous != "received":
        request.received_at = now
    request.updated_by = user_id


def event(
    request: MaterialRequest,
    *,
    user_id: int,
    event_type: str,
    previous: str | None,
    target: str | None,
    note: str | None = None,
) -> MaterialRequestEvent:
    return MaterialRequestEvent(
        material_request_id=request.id,
        event_type=event_type,
        previous_status=previous,
        new_status=target,
        note=note,
        user_id=user_id,
    )


def material_request_total(request: MaterialRequest) -> Decimal:
    return Decimal(request.unit_cost or 0) * Decimal(request.quantity or 0)


async def recalculate_work_order_parts_cost(db: AsyncSession, work_order_id: int | None) -> Decimal | None:
    """Recalcula ``parts_cost`` pela fonte canônica: solicitações compradas.

    A agregação é idempotente: editar uma solicitação, avançar status ou repetir
    a mesma operação nunca acumula o custo duas vezes. Solicitações ainda não
    compradas não entram na soma; cancelamentos deixam de compor o total.
    """
    if work_order_id is None:
        return None

    total = await db.scalar(
        select(
            func.coalesce(
                func.sum(MaterialRequest.unit_cost * MaterialRequest.quantity),
                Decimal("0"),
            )
        ).where(
            MaterialRequest.work_order_id == work_order_id,
            MaterialRequest.status.in_(MATERIAL_COST_STATUSES),
            MaterialRequest.unit_cost.is_not(None),
        )
    )
    value = Decimal(total or 0).quantize(Decimal("0.01"))
    work_order = await db.get(LaboratoryWorkOrder, work_order_id)
    if work_order is not None:
        work_order.parts_cost = value
    return value


async def output_rows(
    db: AsyncSession,
    requests: list[MaterialRequest],
    *,
    include_sensitive_values: bool = True,
) -> list[MaterialRequestOutput]:
    if not requests:
        return []
    work_order_ids = {item.work_order_id for item in requests if item.work_order_id is not None}
    user_ids = {item.requester_user_id for item in requests}
    orders = {
        item.id: item
        for item in (
            await db.scalars(
                select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.id.in_(work_order_ids))
            )
        ).all()
    } if work_order_ids else {}
    users = {
        item.id: item.name
        for item in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()
    }
    result: list[MaterialRequestOutput] = []
    for item in requests:
        order = orders.get(item.work_order_id)
        result.append(MaterialRequestOutput(
            id=item.id,
            code=item.code,
            company_code=item.company_code,
            work_order_id=item.work_order_id,
            work_order_number=order.number if order else None,
            equipment_id=item.equipment_id,
            equipment_serial=order.equipment_serial if order else None,
            customer_name=order.customer_name if order else None,
            source_type=item.source_type,
            requester_user_id=item.requester_user_id,
            requester_name=users.get(item.requester_user_id, "Usuário"),
            item_name=item.item_name,
            quantity=item.quantity,
            priority=item.priority,
            technical_note=item.technical_note,
            suggested_link=item.suggested_link,
            status=item.status,
            supplier_name=item.supplier_name,
            purchase_reference=item.purchase_reference,
            purchase_link=item.purchase_link,
            tracking_code=item.tracking_code,
            unit_cost=item.unit_cost if include_sensitive_values else None,
            expected_delivery_date=item.expected_delivery_date,
            purchased_at=item.purchased_at,
            received_at=item.received_at,
            approved_by=item.approved_by,
            approved_at=item.approved_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        ))
    return result
