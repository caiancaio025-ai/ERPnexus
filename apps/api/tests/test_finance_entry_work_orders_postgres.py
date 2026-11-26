"""Inclusão/remoção de várias OS no mesmo modal e no mesmo título financeiro."""
import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select


async def orders_for(client, count=3, *, approved="100000.00"):
    customer = await client.post("/customers", json={"company_code": "universo_eletronica", "legal_name": f"Cliente modal {uuid4().hex}"})
    assert customer.status_code == 201, customer.text
    rows = []
    for _ in range(count):
        response = await client.post("/laboratory/work-orders", json={"company_code": "universo_eletronica",
            "customer_id": customer.json()["id"], "customer_name": customer.json()["legal_name"],
            "reported_defect": "Equipamento entregue para reparo", "model": "Unidade teste", "approved_value": approved})
        assert response.status_code == 201, response.text
        rows.append(response.json())
    return rows


def base_payload():
    return {"entry_type": "income", "company_code": "universo_eletronica", "nfse_number": uuid4().hex[:12],
            "counterparty_name": "Cliente modal", "description": "Receita original preservada", "amount": "300.00",
            "issue_date": "2026-11-26", "posting_date": "2026-11-26", "due_date": "2026-12-20", "bank_name": "Itaú"}


def links(orders, amounts):
    return [{"work_order_id": row.get("work_order_id", row.get("id")), "version": row["version"], "amount": value}
            for row, value in zip(orders, amounts, strict=True)]


def edit_payload(entry, work_orders=None, **changes):
    body = {key: entry[key] for key in base_payload()}
    body.update(work_order_id=entry["work_order_id"], version=entry["version"])
    if work_orders is not None:
        body.update(work_orders=work_orders, work_order_id=work_orders[0]["work_order_id"] if len(work_orders) == 1 else None)
    if entry["obligation_id"]:
        body.update(obligation_version=entry["obligation_version"], obligation_total_amount=entry["obligation_total_amount"])
    body.update(changes)
    return body


async def create_entry(client, **changes):
    response = await client.post("/finance/entries", json={**base_payload(), **changes}, headers={"Idempotency-Key": uuid4().hex})
    assert response.status_code == 201, response.text
    result = await client.get(f"/finance/entries/{response.json()['id']}")
    assert result.status_code == 200, result.text
    return result.json()


async def create_obligation(client, orders, amounts=None, installments=None, **changes):
    amounts = amounts or ["100.00"] * len(orders)
    installments = installments or ["150.00", "100.00", "50.00"]
    body = base_payload()
    body.pop("amount"); body.pop("due_date")
    body.update(total_amount=str(sum(map(Decimal, amounts))), work_orders=links(orders, amounts),
                installments=[{"installment_number": index, "amount": amount, "due_date": f"2026-12-{index:02d}"}
                              for index, amount in enumerate(installments, 1)])
    body.update(changes)
    response = await client.post("/finance/obligations", json=body, headers={"Idempotency-Key": uuid4().hex})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_existing_single_receipt_adds_removes_orders_without_creating_income(postgres_client):
    from app.core.db import session_factory
    from app.finance.models import FinancialEntry
    client = postgres_client
    orders = await orders_for(client, 2)
    entry = await create_entry(client, work_order_id=orders[0]["id"], work_order_version=orders[0]["version"])
    assert len(entry["work_orders"]) == 1 and entry["work_orders"][0]["amount"] == "300.00"
    selection = links([entry["work_orders"][0], orders[1]], ["100.00", "200.00"])
    response = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, selection))
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["id"] == entry["id"] and saved["amount"] == "300.00" and saved["version"] == 2
    assert saved["work_order_id"] is None and len(saved["work_orders"]) == 2
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(FinancialEntry).where(FinancialEntry.nfse_number == entry["nfse_number"])) == 1
    for order, amount in zip(orders, ["100.00", "200.00"], strict=True):
        response = await client.get(f"/finance/work-orders/{order['id']}/receivables")
        assert response.status_code == 200, response.text
        assert response.json()["total_registered"] == amount
        assert response.json()["installments"][0]["amount"] == "300.00"
        assert response.json()["installments"][0]["work_order_amount"] == amount
    second = saved["work_orders"][1]
    removed = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(saved, links([second], ["300.00"])))
    assert removed.status_code == 200, removed.text
    assert len(removed.json()["work_orders"]) == 1
    cleared = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(removed.json(), []))
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["amount"] == "300.00" and cleared.json()["work_orders"] == []
    assert (await client.get(f"/finance/work-orders/{orders[1]['id']}/receivables")).json()["total_registered"] == "0.00"


