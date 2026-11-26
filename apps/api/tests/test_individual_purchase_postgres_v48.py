"""Real PostgreSQL/HTTP coverage for grouped receipts, OEM edits and migration."""
import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.db import session_factory
from app.inventory.models import InventoryItem, InventoryMovement
from test_purchasing_postgres_v48 import create_linked_request, create_purchase, create_supplier, purchase_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("first", ["order", "request", "concurrent"])
async def test_ten_individual_units_link_both_origins_in_either_order_and_concurrent_retries(postgres_client, first):
    client = postgres_client
    body = purchase_payload(await create_supplier(client), quantity=10, total_amount="125.00",
                            inventory_mode="serialized", inventory_serial=None)
    purchase = await create_purchase(client, body)
    request = await create_linked_request(client, purchase, body)

    async def receive_order():
        return await client.put(f"/purchasing/orders/{purchase['id']}", json={**body, "status": "delivered"})

    async def receive_request():
        return await client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received"})

    if first == "concurrent":
        responses = await asyncio.gather(receive_order(), receive_request())
    else:
        functions = (receive_order, receive_request) if first == "order" else (receive_request, receive_order)
        responses = [await operation() for operation in functions]
    assert all(r.status_code == 200 for r in responses), [(r.status_code, r.text) for r in responses]
    responses = await asyncio.wait_for(asyncio.gather(*[
        operation() for _ in range(4) for operation in (receive_order, receive_request)
    ]), timeout=30)
    assert all(r.status_code == 200 for r in responses), [(r.status_code, r.text) for r in responses]
    async with session_factory() as db:
        rows = list((await db.scalars(select(InventoryMovement).where(
            InventoryMovement.purchase_order_id == purchase["id"],
        ).order_by(InventoryMovement.receipt_unit_index))).all())
        items = list((await db.scalars(select(InventoryItem).where(InventoryItem.id.in_([r.item_id for r in rows])))).all())
        assert len(rows) == len(items) == 10
        assert [row.receipt_unit_index for row in rows] == list(range(1, 11))
        assert all(row.material_request_id == request["id"] and row.quantity == 1 for row in rows)
        assert len({item.stock_code for item in items}) == 10
        assert all(item.quantity == 1 and item.manufacturer_serial is None for item in items)
        assert sum(row.quantity * row.unit_cost for row in rows) == 125


@pytest.mark.asyncio
async def test_different_individual_purchases_received_in_parallel_keep_twenty_distinct_units(postgres_client):
    client = postgres_client
    supplier = await create_supplier(client)
    bodies = [purchase_payload(supplier, quantity=10, total_amount="125.00", inventory_mode="serialized") for _ in range(2)]
    purchases = await asyncio.gather(*(create_purchase(client, body) for body in bodies))
    responses = await asyncio.wait_for(asyncio.gather(*[
        client.put(f"/purchasing/orders/{order['id']}", json={**body, "status": "delivered"})
        for order, body in zip(purchases, bodies, strict=True)
    ]), timeout=30)
    assert all(r.status_code == 200 for r in responses), [(r.status_code, r.text) for r in responses]
    async with session_factory() as db:
        rows = list((await db.scalars(select(InventoryMovement).where(
            InventoryMovement.purchase_order_id.in_([order["id"] for order in purchases]),
        ))).all())
        assert len(rows) == 20 and len({row.item_id for row in rows}) == 20
        for purchase in purchases:
            assert sum(row.quantity for row in rows if row.purchase_order_id == purchase["id"]) == 10


@pytest.mark.asyncio
async def test_bulk_ten_units_still_have_one_item_and_one_receipt(postgres_client):
    body = purchase_payload(await create_supplier(postgres_client), quantity=10, total_amount="125.00", status="delivered")
    purchase = await create_purchase(postgres_client, body)
    async with session_factory() as db:
        rows = list((await db.scalars(select(InventoryMovement).where(
            InventoryMovement.purchase_order_id == purchase["id"],
        ))).all())
        assert len(rows) == 1 and rows[0].quantity == 10 and rows[0].receipt_unit_index == 1
        item = await db.get(InventoryItem, rows[0].item_id)
        assert item.mode == "bulk" and item.quantity == 10


