"""Real HTTP and PostgreSQL regressions for atomic billing of several OS."""
import asyncio
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.db import session_factory
from app.finance.models import FinancialEntry, FinancialObligation
from app.laboratory.models import LaboratoryAuditEvent, LaboratoryWorkOrder


async def make_customer(client, company="universo_eletronica"):
    response = await client.post("/customers", json={"company_code": company, "legal_name": f"Cliente faturamento {uuid4().hex}"})
    assert response.status_code == 201, response.text
    return response.json()


async def make_order(client, customer, *, approved="100.00", **fields):
    response = await client.post("/laboratory/work-orders", json={
        "company_code": customer["company_code"], "customer_id": customer["id"],
        "customer_name": customer["legal_name"], "reported_defect": "Serviço de manutenção",
        "manufacturer": "Teste", "model": "Unidade", "approved_value": approved, **fields,
    })
    assert response.status_code == 201, response.text
    return response.json()


def make_payload(orders, amounts=None, installments=None, **fields):
    amounts = amounts or ["100.00" for _ in orders]
    total = sum((Decimal(value) for value in amounts), Decimal("0.00"))
    installments = installments or [str(total)]
    return {
        "entry_type": "income", "company_code": "universo_eletronica", "nfse_number": f"NF-{uuid4().hex[:12]}",
        "counterparty_name": orders[0]["customer_name"], "description": "Faturamento de manutenção",
        "total_amount": str(total), "issue_date": "2026-11-26", "posting_date": "2026-11-26", "bank_name": "Itaú",
        "work_orders": [{"work_order_id": order["id"], "version": order["version"], "amount": amount} for order, amount in zip(orders, amounts, strict=True)],
        "installments": [{"installment_number": i, "due_date": f"2026-12-{i:02d}", "amount": value} for i, value in enumerate(installments, start=1)],
        **fields,
    }


async def post_batch(client, payload, key=None):
    return await client.post("/finance/billing-batches", json=payload, headers={"Idempotency-Key": key or uuid4().hex})


async def assert_no_billing(order_ids):
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(FinancialObligation).where(FinancialObligation.work_order_id.in_(order_ids))) == 0
        assert await db.scalar(select(func.count()).select_from(FinancialEntry).where(FinancialEntry.work_order_id.in_(order_ids))) == 0
        orders = list((await db.scalars(select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.id.in_(order_ids)))).all())
        assert all(order.status != "invoiced" for order in orders)