@pytest.mark.asyncio
async def test_existing_installment_edits_whole_obligation_and_preserves_paid_history(postgres_client):
    client = postgres_client
    orders = await orders_for(client, 3)
    obligation = await create_obligation(client, orders[:2], ["100.00", "200.00"])
    ids = [row["id"] for row in obligation["installments"]]
    assert len(ids) == 3 and len(obligation["work_orders"]) == 2
    entry = obligation["installments"][1]
    selected = links(entry["obligation_work_orders"] + [orders[2]], ["100.00", "100.00", "100.00"])
    edited = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, selected))
    assert edited.status_code == 200, edited.text
    current = (await client.get(f"/finance/obligations/{obligation['id']}")).json()
    assert [row["id"] for row in current["installments"]] == ids
    assert [row["amount"] for row in current["installments"]] == ["150.00", "100.00", "50.00"]
    assert current["total_amount"] == "300.00" and current["version"] == 2
    assert [row["amount"] for row in current["work_orders"]] == ["100.00"] * 3
    settled = await client.post(f"/finance/entries/{ids[0]}/settle", json={"settlement_date": "2026-11-26"})
    assert settled.status_code == 200, settled.text
    assert not settled.json()["work_order_links_editable"]
    entry = (await client.get(f"/finance/entries/{ids[1]}")).json()
    blocked = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, []))
    assert blocked.status_code == 409 and "baixada" in blocked.text
    notes = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, notes="Observação corrigida sem alterar as OS"))
    assert notes.status_code == 200, notes.text
    current = (await client.get(f"/finance/obligations/{obligation['id']}")).json()
    assert [row["id"] for row in current["installments"]] == ids
    assert current["installments"][0]["status"] == "received"
    assert current["installments"][0]["settlement_date"] == "2026-11-26"
    assert current["total_amount"] == "300.00" and len(current["work_orders"]) == 3
    for order in orders:
        totals = (await client.get(f"/finance/work-orders/{order['id']}/receivables")).json()
        assert totals["total_registered"] == "100.00" and totals["total_received"] == "50.00"


@pytest.mark.asyncio
async def test_concurrent_link_edits_use_entry_version_and_do_not_lose_selection(postgres_client):
    client = postgres_client
    orders = await orders_for(client, 3)
    entry = await create_entry(client)
    edits = await asyncio.gather(*[client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry,
        links([orders[0], other], ["100.00", "200.00"]))) for other in orders[1:]])
    assert sorted(row.status_code for row in edits) == [200, 409], [row.text for row in edits]
    winner = next(row.json() for row in edits if row.status_code == 200)
    assert (await client.get(f"/finance/entries/{entry['id']}")).json() == winner


