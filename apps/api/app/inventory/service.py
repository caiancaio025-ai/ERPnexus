"""Regra canônica de quantidade e custo consumido; transações protegidas por lock."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inventory.models import InventoryItem, InventoryMovement
from app.laboratory.models import LaboratoryWorkOrder


def stock_balance_after(mode: str, balance: int, amount: int, *, consume: bool) -> int:
    if amount <= 0 or int(amount) != amount:
        raise HTTPException(status_code=422, detail="A quantidade deve ser um inteiro positivo.")
    if mode == "serialized" and amount != 1:
        raise HTTPException(status_code=422, detail="Item por série permite apenas uma unidade.")
    remaining = balance - amount if consume else balance + amount
    if remaining < 0 or (mode == "serialized" and remaining > 1):
        raise HTTPException(status_code=409, detail="Quantidade indisponível para essa movimentação.")
    return remaining


async def consumed_cost(db: AsyncSession, work_order_id: int) -> Decimal:
    """Movimentos imutáveis: saídas adicionam custo, devoluções removem custo."""
    multiplier = case(
        (InventoryMovement.kind == "issue", 1),
        (InventoryMovement.kind == "return", -1),
        else_=0,
    )
    total = await db.scalar(
        select(func.coalesce(func.sum(
            InventoryMovement.quantity * InventoryMovement.unit_cost * multiplier
        ), 0)).where(InventoryMovement.work_order_id == work_order_id)
    )
    return Decimal(total or 0).quantize(Decimal("0.01"))


async def move_stock(
    db: AsyncSession, *, item_id: int, quantity: int, kind: str,
    user_id: int, work_order_id: int | None = None,
    reversal_of_id: int | None = None, note: str | None = None,
) -> InventoryMovement:
    item = await db.scalar(select(InventoryItem).where(InventoryItem.id == item_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    if not item.is_active:
        raise HTTPException(status_code=409, detail="Item inativo.")
    if kind not in ("receipt", "issue", "return"):
        raise HTTPException(status_code=422, detail="Movimentação inválida.")
    if kind in {"issue", "return"}:
        work_order = await db.scalar(select(LaboratoryWorkOrder).where(
            LaboratoryWorkOrder.id == work_order_id
        ).with_for_update(of=LaboratoryWorkOrder))
        if work_order is None or work_order.is_cancelled:
            raise HTTPException(status_code=404, detail="O.S. inexistente ou cancelada.")
        if work_order.company_code != item.company_code:
            raise HTTPException(status_code=409, detail="A empresa da O.S. difere da empresa do estoque.")
    else:
        if work_order_id is not None:
            raise HTTPException(status_code=422, detail="Recebimento não pode ser vinculado a O.S.")

    unit_cost = item.unit_cost
    if kind == "return":
        original = await db.scalar(
            select(InventoryMovement).where(InventoryMovement.id == reversal_of_id).with_for_update()
        )
        if original is None or original.kind != "issue" or original.item_id != item_id or original.work_order_id != work_order_id:
            raise HTTPException(status_code=409, detail="Saída original inválida para devolução.")
        returned = await db.scalar(select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
            InventoryMovement.reversal_of_id == original.id,
            InventoryMovement.kind == "return",
        ))
        if Decimal(returned or 0) + quantity > original.quantity:
            raise HTTPException(status_code=409, detail="Quantidade devolvida excede a saída original.")
        unit_cost = original.unit_cost

    item.quantity = stock_balance_after(item.mode, item.quantity, quantity, consume=kind == "issue")
    movement = InventoryMovement(
        item_id=item_id, work_order_id=work_order_id, kind=kind, quantity=quantity,
        unit_cost=unit_cost, reversal_of_id=reversal_of_id, user_id=user_id, note=note,
    )
    db.add(movement)
    await db.flush()
    if work_order_id is not None:
        from app.purchasing.material_service import recalculate_work_order_parts_cost
        await recalculate_work_order_parts_cost(db, work_order_id)
    return movement
