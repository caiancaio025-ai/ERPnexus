"""Individual receipts inherit the full purchase quantity and preserve its history."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.inventory.models import InventoryItem, InventoryMovement
from app.inventory.purchase_cycle import receive_purchase
from app.inventory.service import move_stock
from app.inventory.stock_codes import format_stock_code
from app.purchasing import router as purchasing
from app.purchasing.material_models import MaterialRequest
from app.purchasing.material_schemas import MaterialRequestUpdate
from app.purchasing.models import PurchaseOrder
from app.purchasing.schemas import PurchaseUpdate
from test_purchasing_save_reliability_v48 import context, material, order_payload  # noqa: F401


async def receipts(db, **source):
    statement = select(InventoryMovement).where(InventoryMovement.kind == "receipt")
    for field, value in source.items():
        statement = statement.where(getattr(InventoryMovement, field) == value)
    return list((await db.scalars(statement.order_by(InventoryMovement.receipt_unit_index))).all())


@pytest.mark.asyncio
async def test_ten_individual_units_generate_ten_codes_and_reediting_is_idempotent(context):
    db, user, supplier, _ = context
    payload = order_payload(supplier.id, quantity=10, total_amount=Decimal("45.50"),
                            inventory_mode="serialized", inventory_serial=None, status="delivered")
    created = await purchasing.create_order(payload, user, db)
    for _ in range(2):
        saved = await purchasing.update_order(created.id, PurchaseUpdate(**{
            **payload.model_dump(), "notes": "Conferido sem série OEM",
        }), user, db)
        assert saved.quantity == 10
    rows = await receipts(db, purchase_order_id=created.id)
    items = list((await db.scalars(select(InventoryItem).order_by(InventoryItem.id))).all())
    assert len(rows) == len(items) == 10
    assert [row.receipt_unit_index for row in rows] == list(range(1, 11))
    assert all(row.quantity == 1 and row.unit_cost == Decimal("4.55") for row in rows)
    assert sum(row.quantity * row.unit_cost for row in rows) == Decimal("45.50")
    assert len({item.stock_code for item in items}) == 10
    assert all(item.stock_code == format_stock_code(item.id) and item.quantity == 1 for item in items)
    assert all(item.manufacturer_serial is None and item.serial_normalized is None for item in items)


@pytest.mark.asyncio
async def test_individual_group_can_link_after_consumption_and_returns_keep_historical_cost(context):
    db, user, _, order = context
    request = await material(db, user, order, status="purchased", quantity=10,
                             inventory_destination="new", inventory_name="Resistor 1k",
                             inventory_mode="serialized")
    await purchasing.update_material_request(request.id, MaterialRequestUpdate(status="received"), user, db)
    rows = await receipts(db, material_request_id=request.id)
    await db.refresh(order)
    assert order.parts_cost == Decimal("0.00")
    first = await move_stock(db, item_id=rows[0].item_id, quantity=1, kind="issue", user_id=user.id, work_order_id=order.id)
    await move_stock(db, item_id=rows[1].item_id, quantity=1, kind="issue", user_id=user.id, work_order_id=order.id)
    assert order.parts_cost == Decimal("25.00")
    # A purchase can be reconciled after a unit has already left the stock.
    await receive_purchase(db, source="order", source_id=987, linked_source_id=request.id,
                           source_code="PC-LINK", company_code=request.company_code,
                           name=request.item_name, quantity=10, unit_cost=Decimal("12.50"), user_id=user.id,
                           destination="new", stock_name=request.inventory_name, stock_mode="serialized")
    assert all(row.purchase_order_id == 987 for row in await receipts(db, material_request_id=request.id))
    item = await db.get(InventoryItem, rows[0].item_id)
    item.unit_cost = Decimal("99.00")
    await db.flush()
    returned = await move_stock(db, item_id=item.id, quantity=1, kind="return", user_id=user.id,
                                work_order_id=order.id, reversal_of_id=first.id)
    assert returned.unit_cost == Decimal("12.50")
    assert order.parts_cost == Decimal("12.50")
    assert item.quantity == 1
    assert await db.scalar(select(func.sum(InventoryItem.quantity))) == 9
    assert len(await receipts(db, material_request_id=request.id)) == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity,serial", [(10, "UMA-SERIE-PARA-TODAS"), (1001, None)])
async def test_invalid_individual_receipt_creates_no_partial_units_or_status(context, quantity, serial):
    db, user, _, order = context
    request = await material(db, user, order, status="purchased", quantity=quantity,
                             inventory_destination="new", inventory_name="Fita adesiva",
                             inventory_mode="serialized", inventory_serial=serial)
    request_id = request.id
    with pytest.raises(HTTPException) as error:
        await purchasing.update_material_request(request_id, MaterialRequestUpdate(status="received"), user, db)
    assert error.value.status_code == 422
    await db.rollback()
    assert (await db.get(MaterialRequest, request_id)).status == "purchased"
    assert await db.scalar(select(func.count()).select_from(InventoryItem)) == 0
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 0


@pytest.mark.asyncio
async def test_error_after_all_units_were_created_rolls_back_purchase_and_entire_group(context, monkeypatch):
    db, user, supplier, _ = context
    async def fail_activity(*args, **kwargs):
        assert await db.scalar(select(func.count()).select_from(InventoryItem)) == 10
        assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 10
        raise RuntimeError("Simulated failure after receipt group")
    monkeypatch.setattr(purchasing, "purchase_order_activity", fail_activity)
    with pytest.raises(RuntimeError, match="after receipt group"):
        await purchasing.create_order(order_payload(supplier.id, status="delivered", quantity=10,
                                     inventory_mode="serialized"), user, db)
    await db.rollback()
    assert await db.scalar(select(func.count()).select_from(PurchaseOrder)) == 0
    assert await db.scalar(select(func.count()).select_from(InventoryItem)) == 0
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["quantity", "mode", "unit_cost"])
async def test_linked_request_must_match_the_entire_received_group(context, mismatch):
    db, user, supplier, order = context
    purchase = await purchasing.create_order(order_payload(supplier.id, status="delivered", quantity=10,
        total_amount=Decimal("125.00"), inventory_mode="serialized"), user, db)
    values = dict(status="purchased", quantity=10, purchase_reference=purchase.code,
                  inventory_destination="new", inventory_name=purchase.inventory_name, inventory_mode="serialized")
    values[{"quantity": "quantity", "mode": "inventory_mode", "unit_cost": "unit_cost"}[mismatch]] = {
        "quantity": 9, "mode": "bulk", "unit_cost": Decimal("12.51"),
    }[mismatch]
    request = await material(db, user, order, **values)
    request_id, purchase_id = request.id, purchase.id
    with pytest.raises(HTTPException) as error:
        await purchasing.update_material_request(request_id, MaterialRequestUpdate(status="received"), user, db)
    assert error.value.status_code == 409
    await db.rollback()
    assert (await db.get(MaterialRequest, request_id)).status == "purchased"
    rows = await receipts(db, purchase_order_id=purchase_id)
    assert len(rows) == 10 and all(row.material_request_id is None for row in rows)
    assert await db.scalar(select(func.count()).select_from(InventoryItem)) == 10


@pytest.mark.asyncio
async def test_linked_material_request_cannot_rewrite_its_physical_purchase_reference(context):
    db, user, supplier, order = context
    purchase = await purchasing.create_order(order_payload(supplier.id, status="delivered", quantity=10,
        total_amount=Decimal("125.00"), inventory_mode="serialized"), user, db)
    request = await material(db, user, order, status="purchased", quantity=10,
        inventory_destination="new", inventory_name=purchase.inventory_name,
        inventory_mode="serialized", purchase_reference=purchase.code)
    await purchasing.update_material_request(request.id, MaterialRequestUpdate(status="received"), user, db)
    for reference in (None, "PC-DIFERENTE"):
        with pytest.raises(HTTPException) as error:
            await purchasing.update_material_request(request.id, MaterialRequestUpdate(
                status="received", purchase_reference=reference,
            ), user, db)
        assert error.value.status_code == 409
    edited = await purchasing.update_material_request(request.id, MaterialRequestUpdate(
        status="received", purchase_reference=purchase.code, tracking_code="Conferido",
    ), user, db)
    assert edited.purchase_reference == purchase.code
    rows = await receipts(db, material_request_id=request.id)
    assert len(rows) == 10 and all(row.purchase_order_id == purchase.id for row in rows)


@pytest.mark.asyncio
async def test_linked_single_unit_does_not_silently_discard_a_conflicting_oem_serial(context):
    db, user, supplier, order = context
    purchase = await purchasing.create_order(order_payload(supplier.id, status="delivered", quantity=1,
        total_amount=Decimal("12.50"), inventory_mode="serialized", inventory_serial="OEM-CORRETO"), user, db)
    request = await material(db, user, order, status="purchased", quantity=1,
        inventory_destination="new", inventory_name=purchase.inventory_name,
        inventory_mode="serialized", inventory_serial="OEM-DIFERENTE", purchase_reference=purchase.code)
    purchase_id, request_id = purchase.id, request.id
    with pytest.raises(HTTPException) as error:
        await purchasing.update_material_request(request_id, MaterialRequestUpdate(status="received"), user, db)
    assert error.value.status_code == 409
    await db.rollback()
    rows = await receipts(db, purchase_order_id=purchase_id)
    assert len(rows) == 1 and rows[0].material_request_id is None
    assert (await db.get(InventoryItem, rows[0].item_id)).manufacturer_serial == "OEM-CORRETO"
    assert (await db.get(MaterialRequest, request_id)).status == "purchased"
