"""Planning and receipt use the same stock fields without early stock entries."""
import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import select, text

from app.auth.models import User
from app.core.db import session_factory
from app.inventory.item_details import InventoryItemDetails, merge_inventory_details
from app.inventory.models import (
    InventoryArea, InventoryComponentCategory, InventoryComponentFormat, InventoryComponentSubtype, InventoryContainer,
    InventoryItem, InventoryLocationHistory, InventoryLocationType, InventoryMovement, InventorySlot,
)
from app.purchasing.material_models import MaterialRequest
from test_purchasing_postgres_v48 import create_purchase, create_supplier, purchase_payload


async def catalog_details(category="componentes"):
    tag = uuid4().hex[:12]
    async with session_factory() as db:
        area = InventoryArea(code=f"T{tag}", name="Área de teste de recebimento")
        kind = InventoryLocationType(code=f"t{tag}", name="Caixa de teste")
        subtype = InventoryComponentSubtype(category=category, code=tag, name="Ventilador de teste")
        fmt = InventoryComponentFormat(category=category, code=tag, name="Formato de teste")
        db.add_all([area, kind, subtype, fmt])
        await db.flush()
        container = InventoryContainer(area_id=area.id, type_id=kind.id, code=f"C{tag}", name="Caixa de recebimento")
        db.add(container)
        await db.flush()
        slot = InventorySlot(container_id=container.id, code=f"P{tag}", name="Posição de recebimento", row=1, column=1)
        db.add(slot)
        await db.commit()
        return {
            "subtype_id": subtype.id, "manufacturer": "Fabricante informado", "model": "Ventilador 220V",
            "unit": "PC", "slot_id": slot.id, "notes": "Descrição técnica preservada",
        }, fmt.id


async def material_request(client, *, quantity=10, **fields):
    response = await client.post("/purchasing/material-requests", json={
        "company_code": "universo_eletronica", "item_name": f"Ventilador {uuid4().hex}",
        "quantity": quantity, "inventory_destination": "new", "inventory_name": "Ventilador no estoque",
        "inventory_category": "componentes", "inventory_mode": "serialized", **fields,
    })
    assert response.status_code == 201, response.text
    request = response.json()
    for status in ("approved", "purchasing", "purchased"):
        response = await client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": status, "unit_cost": "12.50"})
        assert response.status_code == 200, response.text
    return response.json()


async def receipt_items(source, source_id):
    field = InventoryMovement.purchase_order_id if source == "order" else InventoryMovement.material_request_id
    async with session_factory() as db:
        movements = list((await db.scalars(select(InventoryMovement).where(field == source_id).order_by(InventoryMovement.receipt_unit_index))).all())
        items = list((await db.scalars(select(InventoryItem).where(InventoryItem.id.in_([row.item_id for row in movements])).order_by(InventoryItem.id))).all())
        return movements, items


def test_nested_inventory_details_preserve_omission_and_forbid_quantity_or_cost_override():
    original = {"manufacturer": "WEG", "model": "Original", "unit": "PC", "slot_id": 1}
    incoming = InventoryItemDetails(notes=" Somente descrição ")
    updated = merge_inventory_details(original, incoming, supplied=True)
    assert updated["manufacturer"] == "WEG" and updated["unit"] == "PC" and updated["slot_id"] == 1
    assert updated["notes"] == "Somente descrição"
    assert merge_inventory_details(original, None, supplied=False) == original
    assert merge_inventory_details(original, None, supplied=True) is None
    for field in ("quantity", "unit_cost", "manufacturer_serial"):
        with pytest.raises(ValidationError):
            InventoryItemDetails.model_validate({field: 10})