@pytest.mark.asyncio
async def test_new_obligation_and_schedule_allow_zero_cells_and_keep_exact_totals(postgres_client):
    client = postgres_client
    orders = await orders_for(client, 3)
    obligation = await create_obligation(client, orders, ["0.01", "0.02", "0.03"], ["0.01", "0.05"])
    assert len(obligation["installments"]) == 2
    assert any(row["amount"] == "0.00" for row in obligation["installments"][0]["work_orders"])
    schedule = {"version": obligation["version"], "total_amount": "0.12", "installments": [
        {"entry_id": obligation["installments"][0]["id"], "installment_number": 1, "amount": "0.07", "due_date": "2026-12-03"},
        {"entry_id": obligation["installments"][1]["id"], "installment_number": 2, "amount": "0.05", "due_date": "2026-12-04"},
    ]}
    updated = await client.put(f"/finance/obligations/{obligation['id']}/schedule", json=schedule)
    assert updated.status_code == 200, updated.text
    assert [row["amount"] for row in updated.json()["work_orders"]] == ["0.02", "0.04", "0.06"]
    assert [row["id"] for row in updated.json()["installments"]] == [row["id"] for row in obligation["installments"]]
    assert (await client.put(f"/finance/obligations/{obligation['id']}/schedule", json=schedule)).status_code == 409


@pytest.mark.asyncio
async def test_shared_receipt_blocks_cancel_and_inactivation_and_is_searchable(postgres_client):
    client = postgres_client
    orders = await orders_for(client, 2)
    entry = await create_entry(client, work_orders=links(orders, ["100.00", "200.00"]))
    for order in orders:
        current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
        cancelled = await client.post(f"/laboratory/work-orders/{order['id']}/status", json={"version": current["version"], "status": "cancelled"})
        assert cancelled.status_code == 409, cancelled.text
        inactive = await client.post(f"/laboratory/work-orders/{order['id']}/inactivate", json={"version": current["version"], "reason": "Inativação de teste bloqueada"})
        assert inactive.status_code == 409, inactive.text
        search = await client.get("/finance/entries", params={"search": order["number"]})
        assert search.status_code == 200, search.text
        assert entry["id"] in [row["id"] for row in search.json()["items"]]
    assert (await client.get(f"/finance/entries/{entry['id']}")).json()["status"] == "pending"


@pytest.mark.asyncio
async def test_paid_single_os_obligation_allows_metadata_when_link_fields_are_omitted(postgres_client):
    client = postgres_client
    orders = await orders_for(client, 1)
    obligation = await create_obligation(client, orders, ["300.00"], ["150.00", "150.00"])
    first, second = obligation["installments"]
    assert (await client.post(f"/finance/entries/{first['id']}/settle", json={"settlement_date": "2026-11-26"})).status_code == 200
    current = (await client.get(f"/finance/entries/{second['id']}")).json()
    payload = edit_payload(current, notes="Documento corrigido sem alterar vínculo ou baixa", nfe_number="NF-HISTORICA")
    payload.pop("work_order_id")
    response = await client.put(f"/finance/entries/{second['id']}", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["work_order_id"] == orders[0]["id"]
    assert response.json()["obligation_work_orders"][0]["amount"] == "300.00"
    received = (await client.get(f"/finance/entries/{first['id']}")).json()
    assert received["status"] == "received" and received["amount"] == "150.00" and received["settlement_date"] == "2026-11-26"
    order = (await client.get(f"/laboratory/work-orders/{orders[0]['id']}")).json()
    assert order["exit_invoice_2"] is None  # Não sincroniza nova NF de OS em baixa histórica.


@pytest.mark.asyncio
async def test_link_checklist_revalidates_only_new_or_increased_allocations(postgres_client):
    client = postgres_client
    orders = await orders_for(client, 2)
    entry = await create_entry(client, work_orders=links(orders[:1], ["300.00"]))
    profile = await client.put(f"/customers/{orders[0]['customer_id']}/billing", json={"requires_purchase_order": True})
    assert profile.status_code == 200, profile.text
    current_links = links(entry["work_orders"], ["300.00"])
    current_links[0]["billing_confirmation"] = {"purchase_order_number": "", "customer_order_number": "",
        "measurement_reference": "", "portal_protocol": "", "notes": "",
        "service_report_confirmed": False, "portal_submitted": False,
        "invoice_email_confirmed": False, "xml_email_confirmed": False}
    unchanged = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, current_links, notes="Correção documental"))
    assert unchanged.status_code == 200, unchanged.text
    current = unchanged.json()
    selected = links([current["work_orders"][0], orders[1]], ["100.00", "200.00"])
    missing = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(current, selected))
    assert missing.status_code == 422 and "Faturamento bloqueado" in missing.text
    selected[1]["billing_confirmation"] = {"purchase_order_number": "PC-CLIENTE-123"}
    confirmed = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(current, selected))
    assert confirmed.status_code == 200, confirmed.text
    assert len(confirmed.json()["work_orders"]) == 2


