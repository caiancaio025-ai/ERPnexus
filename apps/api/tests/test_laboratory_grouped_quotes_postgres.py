"""Orçamento conjunto via HTTP e PostgreSQL real, sem dependência de Docker."""
import asyncio
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import update


async def make_orders(client, count=3, *, company="universo_eletronica", customer=None):
    if customer is None:
        result = await client.post("/laboratory/customers", json={
            "company_code": company, "legal_name": f"Cliente conjunto {uuid4().hex[:10]}",
        })
        assert result.status_code == 201, result.text
        customer = result.json()
    orders = []
    for index in range(count):
        result = await client.post("/laboratory/work-orders", json={
            "company_code": company, "customer_id": customer["id"], "customer_name": customer["legal_name"],
            "reported_defect": f"Falha na unidade {index + 1}", "equipment_type": "Inversor de frequência",
            "manufacturer": "WEG", "model": "CFW11", "serial_number": f"CONJ-{uuid4().hex[:12]}",
            "quoted_value": str(100 * (index + 1)), "approved_value": "45.50",
        })
        assert result.status_code == 201, result.text
        orders.append(result.json())
    return customer, orders


async def create_quote(client, orders, **extra):
    result = await client.post("/laboratory/grouped-quotes", headers={"Idempotency-Key": uuid4().hex}, json={
        "work_order_ids": [row["id"] for row in orders], **extra,
    })
    assert result.status_code == 201, result.text
    return result.json()


def edit_body(quote, **extra):
    return {"version": quote["version"], "work_order_ids": quote["work_order_ids"], "items": quote["items"], **extra}


