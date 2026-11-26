"""Recebimento físico de Compras no estoque, dentro da transação de origem.

Cada origem registra um grupo atômico de entradas; todo recebimento é idempotente.
Não presume que número de série de equipamento da O.S. seja série da peça comprada.
"""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.inventory.stock_codes import format_stock_code
from app.inventory.item_details import canonical_inventory_details
from app.inventory.models import InventoryItem, InventoryLocationHistory, InventoryMovement
from app.inventory.validation import valid_category, valid_company, valid_format, valid_slot, valid_subtype

MAX_INDIVIDUAL_RECEIPT = 1000


async def _receipt_group(db: AsyncSession, field: str, source_id: int) -> list[InventoryMovement]:
    return list((await db.scalars(select(InventoryMovement).where(
        getattr(InventoryMovement, field) == source_id,
    ).order_by(InventoryMovement.receipt_unit_index, InventoryMovement.id)
        .with_for_update().execution_options(populate_existing=True))).all())


async def _validate_group(
    db: AsyncSession, rows: list[InventoryMovement], *, company_code: str,
    quantity: int, unit_cost: Decimal,
) -> dict[int, InventoryItem]:
    """Confere o grupo completo, inclusive unidades já consumidas/devolvidas.

    O saldo atual não representa a quantidade recebida: usa-se o histórico
    imutável das entradas para conciliar PC/SC após a utilização de uma peça.
    """
    items = {item.id: item for item in (await db.scalars(select(InventoryItem).where(
        InventoryItem.id.in_([row.item_id for row in rows]),
    ))).all()}
    valid = (
        len(items) == len(rows)
        and [row.receipt_unit_index for row in rows] == list(range(1, len(rows) + 1))
        and sum(row.quantity for row in rows) == quantity
        and all(row.kind == "receipt" and Decimal(row.unit_cost) == Decimal(unit_cost) for row in rows)
        and all(item.company_code == company_code for item in items.values())
    )
    modes = {item.mode for item in items.values()}
    if modes == {"serialized"}:
        valid = valid and len(rows) == quantity and all(row.quantity == 1 for row in rows)
    elif modes == {"bulk"}:
        valid = valid and len(rows) == 1
    else:
        valid = False
    for field in ("purchase_order_id", "material_request_id"):
        valid = valid and len({getattr(row, field) for row in rows}) == 1
    if not valid:
        raise HTTPException(409, "O recebimento não confere em empresa, quantidade, valor ou unidades. Concilie os registros antes de receber.")
    return items