@pytest.mark.asyncio
async def test_creation_replay_and_settlement_race_never_duplicate_or_rewrite_paid_income(postgres_client):
    client = postgres_client
    orders = await orders_for(client, 3)
    payload = {**base_payload(), "work_orders": links(orders[:2], ["100.00", "200.00"])}
    headers = {"Idempotency-Key": uuid4().hex}
    replies = await asyncio.gather(*[client.post("/finance/entries", json=payload, headers=headers) for _ in range(3)])
    assert all(row.status_code == 201 for row in replies), [row.text for row in replies]
    assert len({row.json()["id"] for row in replies}) == 1
    entry = replies[0].json()
    selection = links([entry["work_orders"][0], orders[2]], ["100.00", "200.00"])
    edit, settle = await asyncio.gather(
        client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, selection)),
        client.post(f"/finance/entries/{entry['id']}/settle", json={"settlement_date": "2026-11-26"}),
    )
    assert settle.status_code in {200, 409} and edit.status_code in {200, 409}, [edit.text, settle.text]
    assert 200 in {edit.status_code, settle.status_code}
    if settle.status_code == 409:
        # A troca de OS enquanto a baixa esperava exige revisão explícita, sem
        # adquirir novas travas fora de ordem ou baixar uma seleção antiga.
        assert edit.status_code == 200
        reviewed = await client.get(f"/finance/entries/{entry['id']}")
        assert reviewed.status_code == 200 and reviewed.json()["status"] == "pending"
        settle = await client.post(f"/finance/entries/{entry['id']}/settle", json={"settlement_date": "2026-11-26"})
        assert settle.status_code == 200, settle.text
    current = (await client.get(f"/finance/entries/{entry['id']}")).json()
    assert current["status"] == "received" and current["amount"] == "300.00"
    assert [row["work_order_id"] for row in current["work_orders"]] == [orders[0]["id"], orders[2 if edit.status_code == 200 else 1]["id"]]
    blocked = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(current, []))
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_closed_period_and_wrong_company_account_do_not_modify_receipt(postgres_client):
    from app.core.db import session_factory
    from app.finance.models import FinancialAccount, FinancialPeriodClosure
    client = postgres_client
    orders = await orders_for(client, 2)
    entry = await create_entry(client, posting_date="2028-11-26")
    async with session_factory() as db:
        account = FinancialAccount(company_code="universo_automacao", name=f"Conta {uuid4().hex}")
        db.add(account); await db.commit()
        account_id = account.id
    wrong = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, links(orders, ["100.00", "200.00"]), account_id=account_id))
    assert wrong.status_code == 422 and "outra empresa" in wrong.text
    user = (await client.get("/auth/me")).json()
    async with session_factory() as db:
        closure = FinancialPeriodClosure(company_code="universo_eletronica", year=2028, month=11, closed_by=user["id"], is_closed=True, snapshot_data={})
        db.add(closure); await db.commit()
        closure_id = closure.id
    try:
        current = (await client.get(f"/finance/entries/{entry['id']}")).json()
        assert not current["work_order_links_editable"] and "competência" in current["work_order_links_lock_reason"]
        blocked = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(current, links(orders, ["100.00", "200.00"])))
        assert blocked.status_code == 409, blocked.text
        stored = (await client.get(f"/finance/entries/{entry['id']}")).json()
        assert stored["version"] == entry["version"] and stored["work_orders"] == [] and stored["amount"] == "300.00"
    finally:
        async with session_factory() as db:
            closure = await db.get(FinancialPeriodClosure, closure_id)
            await db.delete(closure); await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("installment", [False, True])
