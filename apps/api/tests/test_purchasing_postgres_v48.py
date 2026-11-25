"""Concurrent HTTP regressions against an explicitly enabled disposable PostgreSQL.

These tests require postgres_client from conftest: a real authenticated cookie,
the production session dependency and a database migrated with Alembic.
"""
import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, or_, select

from app.core.db import session_factory
from app.inventory.models import InventoryItem, InventoryMovement
from app.purchasing.material_models import MaterialRequest
from app.purchasing.models import PurchaseOrder


async def create_supplier(client):
    response = await client.post("/purchasing/suppliers", json={
        "name": f"Fornecedor PG {uuid4().hex}", "origin": "national",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def purchase_payload(supplier_id, **changes):
    tag = uuid4().hex
    body = {
        "company_code": "universo_eletronica", "supplier_id": supplier_id,
        "product_name": f"Compra concorrente {tag}", "quantity": 4,
        "total_amount": "50.00", "purchase_date": date.today().isoformat(),
        "estimated_delivery_date": (date.today() + timedelta(days=2)).isoformat(),
        "status": "ordered", "inventory_destination": "new",
        "inventory_name": f"Componente PG {tag}", "inventory_mode": "bulk",
        "inventory_category": "componentes",
    }
    body.update(changes)
    return body


async def create_purchase(client, body):
    response = await client.post("/purchasing/orders", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def create_linked_request(client, purchase, body):
    response = await client.post("/purchasing/material-requests", json={
        "company_code": body["company_code"], "item_name": body["product_name"],
        "quantity": body["quantity"], "inventory_destination": body["inventory_destination"],
        "inventory_name": body["inventory_name"], "inventory_mode": body["inventory_mode"],
        "inventory_category": body["inventory_category"],
    })
    assert response.status_code == 201, response.text
    request = response.json()
    for status in ("approved", "purchasing", "purchased"):
        response = await client.patch(f"/purchasing/material-requests/{request['id']}", json={
            "status": status, "purchase_reference": purchase["code"], "unit_cost": "12.50",
        })
        assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_parallel_purchase_and_request_creation_uses_unique_codes(postgres_client):
    client = postgres_client
    supplier_id = await create_supplier(client)
    tag = uuid4().hex
    requests = [client.post("/purchasing/orders", json=purchase_payload(supplier_id)) for _ in range(8)]
    requests.extend(client.post("/purchasing/material-requests", json={
        "company_code": "universo_eletronica", "item_name": f"SC concorrente {tag}-{i}",
        "quantity": 1,
    }) for i in range(8))
    responses = await asyncio.wait_for(asyncio.gather(*requests), timeout=30)
    assert all(r.status_code == 201 for r in responses), [(r.status_code, r.text) for r in responses]
    codes = [r.json()["code"] for r in responses]
    assert len(set(codes[:8])) == 8
    assert len(set(codes[8:])) == 8
    assert all(code.startswith(f"PC-{date.today().year}-") for code in codes[:8])
    assert all(code.startswith(f"SC-{date.today().year}-") for code in codes[8:])
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.id.in_([r.json()["id"] for r in responses[:8]])
        )) == 8
        assert await db.scalar(select(func.count()).select_from(MaterialRequest).where(
            MaterialRequest.id.in_([r.json()["id"] for r in responses[8:]])
        )) == 8


@pytest.mark.asyncio
async def test_repeated_parallel_receipt_registers_exactly_one_stock_entry(postgres_client):
    client = postgres_client
    body = purchase_payload(await create_supplier(client))
    purchase = await create_purchase(client, body)
    received = {**body, "status": "delivered"}
    responses = await asyncio.wait_for(asyncio.gather(*(
        client.put(f"/purchasing/orders/{purchase['id']}", json=received) for _ in range(8)
    )), timeout=30)
    assert all(r.status_code == 200 for r in responses), [(r.status_code, r.text) for r in responses]
    async with session_factory() as db:
        movements = (await db.scalars(select(InventoryMovement).where(
            InventoryMovement.purchase_order_id == purchase["id"]
        ))).all()
        assert len(movements) == 1
        item = await db.get(InventoryItem, movements[0].item_id)
        assert item.quantity == body["quantity"]
        assert item.unit_cost == Decimal("12.50")
        assert await db.scalar(select(func.count()).select_from(InventoryItem).where(
            InventoryItem.name == body["inventory_name"]
        )) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse_submission", [False, True])
async def test_linked_order_and_request_receiving_together_share_one_movement(
    postgres_client, reverse_submission,
):
    client = postgres_client
    body = purchase_payload(await create_supplier(client))
    purchase = await create_purchase(client, body)
    request = await create_linked_request(client, purchase, body)
    for _ in range(2):
        calls = [
            client.put(f"/purchasing/orders/{purchase['id']}", json={**body, "status": "delivered"}),
            client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received"}),
        ]
        if reverse_submission:
            calls.reverse()
        responses = await asyncio.wait_for(asyncio.gather(*calls), timeout=30)
        assert all(r.status_code == 200 for r in responses), [(r.status_code, r.text) for r in responses]
    async with session_factory() as db:
        movements = (await db.scalars(select(InventoryMovement).where(or_(
            InventoryMovement.purchase_order_id == purchase["id"],
            InventoryMovement.material_request_id == request["id"],
        )))).all()
        assert len(movements) == 1
        movement = movements[0]
        assert movement.purchase_order_id == purchase["id"]
        assert movement.material_request_id == request["id"]
        assert movement.quantity == body["quantity"]
        assert (await db.get(InventoryItem, movement.item_id)).quantity == body["quantity"]
        assert (await db.get(PurchaseOrder, purchase["id"])).status == "delivered"
        assert (await db.get(MaterialRequest, request["id"])).status == "received"


@pytest.mark.asyncio
async def test_parallel_existing_stock_receipts_preserve_both_increments(postgres_client):
    client = postgres_client
    supplier_id = await create_supplier(client)
    response = await client.post("/inventory/items", json={
        "company_code": "universo_eletronica", "name": f"Saldo concorrente {uuid4().hex}",
        "category": "componentes", "mode": "bulk", "quantity": 10, "unit_cost": "2.00",
    })
    assert response.status_code == 201, response.text
    item_id = response.json()["id"]
    bodies = [purchase_payload(supplier_id, inventory_destination="existing", inventory_item_id=item_id)
              for _ in range(2)]
    orders = await asyncio.gather(*(create_purchase(client, body) for body in bodies))
    responses = await asyncio.wait_for(asyncio.gather(*(
        client.put(f"/purchasing/orders/{order['id']}", json={**body, "status": "delivered"})
        for order, body in zip(orders, bodies, strict=True)
    )), timeout=30)
    assert all(r.status_code == 200 for r in responses), [(r.status_code, r.text) for r in responses]
    async with session_factory() as db:
        item = await db.get(InventoryItem, item_id)
        assert item.quantity == 18
        assert await db.scalar(select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.purchase_order_id.in_([order["id"] for order in orders])
        )) == 2