@pytest.mark.asyncio
async def test_screenshot_flow_saves_without_receiving_reopens_and_creates_ten_individual_codes(postgres_client):
    client = postgres_client
    details, format_id = await catalog_details()
    request = await material_request(client, inventory_details=details, inventory_format_id=format_id)
    for _ in range(2):
        saved = await client.patch(f"/purchasing/material-requests/{request['id']}", json={
            "status": "purchased", "inventory_serial": None, "inventory_details": details, "tracking_code": "SALVO-SEM-RECEBER",
        })
        assert saved.status_code == 200, saved.text
    assert not (await receipt_items("request", request["id"]))[0]
    fetched = await client.get(f"/purchasing/material-requests/{request['id']}")
    assert fetched.status_code == 200 and fetched.json()["inventory_details"] == details, fetched.text
    assert fetched.json()["quantity"] == 10 and fetched.json()["status"] == "purchased"
    patch = await client.patch(f"/purchasing/material-requests/{request['id']}", json={
        "status": "purchased", "inventory_details": {"notes": "Descrição revisada"},
    })
    assert patch.status_code == 200, patch.text
    details = {**details, "notes": "Descrição revisada"}
    assert patch.json()["inventory_details"] == details
    responses = await asyncio.wait_for(asyncio.gather(*[
        client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received"}) for _ in range(4)
    ]), timeout=30)
    assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
    movements, items = await receipt_items("request", request["id"])
    assert len(items) == len(movements) == len({item.stock_code for item in items}) == 10
    assert all(item.quantity == 1 and item.manufacturer_serial is None and item.stock_code.startswith("EST-") for item in items)
    assert all(all(getattr(item, key) == value for key, value in details.items()) for item in items)
    assert sum(movement.quantity * movement.unit_cost for movement in movements) == 125
    async with session_factory() as db:
        histories = list((await db.scalars(select(InventoryLocationHistory).where(InventoryLocationHistory.item_id.in_([item.id for item in items])))).all())
        assert len(histories) == 10 and all(row.new_slot_id == details["slot_id"] and row.new_slot_code for row in histories)
    protected = await client.patch(f"/purchasing/material-requests/{request['id']}", json={
        "status": "received", "inventory_details": {"model": "Mudança física tardia"},
    })
    assert protected.status_code == 409
    assert (await client.get(f"/purchasing/material-requests/{request['id']}")).json()["inventory_details"] == details


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["bulk", "serialized"])
async def test_purchase_draft_details_survive_legacy_updates_and_match_manual_stock_creation(postgres_client, mode):
    client = postgres_client
    details, format_id = await catalog_details()
    body = purchase_payload(await create_supplier(client), inventory_details=details, inventory_format_id=format_id,
                            inventory_mode=mode, quantity=3, total_amount="37.50")
    purchase = await create_purchase(client, body)
    assert purchase["inventory_details"] == details
    legacy = {key: value for key, value in body.items() if key != "inventory_details"}
    edited = await client.put(f"/purchasing/orders/{purchase['id']}", json={**legacy, "notes": "Observação da compra"})
    assert edited.status_code == 200 and edited.json()["inventory_details"] == details, edited.text
    assert not (await receipt_items("order", purchase["id"]))[0]
    received = await client.put(f"/purchasing/orders/{purchase['id']}", json={**legacy, "status": "delivered"})
    assert received.status_code == 200, received.text
    movements, items = await receipt_items("order", purchase["id"])
    assert len(items) == (3 if mode == "serialized" else 1)
    assert sum(item.quantity for item in items) == 3
    manual = await client.post("/inventory/items", json={
        "company_code": body["company_code"], "name": body["inventory_name"], "category": body["inventory_category"],
        "format_id": format_id, "mode": mode, "quantity": 1 if mode == "serialized" else 3,
        "unit_cost": "12.50", "manufacturer_serial": None, **details,
    })
    assert manual.status_code == 201, manual.text
    assert all(all(getattr(item, key) == manual.json()[key] for key in details) for item in items)
    repeated = await client.put(f"/purchasing/orders/{purchase['id']}", json={**legacy, "status": "delivered", "notes": "Conferido depois"})
    assert repeated.status_code == 200, repeated.text
    assert len((await receipt_items("order", purchase["id"]))[0]) == len(movements)