@pytest.mark.asyncio
async def test_individual_receipt_limit_accepts_all_one_thousand_units_atomically(postgres_client):
    body = purchase_payload(await create_supplier(postgres_client), quantity=1000, total_amount="12500.00",
                            inventory_mode="serialized", status="delivered")
    purchase = await asyncio.wait_for(create_purchase(postgres_client, body), timeout=30)
    async with session_factory() as db:
        rows = list((await db.scalars(select(InventoryMovement).where(
            InventoryMovement.purchase_order_id == purchase["id"],
        ))).all())
        assert len(rows) == 1000 and len({row.item_id for row in rows}) == 1000
        assert {row.receipt_unit_index for row in rows} == set(range(1, 1001))
        assert sum(row.quantity for row in rows) == 1000


@pytest.mark.asyncio
async def test_optional_oem_can_be_added_later_without_changing_est_or_losing_series_on_omitted_field(postgres_client):
    client = postgres_client
    items = []
    for _ in range(2):
        response = await client.post("/inventory/items", json={
            "company_code": "universo_eletronica", "name": f"Unidade {uuid4().hex}",
            "mode": "serialized", "quantity": 1, "category": "componentes",
        })
        assert response.status_code == 201, response.text
        items.append(response.json())
    serial = f"OEM-{uuid4().hex}"
    responses = await asyncio.gather(*[
        client.put(f"/inventory/items/{item['id']}", json={
            "name": item["name"], "category": item["category"],
            "manufacturer_serial": serial.lower() if index else serial.upper(), "notes": "OEM registrado",
        }) for index, item in enumerate(items)
    ])
    assert sorted(r.status_code for r in responses) == [200, 409], [(r.status_code, r.text) for r in responses]
    winner_index = next(i for i, response in enumerate(responses) if response.status_code == 200)
    winner, other = items[winner_index], items[1 - winner_index]
    previous = responses[winner_index].json()
    edited = await client.put(f"/inventory/items/{winner['id']}", json={
        "name": winner["name"], "category": winner["category"], "notes": "Só observação",
    })
    assert edited.status_code == 200, edited.text
    assert edited.json()["manufacturer_serial"] == previous["manufacturer_serial"]
    assert edited.json()["stock_code"] == winner["stock_code"]
    async with session_factory() as db:
        failed = await db.get(InventoryItem, other["id"])
        assert failed.manufacturer_serial is None and failed.serial_normalized is None
        assert failed.notes is None and failed.quantity == 1 and failed.stock_code == other["stock_code"]
        successful = await db.get(InventoryItem, winner["id"])
        assert successful.serial_normalized == serial.upper()


@pytest.mark.asyncio
async def test_migration_preserves_legacy_receipts_and_enforces_each_origin_unit_once(postgres_client):
    # A separate transactional schema models the predecessor table with data.
    # Its DDL and rows are rolled back; the application's migrated schema is untouched.
    path = Path(__file__).resolve().parents[1] / "migrations/versions/20261126_01_individual_purchase_receipts.py"
    spec = importlib.util.spec_from_file_location("individual_receipt_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def verify(session):
        conn = session.connection()
        schema = "receipt_migration_" + uuid4().hex
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(text("""
            CREATE TABLE inventory_movements (
                id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL, quantity INTEGER NOT NULL,
                unit_cost NUMERIC(14,2) NOT NULL, purchase_order_id INTEGER, material_request_id INTEGER,
                CONSTRAINT uq_inv_movements_purchase_once UNIQUE (purchase_order_id),
                CONSTRAINT uq_inv_movements_request_once UNIQUE (material_request_id)
            )
        """))
        conn.execute(text("INSERT INTO inventory_movements VALUES (1,501,10,12.50,7,8),(2,502,1,20.00,NULL,NULL)"))
        before = conn.execute(text("SELECT to_jsonb(t) FROM inventory_movements t ORDER BY id")).scalars().all()
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        after = conn.execute(text("SELECT to_jsonb(t) - 'receipt_unit_index' FROM inventory_movements t ORDER BY id")).scalars().all()
        assert after == before
        assert conn.execute(text("SELECT receipt_unit_index FROM inventory_movements ORDER BY id")).scalars().all() == [1, 1]
        conn.execute(text("INSERT INTO inventory_movements VALUES (3,503,1,12.50,7,8,2)"))
        for values in ("4,504,1,12.50,7,NULL,2", "5,505,1,12.50,NULL,8,2", "6,506,1,12.50,NULL,NULL,0"):
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text(f"INSERT INTO inventory_movements VALUES ({values})"))
        with pytest.raises(RuntimeError, match="Downgrade bloqueado"):
            module.downgrade()

    async with session_factory() as db:
        await db.run_sync(verify)
        await db.rollback()