@pytest.mark.asyncio
async def test_conflicting_serial_receipt_rolls_back_only_the_failed_purchase(postgres_client):
    client = postgres_client
    supplier_id = await create_supplier(client)
    serial = f"SERIAL-PG-{uuid4().hex}"
    bodies = [purchase_payload(supplier_id, quantity=1, total_amount="12.50",
                               inventory_mode="serialized", inventory_serial=serial)
              for _ in range(2)]
    orders = await asyncio.gather(*(create_purchase(client, body) for body in bodies))
    responses = await asyncio.wait_for(asyncio.gather(*(
        client.put(f"/purchasing/orders/{order['id']}", json={**body, "status": "delivered"})
        for order, body in zip(orders, bodies, strict=True)
    )), timeout=30)
    assert sorted(r.status_code for r in responses) == [200, 409], [(r.status_code, r.text) for r in responses]
    async with session_factory() as db:
        saved = (await db.scalars(select(PurchaseOrder).where(
            PurchaseOrder.id.in_([order["id"] for order in orders])
        ))).all()
        assert sorted(order.status for order in saved) == ["delivered", "ordered"]
        assert await db.scalar(select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.purchase_order_id.in_([order["id"] for order in orders])
        )) == 1
        assert await db.scalar(select(func.count()).select_from(InventoryItem).where(
            InventoryItem.serial_normalized == serial.upper()
        )) == 1