@pytest.mark.asyncio
async def test_direct_create_emit_preserves_each_os_and_frozen_pdf(postgres_client):
    from app.core.db import session_factory
    from app.laboratory.models import LaboratoryGroupedQuote, LaboratoryWorkOrder, LaboratoryCustomer
    client = postgres_client
    customer, orders = await make_orders(client)
    quote = await create_quote(client, orders)
    assert quote["code"].startswith("OC-") and quote["revision"] == quote["version"] == 1
    assert quote["total"] == "600.00" and len(quote["items"]) == 3
    assert [row["equipment_serial"] for row in quote["work_orders"]] == [row["equipment_serial"] for row in orders]
    # Uma OS já faturada não pode retroceder nem ter aprovação/financeiro substituído.
    async with session_factory() as db:
        await db.execute(update(LaboratoryWorkOrder).where(LaboratoryWorkOrder.id == orders[0]["id"]).values(status="invoiced"))
        await db.commit()
    result = await client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(
        quote, technical_report="Laudo das três unidades conferido", discount_type="percent", discount_value="10.00"))
    assert result.status_code == 200, result.text
    quote = result.json()
    assert quote["total"] == "540.00" and quote["discount_amount"] == "60.00" and quote["version"] == 2
    assert [row["total"] for row in quote["work_orders"]] == ["90.00", "180.00", "270.00"]
    preview = await client.get(f"/laboratory/grouped-quotes/{quote['id']}/pdf?preview=true")
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF-"), preview.text[:300]
    unchanged = (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json()
    assert unchanged["version"] == 2 and unchanged["status"] == "draft"
    emissions = await asyncio.gather(*[client.post(f"/laboratory/grouped-quotes/{quote['id']}/emit", json={"version": 2}) for _ in range(3)])
    assert all(result.status_code == 200 for result in emissions), [r.text[:300] for r in emissions]
    assert len({hashlib.sha256(result.content).hexdigest() for result in emissions}) == 1
    issued = (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json()
    assert issued["status"] == "emitted" and issued["version"] == 3
    for index, order in enumerate(orders):
        current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
        assert current["quoted_value"] == issued["work_orders"][index]["total"]
        assert current["approved_value"] == "45.50" and current["version"] == order["version"] + 1
        assert "quote_sent" in current["substatuses"]
        assert current["status"] == ("invoiced" if index == 0 else "received")
        assert (await client.get(f"/laboratory/work-orders/{order['id']}/quotes")).json() == []
    async with session_factory() as db:
        stored = await db.get(LaboratoryGroupedQuote, quote["id"])
        assert stored.document_snapshot["quote"] == issued
        await db.execute(update(LaboratoryCustomer).where(LaboratoryCustomer.id == customer["id"]).values(legal_name="Nome corrigido depois"))
        await db.execute(update(LaboratoryWorkOrder).where(LaboratoryWorkOrder.id == orders[0]["id"]).values(
            equipment_serial="SÉRIE ALTERADA DEPOIS", reported_defect="Defeito editado depois", quoted_value=999))
        await db.commit()
    assert (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json() == issued
    for path, method in ((f"/laboratory/grouped-quotes/{quote['id']}/pdf", "get"),
                         (f"/laboratory/grouped-quotes/{quote['id']}/emit", "post")):
        response = await getattr(client, method)(path, **({"json": {"version": 1}} if method == "post" else {}))
        assert response.status_code == 200 and response.content == emissions[0].content
    current = (await client.get(f"/laboratory/work-orders/{orders[0]['id']}")).json()
    assert current["quoted_value"] == "999.00"  # Retry não reaplica o orçamento antigo.
    assert (await client.delete(f"/laboratory/grouped-quotes/{quote['id']}?version={issued['version']}")).status_code == 409
    assert (await client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(issued))).status_code == 409


@pytest.mark.asyncio
async def test_concurrent_edits_and_revisions_have_no_lost_draft(postgres_client):
    client = postgres_client
    _, orders = await make_orders(client, 2)
    quote = await create_quote(client, orders, technical_report="Laudo base")
    edits = await asyncio.gather(*[client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(quote, title=title))
                                 for title in ("Primeira edição", "Segunda edição")])
    assert sorted(result.status_code for result in edits) == [200, 409], [r.text for r in edits]
    winner = next(result.json() for result in edits if result.status_code == 200)
    assert (await client.post(f"/laboratory/grouped-quotes/{quote['id']}/emit", json={"version": 1})).status_code == 409
    assert (await client.post(f"/laboratory/grouped-quotes/{quote['id']}/emit", json={"version": winner['version']})).status_code == 200
    revisions = await asyncio.gather(*[client.post(f"/laboratory/grouped-quotes/{quote['id']}/revisions") for _ in range(4)])
    assert all(result.status_code == 201 for result in revisions), [r.text for r in revisions]
    assert len({row.json()["id"] for row in revisions}) == 1
    draft = revisions[0].json()
    assert draft["revision"] == 2 and draft["title"] == winner["title"]
    saved = await client.put(f"/laboratory/grouped-quotes/{draft['id']}", json=edit_body(draft, title="Edição que deve ser preservada"))
    assert saved.status_code == 200, saved.text
    replay = await client.post(f"/laboratory/grouped-quotes/{quote['id']}/revisions")
    assert replay.json() == saved.json()
    stale_delete = await client.delete(f"/laboratory/grouped-quotes/{draft['id']}?version={draft['version']}")
    assert stale_delete.status_code == 409
    assert (await client.get(f"/laboratory/grouped-quotes/{draft['id']}")).json() == saved.json()
    listing = await client.get("/laboratory/grouped-quotes", params={"work_order_id": orders[0]["id"], "group_id": quote["group_id"], "search": quote["code"]})
    assert listing.status_code == 200, listing.text
    assert [row["revision"] for row in listing.json()] == [2, 1]
    by_os_number = await client.get("/laboratory/grouped-quotes", params={"search": orders[0]["number"]})
    assert [row["revision"] for row in by_os_number.json()] == [2, 1]
    assert (await client.delete(f"/laboratory/grouped-quotes/{draft['id']}?version={saved.json()['version']}")).status_code == 204
    assert (await client.get(f"/laboratory/grouped-quotes/{draft['id']}")).status_code == 404
    assert (await client.get(f"/laboratory/grouped-quotes/{quote['id']}/pdf")).status_code == 200


@pytest.mark.asyncio
async def test_create_idempotency_replays_before_revalidating_current_os(postgres_client):
    from app.core.db import session_factory
    from app.laboratory.models import LaboratoryWorkOrder
    client = postgres_client
    _, orders = await make_orders(client, 2)
    payload = {"work_order_ids": [row["id"] for row in orders]}
    headers = {"Idempotency-Key": uuid4().hex}
    assert (await client.post("/laboratory/grouped-quotes", json=payload)).status_code == 422
    results = await asyncio.gather(*[client.post("/laboratory/grouped-quotes", json=payload, headers=headers) for _ in range(4)])
    assert all(result.status_code == 201 for result in results), [r.text for r in results]
    assert len({result.json()["id"] for result in results}) == 1
    async with session_factory() as db:
        await db.execute(update(LaboratoryWorkOrder).where(LaboratoryWorkOrder.id == orders[0]["id"]).values(is_inactive=True))
        await db.commit()
    replay = await client.post("/laboratory/grouped-quotes", json=payload, headers=headers)
    assert replay.status_code == 201 and replay.json()["id"] == results[0].json()["id"], replay.text
    changed = await client.post("/laboratory/grouped-quotes", json={**payload, "title": "Outro conjunto"}, headers=headers)
    assert changed.status_code == 409
    assert (await client.post("/laboratory/grouped-quotes", json=payload, headers={"Idempotency-Key": uuid4().hex})).status_code == 409


@pytest.mark.asyncio
async def test_membership_can_change_but_mixed_customer_or_invalid_lines_are_rejected(postgres_client):
    client = postgres_client
    _, orders = await make_orders(client, 3)
    quote = await create_quote(client, orders[:2])
    new_ids = [row["id"] for row in orders[1:]]
    new_items = [{"work_order_id": key, "description": "Reparo unitário", "quantity": "1", "unit_value": "7.77"} for key in new_ids]
    updated = await client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(quote, work_order_ids=new_ids, items=new_items))
    assert updated.status_code == 200, updated.text
    assert updated.json()["total"] == "15.54" and updated.json()["work_order_ids"] == new_ids
    assert (await client.get("/laboratory/grouped-quotes", params={"work_order_id": orders[0]["id"]})).json() == []
    _, other = await make_orders(client, 2)
    mixed = await client.post("/laboratory/grouped-quotes", headers={"Idempotency-Key": uuid4().hex},
                              json={"work_order_ids": [orders[0]["id"], other[0]["id"]]})
    assert mixed.status_code == 422, mixed.text
    invalid = await client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(updated.json(), items=new_items[:1]))
    assert invalid.status_code == 422
    assert (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json()["total"] == "15.54"


@pytest.mark.asyncio
async def test_pdf_generation_failure_does_not_emit_or_change_os(postgres_client, monkeypatch):
    from app.laboratory import grouped_quote_router as module
    client = postgres_client
    _, orders = await make_orders(client, 2)
    quote = await create_quote(client, orders, technical_report="Texto conferido", discount_type="amount", discount_value="25.00")
    def broken(_snapshot):
        raise ValueError("Simulação de falha na geração")
    monkeypatch.setattr(module, "grouped_quote_pdf", broken)
    result = await client.post(f"/laboratory/grouped-quotes/{quote['id']}/emit", json={"version": 1})
    assert result.status_code == 422, result.text
    current = (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json()
    assert current["status"] == "draft" and current["version"] == 1 and current["emitted_at"] is None
    for order in orders:
        current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
        assert current["version"] == order["version"] and current["quoted_value"] == order["quoted_value"]


@pytest.mark.asyncio
async def test_edit_and_emit_cannot_both_succeed_with_the_same_version(postgres_client):
    client = postgres_client
    _, orders = await make_orders(client, 2)
    quote = await create_quote(client, orders, technical_report="Laudo pronto")
    edited, emitted = await asyncio.gather(
        client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(quote, technical_report="Laudo alterado")),
        client.post(f"/laboratory/grouped-quotes/{quote['id']}/emit", json={"version": quote["version"]}),
    )
    assert sorted([edited.status_code, emitted.status_code]) == [200, 409], [edited.text[:200], emitted.text[:200]]
    current = (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json()
    assert current["version"] == 2
    assert current["status"] == ("emitted" if emitted.status_code == 200 else "draft")
    assert current["technical_report"] == ("Laudo pronto" if emitted.status_code == 200 else "Laudo alterado")


@pytest.mark.asyncio
async def test_fractional_line_totals_are_persisted_and_individual_quote_is_untouched(postgres_client):
    client = postgres_client
    _, orders = await make_orders(client, 2)
    individual = await client.post(f"/laboratory/work-orders/{orders[0]['id']}/quotes", json={
        "technical_report": "Laudo individual preservado", "payment_terms": "PIX", "return_condition": "Devolução",
        "consumer_clause": "Garantia", "supply_clause": "Prazo acordado", "estimate_clause": "Estimativa",
        "items": [{"description": "Reparo individual", "quantity": "1", "unit_value": "876.54"}],
    })
    assert individual.status_code == 201, individual.text
    before = (await client.get(f"/laboratory/work-orders/{orders[0]['id']}/quotes")).json()
    ids = [order["id"] for order in orders]
    lines = [
        {"work_order_id": ids[0], "description": "Linha A", "quantity": "0.5", "unit_value": "0.01"},
        {"work_order_id": ids[0], "description": "Linha B", "quantity": "0.5", "unit_value": "0.01"},
        {"work_order_id": ids[1], "description": "Linha C", "quantity": "1", "unit_value": "1"},
    ]
    quote = await create_quote(client, orders, technical_report="Laudo fracionado", items=lines)
    assert quote["subtotal"] == quote["total"] == "1.02"
    assert [row["total"] for row in quote["work_orders"]] == ["0.02", "1.00"]
    assert (await client.post(f"/laboratory/grouped-quotes/{quote['id']}/emit", json={"version": 1})).status_code == 200
    assert (await client.get(f"/laboratory/work-orders/{orders[0]['id']}/quotes")).json() == before


@pytest.mark.asyncio
async def test_partial_terms_are_validated_after_merging_saved_discount_type(postgres_client):
    client = postgres_client
    _, orders = await make_orders(client, 2)
    quote = await create_quote(client, orders, discount_type="percent", discount_value="5.00")
    quote = (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json()
    invalid = await client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(quote, discount_value="101.00"))
    assert invalid.status_code == 422, invalid.text
    assert (await client.get(f"/laboratory/grouped-quotes/{quote['id']}")).json() == quote
    valid = await client.put(f"/laboratory/grouped-quotes/{quote['id']}", json=edit_body(quote, discount_value="7.50"))
    assert valid.status_code == 200, valid.text
    assert valid.json()["discount_type"] == "percent" and valid.json()["discount_amount"] == "22.50"
    assert valid.json()["total"] == "277.50" and valid.json()["version"] == 2


@pytest.mark.asyncio
async def test_non_quote_role_cannot_read_money_or_generate_group_pdf(postgres_client):
    from app.auth.models import User
    from app.core.db import session_factory
    client = postgres_client
    _, orders = await make_orders(client, 2)
    quote = await create_quote(client, orders)
    identity = (await client.get("/auth/me")).json()
    async with session_factory() as db:
        await db.execute(update(User).where(User.id == identity["id"]).values(role="lab", modules=["laboratorio"]))
        await db.commit()
    for path in ("/laboratory/grouped-quotes", f"/laboratory/grouped-quotes/{quote['id']}", f"/laboratory/grouped-quotes/{quote['id']}/pdf"):
        assert (await client.get(path)).status_code == 403
    assert (await client.post("/laboratory/grouped-quotes", headers={"Idempotency-Key": uuid4().hex},
                              json={"work_order_ids": quote["work_order_ids"]})).status_code == 403
