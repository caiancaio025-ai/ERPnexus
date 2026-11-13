"""Recebimento físico de Compras no estoque, dentro da transação de origem.

Cada origem registra no máximo uma entrada; todo recebimento é idempotente.
Não presume que número de série de equipamento da O.S. seja série da peça comprada.
"""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.inventory.stock_codes import format_stock_code
from app.inventory.models import InventoryComponentFormat, InventoryItem, InventoryMovement


def purchase_unit_cost(total: Decimal, quantity: int) -> Decimal:
    if quantity < 1:
        raise HTTPException(422, "Compra sem quantidade válida.")
    return (Decimal(total) / Decimal(quantity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def receive_purchase(
    db: AsyncSession, *, source: str, source_id: int, company_code: str,
    name: str, quantity: int, unit_cost: Decimal, user_id: int, source_code: str,
    linked_source_id: int | None = None,
    destination: str | None = None, target_item_id: int | None = None,
    stock_name: str | None = None, stock_mode: str | None = None,
    stock_serial: str | None = None, stock_category: str | None = None,
    stock_format_id: int | None = None,
) -> InventoryMovement:
    """Cria lote controlado no estoque; não une SKUs por nomes aproximados.

    O chamador deve travar a origem e commitar a mesma transação.
    """
    if source not in {"order", "request"}:
        raise ValueError("Origem do estoque inválida.")
    field = "purchase_order_id" if source == "order" else "material_request_id"
    existing = await db.scalar(select(InventoryMovement).where(getattr(InventoryMovement, field) == source_id))
    if existing is not None:
        return existing
    if quantity < 1:
        raise HTTPException(422, "Quantidade recebida inválida.")
    if linked_source_id is not None:
        # Uma SC vinculada explicitamente ao código de um pedido pode compartilhar
        # a mesma movimentação de entrada: jamais contabilizar o recebimento duas vezes.
        other_field = "material_request_id" if source == "order" else "purchase_order_id"
        linked = await db.scalar(select(InventoryMovement).where(
            getattr(InventoryMovement, other_field) == linked_source_id,
        ).with_for_update())
        if linked is not None:
            matched = await db.scalar(select(InventoryItem).where(
                InventoryItem.id == linked.item_id,
            ))
            if (matched is None or matched.company_code != company_code
                    or linked.quantity != quantity
                    or Decimal(linked.unit_cost) != Decimal(unit_cost)):
                raise HTTPException(409, "Pedido e solicitação vinculados não conferem em empresa, peça, quantidade ou valor. Revisar antes de receber.")
            if destination == "existing" and target_item_id != linked.item_id:
                raise HTTPException(409, "O pedido vinculado aponta para outro item de estoque.")
            if destination == "new" and (stock_name or name).strip().casefold() != matched.name.strip().casefold():
                raise HTTPException(409, "A solicitação já recebeu outra peça. Concilie antes de vincular.")
            setattr(linked, field, source_id)
            await db.flush()
            return linked
    # Todas as origens novas exigem mapeamento explícito antes do recebimento.
    # Entradas antigas, já registradas, retornam acima de forma idempotente.
    if destination not in {"new", "existing"}:
        raise HTTPException(422, "Defina o destino de estoque antes de confirmar o recebimento.")
    if destination == "existing":
        if target_item_id is None:
            raise HTTPException(422, "Selecione o item que receberá o saldo.")
        item = await db.scalar(select(InventoryItem).where(InventoryItem.id == target_item_id).with_for_update())
        if item is None or not item.is_active or item.company_code != company_code or item.mode != "bulk":
            raise HTTPException(422, "Item de estoque inexistente, de outra empresa ou não acumulável.")
        old_qty = item.quantity
        if old_qty + quantity > 1000000:
            raise HTTPException(422, "Saldo máximo de item excedido.")
        # Mantém cada preço de entrada na movimentação; atualiza o custo médio
        # atual do lote para novas baixas, sem reescrever movimentos antigos.
        amount = Decimal(item.unit_cost) * old_qty + Decimal(unit_cost) * quantity
        item.quantity = old_qty + quantity
        item.unit_cost = (amount / item.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        mode = stock_mode or "bulk"
        if mode not in {"bulk", "serialized"}:
            raise HTTPException(422, "Tipo de controle de estoque inválido.")
        serial = (stock_serial or "").strip()
        if mode == "serialized" and (quantity != 1 or not serial):
            raise HTTPException(422, "Item individual exige quantidade 1 e série obrigatória.")
        category = (stock_category or "componentes").strip().lower()
        if stock_format_id is not None:
            fmt = await db.get(InventoryComponentFormat, stock_format_id)
            if fmt is None or not fmt.is_active or fmt.category != category:
                raise HTTPException(422, "Formato técnico inválido para a categoria.")
        item = InventoryItem(
            stock_code=f"TMP-{uuid4().hex[:24]}", company_code=company_code,
            name=(stock_name or name).strip()[:220], category=category,
            format_id=stock_format_id, mode=mode, unit="UN",
            manufacturer_serial=serial if mode == "serialized" else None,
            serial_normalized=serial.upper() if mode == "serialized" else None,
            quantity=quantity, unit_cost=Decimal(unit_cost),
            notes=f"Recebimento automático de Compras: {source_code}"[:4000],
            created_by=user_id,
        )
        if len(item.name) < 2:
            raise HTTPException(422, "Informe o nome que será usado no estoque.")
        db.add(item)
        try:
            await db.flush()
        except IntegrityError:
            # A transação do pedido será revertida pelo gerenciador de sessão.
            # Impede erro 500 por número de série duplicado.
            raise HTTPException(409, "Número de série já registrado ou conflito no cadastro do item.") from None
        item.stock_code = format_stock_code(item.id)
    movement = InventoryMovement(
        item_id=item.id, kind="receipt", quantity=quantity,
        unit_cost=Decimal(unit_cost), user_id=user_id,
        note=f"Recebimento automático de Compras: {source_code}"[:500],
        **{field: source_id},
    )
    db.add(movement)
    await db.flush()
    return movement
