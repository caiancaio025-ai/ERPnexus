"""Eventos operacionais transacionais do histórico interno do SÊNTICO.

Não inclui valores comerciais/financeiros em notificações compartilhadas.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.notifications.service import notify_activity


def _equipment_label(equipment) -> str | None:
    if not equipment:
        return None
    pieces = [getattr(equipment, name, None) for name in ("equipment_type", "manufacturer", "model")]
    return " · ".join(str(part).strip() for part in pieces if part and str(part).strip()) or None


async def work_order_activity(
    db: AsyncSession, *, actor: User, work_order, action: str,
    title: str, message: str, module: str = "laboratorio", severity: str = "info",
    details: str | None = None, target: str | None = None,
    exclude_roles: set[str] | None = None,
) -> None:
    from app.laboratory.models import LaboratoryEquipment
    equipment = await db.get(LaboratoryEquipment, work_order.equipment_id)
    await notify_activity(
        db, actor=actor, activity_module=module, action=action,
        title=title, message=message, details=details, severity=severity,
        target=target or f"/laboratorio?os={work_order.id}",
        entity_type="laboratory_work_order", entity_id=work_order.id,
        work_order_id=work_order.id, work_order_number=work_order.number,
        equipment_name=_equipment_label(equipment), exclude_roles=exclude_roles,
    )


async def material_request_activity(
    db: AsyncSession, *, actor: User, request, action: str,
    title: str, message: str, severity: str = "info", details: str | None = None,
) -> None:
    from app.laboratory.models import LaboratoryEquipment, LaboratoryWorkOrder
    order = await db.get(LaboratoryWorkOrder, request.work_order_id) if request.work_order_id else None
    equipment = await db.get(LaboratoryEquipment, order.equipment_id) if order else None
    await notify_activity(
        db, actor=actor, activity_module="compras", action=action,
        title=title, message=message, severity=severity, details=details,
        target=(f"/laboratorio?os={order.id}&aba=materials" if order else "/compras?view=requests"),
        entity_type="material_request", entity_id=request.id,
        work_order_id=order.id if order else None,
        work_order_number=order.number if order else None,
        equipment_name=_equipment_label(equipment),
    )


async def purchase_order_activity(
    db: AsyncSession, *, actor: User, purchase, action: str,
    title: str, message: str, severity: str = "info",
) -> None:
    from app.laboratory.models import LaboratoryEquipment, LaboratoryWorkOrder
    order = await db.get(LaboratoryWorkOrder, purchase.laboratory_work_order_id) if purchase.laboratory_work_order_id else None
    equipment_id = purchase.laboratory_equipment_id or (order.equipment_id if order else None)
    equipment = await db.get(LaboratoryEquipment, equipment_id) if equipment_id else None
    await notify_activity(
        db, actor=actor, activity_module="compras", action=action,
        title=title, message=message, severity=severity,
        target=f"/compras?order={purchase.id}",
        entity_type="purchase_order", entity_id=purchase.id,
        work_order_id=order.id if order else None,
        work_order_number=order.number if order else None,
        equipment_name=_equipment_label(equipment),
    )