@pytest.mark.asyncio
async def test_linked_sources_share_full_details_and_link_after_stock_location_changes(postgres_client):
    client = postgres_client
    details, format_id = await catalog_details()
    body = purchase_payload(await create_supplier(client), inventory_details=details, inventory_format_id=format_id,
                            inventory_mode="serialized", quantity=3, total_amount="37.50", status="delivered")
    purchase = await create_purchase(client, body)
    _, items = await receipt_items("order", purchase["id"])
    async with session_factory() as db:
        stored = await db.get(InventoryItem, items[0].id)
        stored.slot_id = None
        await db.commit()
    request = await material_request(client, quantity=3, inventory_details=details, inventory_format_id=format_id,
                                     inventory_name=body["inventory_name"])
    planned = await client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "purchased", "purchase_reference": purchase["code"]})
    assert planned.status_code == 200, planned.text
    responses = await asyncio.gather(
        client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received"}),
        client.put(f"/purchasing/orders/{purchase['id']}", json=body),
    )
    assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
    movements, linked_items = await receipt_items("request", request["id"])
    assert len(movements) == 3 and all(row.purchase_order_id == purchase["id"] for row in movements)
    assert {item.id for item in linked_items} == {item.id for item in items}
    assert linked_items[0].slot_id is None  # Reconciliation does not undo a later stock movement.


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["subtype", "format", "slot", "category"])
async def test_invalid_catalogue_receipt_rolls_back_and_keeps_saved_plan(postgres_client, invalid):
    details, format_id = await catalog_details()
    fields = {"inventory_details": details, "inventory_format_id": format_id}
    if invalid == "subtype":
        details["subtype_id"] = 2147483000
    elif invalid == "slot":
        details["slot_id"] = 2147483000
    elif invalid == "category":
        fields["inventory_category"] = "tipo_nao_cadastrado"
    else:
        fields["inventory_category"] = "outros"
        details["subtype_id"] = None
    request = await material_request(postgres_client, **fields)
    response = await postgres_client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received"})
    assert response.status_code == 422, response.text
    fetched = await postgres_client.get(f"/purchasing/material-requests/{request['id']}")
    assert fetched.json()["status"] == "purchased" and fetched.json()["received_at"] is None
    assert fetched.json()["inventory_details"] == details
    assert not (await receipt_items("request", request["id"]))[0]


@pytest.mark.asyncio
async def test_real_oem_is_never_discarded_and_multiple_units_require_explicit_clear(postgres_client):
    request = await material_request(postgres_client, inventory_serial="OEM-REAL-INFORMADO")
    response = await postgres_client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received"})
    assert response.status_code == 422 and "apenas uma unidade" in response.text
    assert (await postgres_client.get(f"/purchasing/material-requests/{request['id']}")).json()["inventory_serial"] == "OEM-REAL-INFORMADO"
    response = await postgres_client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received", "inventory_serial": None})
    assert response.status_code == 200, response.text
    assert len((await receipt_items("request", request["id"]))[1]) == 10
    single = await material_request(postgres_client, quantity=1, inventory_serial=f"OEM-{uuid4().hex}")
    response = await postgres_client.patch(f"/purchasing/material-requests/{single['id']}", json={"status": "received"})
    assert response.status_code == 200, response.text
    assert (await receipt_items("request", single["id"]))[1][0].manufacturer_serial == single["inventory_serial"]


@pytest.mark.asyncio
async def test_purchasing_only_user_can_reopen_details_and_select_catalogue_without_costs(postgres_client):
    client = postgres_client
    details, _ = await catalog_details()
    request = await material_request(client, inventory_details=details)
    user_id = (await client.get("/auth/me")).json()["id"]
    async with session_factory() as db:
        user = await db.get(User, user_id)
        user.role, user.modules = "compras", ["compras"]
        await db.commit()
    response = await client.get("/purchasing/stock-options", params={"company_code": "universo_eletronica"})
    assert response.status_code == 200, response.text
    data = response.json()
    for key in ("categories", "subtypes", "areas", "types", "containers", "slots"):
        assert data[key]
    assert any(row["id"] == details["slot_id"] for row in data["slots"])
    assert '"unit_cost"' not in response.text and '"total_amount"' not in response.text
    current = await client.get(f"/purchasing/material-requests/{request['id']}")
    assert current.status_code == 200 and current.json()["inventory_details"] == details
    assert current.json()["unit_cost"] is None
    assert (await client.get("/inventory/map")).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("send_unchanged_links", [False, True])