async def test_omitted_account_and_category_are_preserved_but_explicit_null_clears(postgres_client, installment):
    from app.core.db import session_factory
    from app.finance.models import FinancialAccount, FinancialCategory, FinancialEntry
    client = postgres_client
    async with session_factory() as db:
        account = FinancialAccount(company_code="universo_eletronica", name=f"Conta preservada {uuid4().hex}")
        category = FinancialCategory(name=f"Categoria preservada {uuid4().hex}", entry_type="income")
        db.add_all([account, category])
        await db.commit()
        account_id, category_id = account.id, category.id
    if installment:
        obligation = await create_obligation(client, await orders_for(client, 1), ["300.00"],
            account_id=account_id, category_id=category_id)
        entry = obligation["installments"][1]
    else:
        entry = await create_entry(client, account_id=account_id, category_id=category_id)
    changed = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, notes="Somente observação"))
    assert changed.status_code == 200, changed.text
    current = changed.json()
    assert current["account_id"] == account_id and current["category_id"] == category_id
    assert current["amount"] == entry["amount"]
    if not installment:
        wrong_company = await client.put(f"/finance/entries/{entry['id']}",
            json=edit_payload(current, company_code="universo_automacao", bank_name="Banco do Brasil"))
        assert wrong_company.status_code == 422 and "outra empresa" in wrong_company.text
    cleared = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(current, account_id=None, category_id=None))
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["account_id"] is None and cleared.json()["category_id"] is None
    async with session_factory() as db:
        stored = await db.get(FinancialEntry, entry["id"])
        assert stored.account_id is None and stored.category_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("installment", [False, True])
async def test_removing_all_orders_preserves_two_invoices_without_requesting_output_invoice(postgres_client, installment):
    client = postgres_client
    orders = await orders_for(client, 2)
    invoices = {"nfse_number": "340", "nfe_number": "1750", "exit_invoice": "1750"}
    if installment:
        obligation = await create_obligation(client, orders, ["100.00", "200.00"], **invoices)
        entry = obligation["installments"][0]
    else:
        entry = await create_entry(client, work_orders=links(orders, ["100.00", "200.00"]), **invoices)
    response = await client.put(f"/finance/entries/{entry['id']}",
        json=edit_payload(entry, [], nfe_number="1750"))
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["id"] == entry["id"] and saved["amount"] == entry["amount"]
    assert saved["nfse_number"] == "340" and saved["nfe_number"] == "1750"
    assert saved["work_orders"] == [] and saved["work_order_id"] is None
    if installment:
        assert saved["obligation_total_amount"] == "300.00" and saved["obligation_work_orders"] == []
        after = (await client.get(f"/finance/obligations/{obligation['id']}")).json()
        assert [row["id"] for row in after["installments"]] == [row["id"] for row in obligation["installments"]]
        assert all(row["work_orders"] == [] for row in after["installments"])
    for order in orders:
        stored = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
        assert stored["exit_invoice"] == "1750"  # Documento histórico não é apagado.