@pytest.mark.asyncio
async def test_batch_keeps_each_os_and_each_installment_total_and_invoice(postgres_client):
    client = postgres_client
    customer = await make_customer(client)
    amounts = ["100.01", "200.02", "0.03"]
    orders = [await make_order(client, customer, approved=value) for value in amounts]
    payload = make_payload(orders, amounts, ["100.01", "100.02", "100.03"])
    response = await post_batch(client, payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert Decimal(body["total_amount"]) == Decimal("300.06")
    assert len(body["work_orders"]) == 3
    for index, row in enumerate(body["work_orders"]):
        assert row["work_order_id"] == orders[index]["id"]
        assert Decimal(row["amount"]) == Decimal(amounts[index])
        obligation = row["obligation"]
        assert obligation["work_order_id"] == row["work_order_id"]
        assert sum(Decimal(entry["amount"]) for entry in obligation["installments"]) == Decimal(amounts[index])
        assert all(entry["billing_compliance"]["batch"]["batch_id"] == body["batch_id"] for entry in obligation["installments"])
        current = (await client.get(f"/laboratory/work-orders/{row['work_order_id']}")).json()
        assert current["status"] == "invoiced" and current["exit_invoice"] == payload["nfse_number"]
        assert current["version"] == orders[index]["version"] + 1
        receivables = await client.get(f"/finance/work-orders/{row['work_order_id']}/receivables")
        assert receivables.status_code == 200, receivables.text
        assert Decimal(receivables.json()["total_registered"]) == Decimal(amounts[index])
        assert Decimal(receivables.json()["remaining_to_issue"]) == 0
    for index, expected in enumerate(payload["installments"]):
        assert sum(Decimal(row["obligation"]["installments"][index]["amount"]) for row in body["work_orders"]) == Decimal(expected["amount"])
    selected = await client.get("/finance/work-orders", params={"ids": ",".join(str(order["id"]) for order in orders)})
    assert selected.status_code == 200, selected.text
    assert {row["id"] for row in selected.json()} == {order["id"] for order in orders}
    assert all(row["customer_id"] == customer["id"] and Decimal(row["remaining_to_issue"]) == 0 for row in selected.json())


@pytest.mark.asyncio
async def test_parallel_retries_replay_before_stale_versions_without_duplicate_income(postgres_client):
    client = postgres_client
    customer = await make_customer(client)
    orders = [await make_order(client, customer) for _ in range(2)]
    payload, key = make_payload(orders), uuid4().hex
    responses = await asyncio.wait_for(asyncio.gather(*[post_batch(client, payload, key) for _ in range(5)]), timeout=30)
    assert all(response.status_code == 201 for response in responses), [response.text for response in responses]
    ids = [[row["obligation"]["id"] for row in response.json()["work_orders"]] for response in responses]
    assert all(values == ids[0] for values in ids)
    replay = deepcopy(payload)
    replay["work_orders"].reverse()
    response = await post_batch(client, replay, key)
    assert response.status_code == 201, response.text
    changed = deepcopy(payload)
    changed["description"] += " diferente"
    conflict = await post_batch(client, changed, key)
    assert conflict.status_code == 409, conflict.text
    async with session_factory() as db:
        entries = list((await db.scalars(select(FinancialEntry).where(FinancialEntry.work_order_id.in_([order["id"] for order in orders])))).all())
        assert len(entries) == 2 and sum(row.amount for row in entries) == 200


@pytest.mark.asyncio
async def test_different_keys_cannot_bill_same_selection_concurrently(postgres_client):
    customer = await make_customer(postgres_client)
    orders = [await make_order(postgres_client, customer) for _ in range(2)]
    payload = make_payload(orders)
    reversed_payload = {**payload, "work_orders": list(reversed(payload["work_orders"]))}
    responses = await asyncio.wait_for(asyncio.gather(post_batch(postgres_client, payload), post_batch(postgres_client, reversed_payload)), timeout=30)
    assert sorted(response.status_code for response in responses) == [201, 409], [response.text for response in responses]


@pytest.mark.asyncio
@pytest.mark.parametrize("problem,expected", [("customer", 422), ("company", 422), ("legacy_customer", 422), ("version", 409), ("invoice_slots", 409), ("balance", 409), ("checklist", 422)])
async def test_validation_of_any_os_leaves_the_whole_batch_unchanged(postgres_client, problem, expected):
    client = postgres_client
    customer = await make_customer(client)
    other = await make_customer(client, "universo_automacao" if problem == "company" else "universo_eletronica")
    first = await make_order(client, customer)
    second = await make_order(client, other if problem in {"customer", "company"} else customer)
    orders = [first, second]
    payload = make_payload(orders)
    async with session_factory() as db:
        second_db = await db.get(LaboratoryWorkOrder, second["id"])
        if problem == "legacy_customer":
            second_db.customer_id = None
        elif problem == "version":
            second_db.version += 1
        elif problem == "invoice_slots":
            second_db.exit_invoice, second_db.exit_invoice_2, second_db.exit_invoice_3 = "1", "2", "3"
        elif problem == "balance":
            second_db.approved_value = Decimal("99.99")
        await db.commit()
    if problem == "checklist":
        response = await client.put(f"/customers/{customer['id']}/billing", json={"requires_purchase_order": True})
        assert response.status_code == 200, response.text
        payload["work_orders"][0]["billing_confirmation"] = {"purchase_order_number": "PO-OK"}
    response = await post_batch(client, payload)
    assert response.status_code == expected, response.text
    await assert_no_billing([order["id"] for order in orders])
    first_current = (await client.get(f"/laboratory/work-orders/{first['id']}")).json()
    assert first_current["exit_invoice"] is None and first_current["version"] == first["version"]


@pytest.mark.asyncio
async def test_failure_after_all_entries_and_os_changes_rolls_back_the_entire_transaction(postgres_client, monkeypatch):
    customer = await make_customer(postgres_client)
    orders = [await make_order(postgres_client, customer) for _ in range(2)]

    async def fail_notification(*args, **kwargs):
        raise RuntimeError("Simulated failure before commit")

    monkeypatch.setattr("app.finance.router.notify_activity", fail_notification)
    response = await post_batch(postgres_client, make_payload(orders))
    assert response.status_code == 500, response.text
    await assert_no_billing([order["id"] for order in orders])
    async with session_factory() as db:
        for order in orders:
            saved = await db.get(LaboratoryWorkOrder, order["id"])
            assert saved.exit_invoice is None and saved.version == order["version"]


@pytest.mark.asyncio
async def test_no_approved_value_accepts_explicit_amount_and_documents_do_not_overwrite(postgres_client):
    customer = await make_customer(postgres_client)
    orders = [await make_order(postgres_client, customer, approved=None, exit_invoice="ANTIGA") for _ in range(2)]
    payload = make_payload(orders, ["12.34", "56.78"], nfse_number="SERVICO", nfe_number="MERCADORIA")
    missing_choice = await post_batch(postgres_client, payload)
    assert missing_choice.status_code == 422, missing_choice.text
    response = await post_batch(postgres_client, {**payload, "exit_invoice": "MERCADORIA"})
    assert response.status_code == 201, response.text
    for order in orders:
        saved = (await postgres_client.get(f"/laboratory/work-orders/{order['id']}")).json()
        assert saved["exit_invoice"] == "ANTIGA" and saved["exit_invoice_2"] == "MERCADORIA"
        assert saved["exit_invoice_3"] is None


@pytest.mark.asyncio
async def test_single_entry_nf_sync_is_compatible_and_legacy_edit_preserves_document(postgres_client):
    client = postgres_client
    customer = await make_customer(client)
    order = await make_order(client, customer)
    data = make_payload([order])
    data.pop("work_orders")
    data.pop("installments")
    data.pop("total_amount")
    data.update(work_order_id=order["id"], amount="100.00", due_date="2026-12-26", work_order_version=order["version"])
    response = await client.post("/finance/entries", json=data, headers={"Idempotency-Key": uuid4().hex})
    assert response.status_code == 201, response.text
    entry = response.json()
    current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    assert current["exit_invoice"] == data["nfse_number"] and current["version"] == order["version"] + 1
    changed = await client.patch(f"/laboratory/work-orders/{order['id']}", json={"version": current["version"], "exit_invoice": "CORRIGIDA"})
    assert changed.status_code == 200, changed.text
    legacy_edit = {key: value for key, value in data.items() if key != "work_order_version"}
    response = await client.put(f"/finance/entries/{entry['id']}", json={**legacy_edit, "description": "Descrição corrigida"})
    assert response.status_code == 200, response.text
    after = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    assert after["exit_invoice"] == "CORRIGIDA" and after["exit_invoice_2"] is None
    assert after["version"] == changed.json()["version"]
    response = await client.put(f"/finance/entries/{entry['id']}", json={**legacy_edit, "exit_invoice": "NOVA", "work_order_version": after["version"]})
    assert response.status_code == 200, response.text
    after = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    assert after["exit_invoice"] == "CORRIGIDA" and after["exit_invoice_2"] == "NOVA"
    assert after["version"] == changed.json()["version"] + 1
    async with session_factory() as db:
        events = list((await db.scalars(select(LaboratoryAuditEvent).where(
            LaboratoryAuditEvent.work_order_id == order["id"],
            LaboratoryAuditEvent.action == "finance_exit_invoice_registered",
        ))).all())
        assert len(events) == 2 and any("NOVA" in event.description for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["entries", "obligations"])
async def test_single_creation_parallel_retry_checks_saved_key_before_version(postgres_client, endpoint):
    client = postgres_client
    order = await make_order(client, await make_customer(client))
    data = make_payload([order])
    data.pop("work_orders")
    data.update(work_order_id=order["id"], work_order_version=order["version"])
    if endpoint == "entries":
        data.pop("installments")
        data.pop("total_amount")
        data.update(amount="100.00", due_date="2026-12-26")
    key = uuid4().hex
    responses = await asyncio.wait_for(asyncio.gather(*[
        client.post(f"/finance/{endpoint}", json=data, headers={"Idempotency-Key": key}) for _ in range(3)
    ]), timeout=30)
    assert all(response.status_code == 201 for response in responses), [response.text for response in responses]
    assert len({response.json()["id"] for response in responses}) == 1
    current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    assert current["version"] == order["version"] + 1 and current["exit_invoice"] == data["nfse_number"]


@pytest.mark.asyncio
async def test_editing_a_batch_installment_preserves_each_os_scope_and_batch_trace(postgres_client):
    client = postgres_client
    customer = await make_customer(client)
    orders = [await make_order(client, customer) for _ in range(2)]
    response = await post_batch(client, make_payload(orders, installments=["100.00", "100.00"]))
    assert response.status_code == 201, response.text
    batch = response.json()
    first_obligation = batch["work_orders"][0]["obligation"]
    entry = first_obligation["installments"][0]
    current = (await client.get(f"/laboratory/work-orders/{orders[0]['id']}")).json()
    # Contrato legado: omite a nova lista, cujo escopo é a obrigação inteira.
    legacy_payload = {key: value for key, value in entry.items() if key != "work_orders"}
    response = await client.put(f"/finance/entries/{entry['id']}", json={
        **legacy_payload, "nfse_number": "NF-CORRIGIDA", "exit_invoice": "NF-CORRIGIDA",
        "work_order_version": current["version"], "description": "Correção apenas desta OS",
    })
    assert response.status_code == 200, response.text
    edited = await client.get(f"/finance/obligations/{first_obligation['id']}")
    assert edited.status_code == 200, edited.text
    assert all(row["nfse_number"] == "NF-CORRIGIDA" for row in edited.json()["installments"])
    assert all(row["billing_compliance"]["batch"]["batch_id"] == batch["batch_id"] for row in edited.json()["installments"])
    unchanged = await client.get(f"/finance/obligations/{batch['work_orders'][1]['obligation']['id']}")
    assert unchanged.json()["nfse_number"] != "NF-CORRIGIDA"
    assert Decimal(edited.json()["total_amount"]) == Decimal(unchanged.json()["total_amount"]) == 100
    current = (await client.get(f"/laboratory/work-orders/{orders[0]['id']}")).json()
    assert current["exit_invoice_2"] == "NF-CORRIGIDA" and current["version"] == orders[0]["version"] + 2