async def test_editing_existing_stock_keeps_inactive_catalogue_and_location_links(postgres_client, send_unchanged_links):
    client = postgres_client
    category = "legacy_" + uuid4().hex[:12]
    async with session_factory() as db:
        row = InventoryComponentCategory(code=category, name="Categoria histórica")
        db.add(row)
        await db.commit()
        category_id = row.id
    details, format_id = await catalog_details(category)
    response = await client.post("/inventory/items", json={
        "company_code": "universo_eletronica", "name": "Cadastro histórico", "category": category,
        "format_id": format_id, "mode": "serialized", "quantity": 1, **details,
    })
    assert response.status_code == 201, response.text
    item = response.json()
    async with session_factory() as db:
        for model, key in ((InventoryComponentCategory, category_id), (InventoryComponentSubtype, details["subtype_id"]),
                           (InventoryComponentFormat, format_id), (InventorySlot, details["slot_id"])):
            (await db.get(model, key)).is_active = False
        slot = await db.get(InventorySlot, details["slot_id"])
        (await db.get(InventoryContainer, slot.container_id)).is_active = False
        incompatible = InventoryComponentSubtype(category=category, code=uuid4().hex, name="Outro subtipo inativo", is_active=False)
        db.add(incompatible)
        await db.commit()
        incompatible_id = incompatible.id
    fields = {**details, "format_id": format_id} if send_unchanged_links else {}
    response = await client.put(f"/inventory/items/{item['id']}", json={
        **fields, "name": "Nome corrigido", "category": category,
        "notes": "Descrição corrigida", "manufacturer_serial": f"OEM-{uuid4().hex}",
    })
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["name"] == "Nome corrigido" and current["notes"] == "Descrição corrigida"
    assert current["stock_code"] == item["stock_code"] and current["manufacturer_serial"].startswith("OEM-")
    for field in ("category", "slot_id", "subtype_id", "format_id", "manufacturer", "model", "unit"):
        assert current[field] == item[field]
    changed_link = await client.put(f"/inventory/items/{item['id']}", json={
        "name": "Tentativa recusada", "category": category, "subtype_id": incompatible_id,
    })
    assert changed_link.status_code == 422
    async with session_factory() as db:
        assert (await db.get(InventoryItem, item["id"])).name == "Nome corrigido"


@pytest.mark.asyncio
async def test_legacy_purchased_request_without_cost_can_save_details_and_receive(postgres_client):
    client = postgres_client
    request = await material_request(client)
    async with session_factory() as db:
        (await db.get(MaterialRequest, request["id"])).unit_cost = None
        await db.commit()
    saved = await client.patch(f"/purchasing/material-requests/{request['id']}", json={
        "status": "purchased", "unit_cost": None, "inventory_details": {"notes": "Cadastro legado conferido"},
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "purchased" and saved.json()["unit_cost"] is None
    assert not (await receipt_items("request", request["id"]))[0]
    received = await client.patch(f"/purchasing/material-requests/{request['id']}", json={"status": "received"})
    assert received.status_code == 200, received.text
    movements, items = await receipt_items("request", request["id"])
    assert len(movements) == len(items) == 10 and all(row.unit_cost == 0 for row in movements)
    fresh = await client.post("/purchasing/material-requests", json={
        "company_code": "universo_eletronica", "item_name": "Nova compra ainda sem valor",
    })
    assert fresh.status_code == 201, fresh.text
    key = fresh.json()["id"]
    for status in ("approved", "purchasing"):
        assert (await client.patch(f"/purchasing/material-requests/{key}", json={"status": status})).status_code == 200
    missing_cost = await client.patch(f"/purchasing/material-requests/{key}", json={"status": "purchased"})
    assert missing_cost.status_code == 422 and "valor unitário" in missing_cost.text
    assert (await client.get(f"/purchasing/material-requests/{key}")).json()["status"] == "purchasing"


@pytest.mark.asyncio
async def test_additive_inventory_details_migration_preserves_all_legacy_rows(postgres_client):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/20261126_04_purchase_inventory_details.py"
    spec = importlib.util.spec_from_file_location("purchase_inventory_details_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "20261126_03"

    def verify(session):
        conn = session.connection()
        schema = "purchase_details_" + uuid4().hex
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        for table in ("purchase_orders", "material_requests"):
            conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, note TEXT, quantity INTEGER)"))
            conn.execute(text(f"INSERT INTO {table} VALUES (1,'Histórico preservado',10)"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        for table in ("purchase_orders", "material_requests"):
            row = conn.execute(text(f"SELECT id,note,quantity,inventory_details FROM {table}")).one()
            assert tuple(row) == (1, "Histórico preservado", 10, None)
        with pytest.raises(RuntimeError, match="Downgrade bloqueado"):
            module.downgrade()

    async with session_factory() as db:
        await db.run_sync(verify)
        await db.rollback()
