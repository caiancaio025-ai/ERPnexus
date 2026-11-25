"""Gravação HTTP concorrente em PostgreSQL real (banco descartável de testes)."""

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest


async def new_work_order(client, *, serial=None):
    response = await client.post("/laboratory/work-orders", json={
        "company_code": "universo_eletronica", "customer_name": f"Cliente teste {uuid4().hex[:8]}",
        "reported_defect": "Diagnóstico inicial", "manufacturer": "WEG", "model": "CFW11",
        "serial_number": serial, "entry_invoice": "123456", "parts_cost": "20.00",
    })
    assert response.status_code == 201, response.text
    return response.json()


def quote_payload(value="200.00"):
    return {
        "technical_report": "Laudo técnico confirmado", "payment_terms": "PIX",
        "return_condition": "Devolução", "consumer_clause": "Garantia",
        "supply_clause": "Prazo acordado", "estimate_clause": "Estimativa",
        "items": [{"description": "Manutenção", "quantity": "1.000", "unit_value": value}],
    }


@pytest.mark.asyncio
async def test_concurrent_os_patches_keep_one_winner_and_one_conflict(postgres_client):
    client = postgres_client
    order = await new_work_order(client)
    responses = await asyncio.gather(*[
        client.patch(f"/laboratory/work-orders/{order['id']}", json={
            "version": order["version"], "internal_notes": note,
        }) for note in ("Edição A", "Edição B")
    ])
    assert sorted(response.status_code for response in responses) == [200, 409], [r.text for r in responses]
    saved = next(response.json() for response in responses if response.status_code == 200)
    current = await client.get(f"/laboratory/work-orders/{order['id']}")
    assert current.status_code == 200, current.text
    stored = current.json()
    assert stored["version"] == order["version"] + 1
    assert stored["internal_notes"] == saved["internal_notes"]
    assert stored["entry_invoice"] == "123456" and stored["manufacturer"] == "WEG"
    assert stored["parts_cost"] == "20.00"
    assert datetime.fromisoformat(saved["updated_at"]) >= datetime.fromisoformat(order["updated_at"])


@pytest.mark.asyncio
async def test_parallel_os_creation_has_unique_numbers_and_one_shared_equipment(postgres_client):
    serial = f"V48-{uuid4().hex}"
    orders = await asyncio.gather(*[new_work_order(postgres_client, serial=serial) for _ in range(6)])
    assert len({row["id"] for row in orders}) == 6
    assert len({row["number"] for row in orders}) == 6
    assert len({row["equipment_id"] for row in orders}) == 1
    assert all(row["equipment_serial"] == serial for row in orders)


@pytest.mark.asyncio
async def test_serial_correction_does_not_rekey_equipment_shared_with_other_os(postgres_client):
    client = postgres_client
    original_serial = f"V48-{uuid4().hex}"
    first = await new_work_order(client, serial=original_serial)
    second = await new_work_order(client, serial=original_serial)
    assert first["equipment_id"] == second["equipment_id"]
    changed = await client.patch(f"/laboratory/work-orders/{first['id']}", json={
        "version": first["version"], "serial_number": f"NOVO-{uuid4().hex}",
    })
    assert changed.status_code == 200, changed.text
    assert changed.json()["equipment_id"] != second["equipment_id"]
    original = await new_work_order(client, serial=original_serial)
    assert original["equipment_id"] == second["equipment_id"]
    stored_second = (await client.get(f"/laboratory/work-orders/{second['id']}")).json()
    assert stored_second["equipment_serial"] == original_serial


@pytest.mark.asyncio
async def test_status_change_and_patch_cannot_both_use_same_os_version(postgres_client):
    client = postgres_client
    order = await new_work_order(client)
    patch, status = await asyncio.gather(
        client.patch(f"/laboratory/work-orders/{order['id']}", json={"version": order["version"], "reported_defect": "Novo laudo"}),
        client.post(f"/laboratory/work-orders/{order['id']}/status", json={"version": order["version"], "status": "in_repair"}),
    )
    assert sorted([patch.status_code, status.status_code]) == [200, 409], [patch.text, status.text]
    current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    if patch.status_code == 200:
        assert current["reported_defect"] == "Novo laudo" and current["status"] == "received"
    else:
        assert current["reported_defect"] == "Diagnóstico inicial" and current["status"] == "in_repair"
    assert current["version"] == order["version"] + 1


@pytest.mark.asyncio
async def test_quote_edit_and_emit_are_serialized_and_revisions_reuse_draft(postgres_client):
    client = postgres_client
    order = await new_work_order(client)
    response = await client.post(f"/laboratory/work-orders/{order['id']}/quotes", json=quote_payload())
    assert response.status_code == 201, response.text
    quote = response.json()
    edit, emission = await asyncio.gather(
        client.put(f"/laboratory/quotes/{quote['id']}", json=quote_payload("300.00")),
        client.post(f"/laboratory/quotes/{quote['id']}/emit"),
    )
    assert emission.status_code == 200 and emission.content.startswith(b"%PDF-"), emission.text[:300]
    assert edit.status_code in {200, 409}, edit.text
    rows = (await client.get(f"/laboratory/work-orders/{order['id']}/quotes")).json()
    issued = next(row for row in rows if row["id"] == quote["id"])
    assert issued["status"] == "emitted"
    assert issued["total"] == ("300.00" if edit.status_code == 200 else "200.00")
    revisions = await asyncio.gather(*[client.post(f"/laboratory/quotes/{quote['id']}/revisions") for _ in range(4)])
    assert all(row.status_code == 201 for row in revisions), [row.text for row in revisions]
    assert {row.json()["revision"] for row in revisions} == {2}
    assert len({row.json()["id"] for row in revisions}) == 1
    updated = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    assert "quote_sent" in updated["substatuses"]
    assert updated["version"] == order["version"] + 1


@pytest.mark.asyncio
async def test_parallel_commercial_revisions_reuse_next_family_revision(postgres_client):
    client = postgres_client
    customer = await client.post("/laboratory/customers", json={
        "company_code": "universo_eletronica", "legal_name": f"Cliente comercial {uuid4().hex[:8]}",
    })
    assert customer.status_code == 201, customer.text
    response = await client.post("/commercial/quotes", json={
        "quote_type": "sale", "company_code": "universo_eletronica", "customer_id": customer.json()["id"],
        "items": [{"description": "Inversor", "unit_price": 1500, "quantity": 1}],
    })
    assert response.status_code == 201, response.text
    original = response.json()
    response = await client.post(f"/commercial/quotes/{original['id']}/issue")
    assert response.status_code == 200, response.text
    revisions = await asyncio.gather(*[client.post(f"/commercial/quotes/{original['id']}/revision") for _ in range(4)])
    assert all(row.status_code == 201 for row in revisions), [row.text for row in revisions]
    assert {row.json()["revision"] for row in revisions} == {2}
    assert len({row.json()["id"] for row in revisions}) == 1
    second_id = revisions[0].json()["id"]
    assert (await client.post(f"/commercial/quotes/{second_id}/issue")).status_code == 200
    third = await client.post(f"/commercial/quotes/{original['id']}/revision")
    assert third.status_code == 201, third.text
    assert third.json()["revision"] == 3