async def lock_purchase_receipts(db: AsyncSession) -> None:
    """Serializa a conciliação pedido/solicitação antes de travar suas origens.

    Uma origem pode chegar ao estoque por qualquer um dos dois módulos. Sem
    este lock, dois recebimentos simultâneos não enxergam o movimento ainda
    não confirmado do outro e criam duas entradas físicas para a mesma compra.
    Deve ser chamado antes de SELECT FOR UPDATE do pedido ou da solicitação.
    """
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(1397051988, 1)))


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
    stock_details: dict | None = None,
) -> InventoryMovement:
    """Cria lote ou unidades individuais com códigos EST gerados pelo banco.

    O chamador deve travar a origem e commitar a mesma transação.
    Retorna a primeira entrada para compatibilidade dos chamadores legados;
    a idempotência e a conciliação sempre consideram o grupo inteiro.
    """
    if source not in {"order", "request"}:
        raise ValueError("Origem do estoque inválida.")
    field = "purchase_order_id" if source == "order" else "material_request_id"
    other_field = "material_request_id" if source == "order" else "purchase_order_id"
    if quantity < 1:
        raise HTTPException(422, "Quantidade recebida inválida.")
    serial = (stock_serial or "").strip() or None
    if destination == "new" and stock_mode == "serialized":
        if quantity > MAX_INDIVIDUAL_RECEIPT:
            raise HTTPException(422, "Recebimento individual permite até 1.000 unidades; use controle por quantidade para quantidades maiores.")
        if quantity > 1 and serial:
            raise HTTPException(422, "Uma série de fabricante identifica apenas uma unidade. Para várias unidades, deixe a série em branco e informe-a depois por item no Estoque.")
    existing = await _receipt_group(db, field, source_id)
    if existing:
        await _validate_group(db, existing, company_code=company_code, quantity=quantity, unit_cost=unit_cost)
        if linked_source_id is not None and any(getattr(row, other_field) not in (None, linked_source_id) for row in existing):
            raise HTTPException(409, "Este recebimento já está vinculado a outra compra ou solicitação.")
        return existing[0]
    if linked_source_id is not None:
        # Uma SC vinculada explicitamente ao código de um pedido pode compartilhar
        # o grupo inteiro: jamais contabilizar o recebimento duas vezes.
        linked = await _receipt_group(db, other_field, linked_source_id)
        if linked:
            if any(getattr(row, field) not in (None, source_id) for row in linked):
                raise HTTPException(
                    409,
                    "Este recebimento já está vinculado a outra compra ou solicitação. "
                    "Concilie a referência antes de receber.",
                )
            items = await _validate_group(db, linked, company_code=company_code, quantity=quantity, unit_cost=unit_cost)
            if destination == "existing" and (len(linked) != 1 or target_item_id != linked[0].item_id or items[linked[0].item_id].mode != "bulk"):
                raise HTTPException(409, "O pedido vinculado aponta para outro item de estoque.")
            if destination == "new":
                if any((stock_name or name).strip().casefold() != item.name.strip().casefold() for item in items.values()):
                    raise HTTPException(409, "A solicitação já recebeu outra peça. Concilie antes de vincular.")
                if stock_mode is not None and any(item.mode != stock_mode for item in items.values()):
                    raise HTTPException(409, "Pedido e solicitação utilizam controles de estoque diferentes.")
                if serial and any(item.serial_normalized != serial.upper() for item in items.values()):
                    raise HTTPException(409, "A série informada difere da unidade já recebida. Concilie a identificação no Estoque antes de vincular.")
                if stock_details is not None:
                    details = canonical_inventory_details(stock_details)
                    # Compare the original receipt plan, not mutable stock
                    # metadata (an item may already have moved to another slot).
                    from app.purchasing.material_models import MaterialRequest
                    from app.purchasing.models import PurchaseOrder
                    origin_model = PurchaseOrder if source == "request" else MaterialRequest
                    original_source = await db.get(origin_model, linked_source_id)
                    original_details = getattr(original_source, "inventory_details", None)
                    reference = (canonical_inventory_details(original_details) if original_details is not None
                                 else {key: getattr(next(iter(items.values())), key) for key in details})
                    for key, value in details.items():
                        if value is not None and reference[key] != value:
                            raise HTTPException(409, "Os detalhes informados diferem do item já recebido pela compra vinculada. Confira o cadastro no Estoque antes de vincular.")
            for row in linked:
                setattr(row, field, source_id)
            await db.flush()
            return linked[0]
    # Todas as origens novas exigem mapeamento explícito antes do recebimento.
    # Entradas antigas, já registradas, retornam acima de forma idempotente.
    if destination not in {"new", "existing"}:
        raise HTTPException(422, "Defina o destino de estoque antes de confirmar o recebimento.")
    if destination == "existing":
        if target_item_id is None:
            raise HTTPException(422, "Selecione o item que receberá o saldo.")
        item = await db.scalar(select(InventoryItem).where(
            InventoryItem.id == target_item_id,
        ).with_for_update().execution_options(populate_existing=True))
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
        category = (stock_category or "componentes").strip().lower()
        details = canonical_inventory_details(stock_details)
        await valid_company(db, company_code)
        await valid_category(db, category)
        await valid_subtype(db, details["subtype_id"], category)
        await valid_format(db, stock_format_id, category)
        slot = await valid_slot(db, details["slot_id"])
        item_name = (stock_name or name).strip()[:220]
        if len(item_name) < 2:
            raise HTTPException(422, "Informe o nome que será usado no estoque.")
        # Um flush para todos os IDs, depois um flush para códigos/movimentos.
        # Não há consulta nem transação por unidade; a origem confirma tudo junto.
        units = quantity if mode == "serialized" else 1
        items = [InventoryItem(
            stock_code=f"TMP-{uuid4().hex[:24]}", company_code=company_code,
            name=item_name, category=category, format_id=stock_format_id, mode=mode,
            **{key: value for key, value in details.items() if key != "notes"},
            manufacturer_serial=serial if mode == "serialized" else None,
            serial_normalized=serial.upper() if mode == "serialized" and serial else None,
            quantity=1 if mode == "serialized" else quantity, unit_cost=Decimal(unit_cost),
            notes=details["notes"] if stock_details is not None else f"Recebimento automático de Compras: {source_code}"[:4000],
            created_by=user_id,
        ) for _ in range(units)]
        db.add_all(items)
        try:
            await db.flush()
            for item in items:
                item.stock_code = format_stock_code(item.id)
            if slot is not None:
                db.add_all([InventoryLocationHistory(
                    item_id=item.id, new_slot_id=slot.id, new_slot_code=slot.code, moved_by=user_id,
                ) for item in items])
            movements = [InventoryMovement(
                item_id=item.id, kind="receipt", quantity=item.quantity,
                receipt_unit_index=index, unit_cost=Decimal(unit_cost), user_id=user_id,
                note=f"Recebimento automático de Compras: {source_code}"[:500], **{field: source_id},
            ) for index, item in enumerate(items, 1)]
            db.add_all(movements)
            await db.flush()
        except IntegrityError:
            # A transação do pedido será revertida pelo gerenciador de sessão.
            # Impede erro 500 por número de série duplicado.
            raise HTTPException(409, "Número de série já registrado ou conflito no cadastro do item.") from None
        return movements[0]
    movement = InventoryMovement(
        item_id=item.id, kind="receipt", quantity=quantity,
        unit_cost=Decimal(unit_cost), user_id=user_id,
        note=f"Recebimento automático de Compras: {source_code}"[:500],
        **{field: source_id},
    )
    db.add(movement)
    await db.flush()
    return movement