@pytest.mark.asyncio
async def test_closing_waits_for_financial_writer_and_snapshots_its_committed_amount(postgres_client, monkeypatch):
    from app.finance import router as finance
    client = postgres_client
    entry = await create_entry(client, posting_date="2030-02-20", issue_date="2030-02-20", due_date="2030-03-01")
    writer_ready, release_writer, closer_ready = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_notify, original_lock = finance.notify_activity, finance.lock_period

    async def paused_notify(db, **kwargs):
        if kwargs.get("action") == "finance_entry_updated" and kwargs.get("entity_id") == entry["id"]:
            writer_ready.set()
            await asyncio.wait_for(release_writer.wait(), 10)
        return await original_notify(db, **kwargs)

    async def observed_lock(db, company_code, year, month, *, exclusive=False):
        if exclusive and (year, month) == (2030, 2):
            closer_ready.set()
        await original_lock(db, company_code, year, month, exclusive=exclusive)

    monkeypatch.setattr(finance, "notify_activity", paused_notify)
    monkeypatch.setattr(finance, "lock_period", observed_lock)
    period = {"company_code": "universo_eletronica", "year": 2030, "month": 2}
    update_task = asyncio.create_task(client.put(f"/finance/entries/{entry['id']}", json=edit_payload(entry, amount="321.00")))
    close_task = None
    try:
        await asyncio.wait_for(writer_ready.wait(), 10)
        close_task = asyncio.create_task(client.post("/finance/closures/close", json=period))
        await asyncio.wait_for(closer_ready.wait(), 10)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(close_task), 0.15)
        release_writer.set()
        updated, closed = await asyncio.wait_for(asyncio.gather(update_task, close_task), 10)
        assert updated.status_code == 200, updated.text
        assert closed.status_code == 200, closed.text
        assert Decimal(str(closed.json()["snapshot_data"]["period_income"])) == Decimal("321.00")
        blocked = await client.put(f"/finance/entries/{entry['id']}", json=edit_payload(updated.json(), amount="400.00"))
        assert blocked.status_code == 409 and "fechada" in blocked.text
        assert (await client.get(f"/finance/entries/{entry['id']}")).json()["amount"] == "321.00"
    finally:
        release_writer.set()
        await asyncio.gather(update_task, *([close_task] if close_task else []), return_exceptions=True)
        await client.post("/finance/closures/reopen", json=period)


@pytest.mark.asyncio
async def test_cancelled_revenue_cannot_be_revived_by_late_settlement_or_reversal(postgres_client):
    client = postgres_client
    order = (await orders_for(client, 1))[0]
    entry = await create_entry(client, work_orders=links([order], ["300.00"]))
    current_order = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    cancelled = await client.post(f"/laboratory/work-orders/{order['id']}/status",
        json={"version": current_order["version"], "status": "cancelled"})
    assert cancelled.status_code == 200, cancelled.text
    before = (await client.get(f"/finance/entries/{entry['id']}")).json()
    assert before["status"] == "cancelled"
    late_settle = await client.post(f"/finance/entries/{entry['id']}/settle", json={"settlement_date": "2026-11-26"})
    late_reverse = await client.post(f"/finance/entries/{entry['id']}/unsettle")
    assert late_settle.status_code == late_reverse.status_code == 409
    after = (await client.get(f"/finance/entries/{entry['id']}")).json()
    assert after["status"] == "cancelled" and after["settlement_date"] is None
    assert after["version"] == before["version"] and after["amount"] == "300.00"


@pytest.mark.asyncio
async def test_laboratory_cancellation_cannot_change_income_in_closed_period(postgres_client):
    client = postgres_client
    order = (await orders_for(client, 1))[0]
    entry = await create_entry(client, work_orders=links([order], ["300.00"]),
        posting_date="2032-04-20", issue_date="2032-04-20", due_date="2032-05-01")
    period = {"company_code": "universo_eletronica", "year": 2032, "month": 4}
    closed = await client.post("/finance/closures/close", json=period)
    assert closed.status_code == 200, closed.text
    try:
        current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
        blocked = await client.post(f"/laboratory/work-orders/{order['id']}/status",
            json={"version": current["version"], "status": "cancelled"})
        assert blocked.status_code == 409 and "fechada" in blocked.text
        saved = (await client.get(f"/finance/entries/{entry['id']}")).json()
        assert saved["status"] == "pending" and saved["version"] == entry["version"]
        order_after = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
        assert order_after["status"] == current["status"] and order_after["version"] == current["version"]
    finally:
        assert (await client.post("/finance/closures/reopen", json=period)).status_code == 200
