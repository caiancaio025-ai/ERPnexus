"""Ciclos de vida e gravações simultâneas no banco PostgreSQL descartável."""

import asyncio
import base64
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.db import session_factory
from app.employees.models import EmployeeAuditEvent
from app.laboratory import router as laboratory
from app.laboratory.models import LaboratoryWorkOrder


async def new_order(client):
    response = await client.post("/laboratory/work-orders", json={
        "company_code": "universo_eletronica", "customer_name": "Cliente teste de ciclo",
        "reported_defect": "Falha de teste", "manufacturer": "WEG",
    })
    assert response.status_code == 201, response.text
    return response.json()


async def new_employee(client):
    response = await client.post("/employees", json={
        "company_code": "universo_eletronica", "full_name": "Colaborador " + "X" * 168,
        "document": f"{uuid4().int % 10**11:011d}", "department": "Laboratório",
        "position": "Técnico", "salary_base": "2500.00", "hiring_date": "2026-01-10",
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_first_label_concurrency_uses_one_persistent_tracking_token(postgres_client, monkeypatch):
    order = await new_order(postgres_client)
    tokens = []

    def capture_token(work_order, equipment, token):
        tokens.append(token)
        return b"%PDF-1.4\nTracking-token regression test"

    monkeypatch.setattr(laboratory, "label_pdf", capture_token)
    results = await asyncio.gather(*[
        postgres_client.get(f"/laboratory/work-orders/{order['id']}/label.pdf") for _ in range(5)
    ])
    assert all(row.status_code == 200 for row in results), [row.text for row in results]
    assert len(tokens) == 5 and len(set(tokens)) == 1
    async with session_factory() as db:
        stored = await db.get(LaboratoryWorkOrder, order["id"])
        assert stored.tracking_token == tokens[0]


@pytest.mark.asyncio
async def test_painting_return_cannot_race_item_uncheck(postgres_client):
    client = postgres_client
    order = await new_order(client)
    response = await client.post(f"/laboratory/work-orders/{order['id']}/mechanics/painting", json={"provider": "Pintura teste", "items": ["Tampa"]})
    assert response.status_code == 201, response.text
    dispatch = response.json()
    item_id = dispatch["items"][0]["id"]
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7R0AAAAASUVORK5CYII=")
    photo = await client.post(f"/laboratory/mechanics/painting/{dispatch['id']}/photos?phase=outbound&item_id={item_id}", files={"file": ("tampa.png", png, "image/png")})
    assert photo.status_code == 201, photo.text
    sent = await client.post(f"/laboratory/mechanics/painting/{dispatch['id']}/send")
    assert sent.status_code == 200, sent.text
    checked = await client.patch(f"/laboratory/mechanics/painting/items/{item_id}", json={"returned": True})
    assert checked.status_code == 200, checked.text
    returned, unchecked = await asyncio.gather(
        client.post(f"/laboratory/mechanics/painting/{dispatch['id']}/return"),
        client.patch(f"/laboratory/mechanics/painting/items/{item_id}", json={"returned": False}),
    )
    assert (returned.status_code, unchecked.status_code) in {(200, 409), (422, 200)}, [returned.text, unchecked.text]
    current = await client.get(f"/laboratory/work-orders/{order['id']}/mechanics/painting")
    assert current.status_code == 200, current.text
    stored = next(row for row in current.json() if row["id"] == dispatch["id"])
    assert stored["items"][0]["returned"] == (stored["status"] == "returned")


@pytest.mark.asyncio
async def test_employee_termination_is_atomic_returns_history_and_accepts_full_reason(postgres_client):
    client = postgres_client
    employee = await new_employee(client)
    reason = "R" * 500
    responses = await asyncio.gather(*[
        client.post(f"/employees/{employee['id']}/terminate", json={"termination_date": "2026-11-25", "reason_end": reason})
        for _ in range(2)
    ])
    assert sorted(row.status_code for row in responses) == [200, 409], [row.text for row in responses]
    saved = next(row.json() for row in responses if row.status_code == 200)
    assert saved["is_active"] is False
    assert len(saved["employment_history"]) == 1
    assert saved["employment_history"][0]["reason_end"] == reason
    current = (await client.get(f"/employees/{employee['id']}")).json()
    assert len(current["employment_history"]) == 1
    async with session_factory() as db:
        events = (await db.scalars(select(EmployeeAuditEvent).where(
            EmployeeAuditEvent.employee_id == employee["id"], EmployeeAuditEvent.action == "employee_terminated",
        ))).all()
        assert len(events) == 1 and len(events[0].description) <= 500


@pytest.mark.asyncio
async def test_employee_rejects_termination_before_hiring(postgres_client):
    employee = await new_employee(postgres_client)
    response = await postgres_client.post(f"/employees/{employee['id']}/terminate", json={
        "termination_date": "2025-12-01", "reason_end": "Data incorreta",
    })
    assert response.status_code == 422, response.text
    current = (await postgres_client.get(f"/employees/{employee['id']}")).json()
    assert current["is_active"] is True and current["employment_history"] == []


@pytest.mark.asyncio
async def test_parallel_finance_receipts_invoice_os_once(postgres_client):
    client = postgres_client
    order = await new_order(client)
    payload = {
        "entry_type": "income", "company_code": "universo_eletronica", "counterparty_name": "Cliente teste",
        "description": "Receita de teste", "amount": "50.00", "issue_date": "2026-11-25",
        "posting_date": "2026-11-25", "due_date": "2026-12-25", "bank_name": "Bradesco", "work_order_id": order["id"],
        "nfse_number": "TESTE-V48-123",
    }
    receipts = await asyncio.gather(*[client.post("/finance/entries", json=payload) for _ in range(3)])
    assert all(row.status_code == 201 for row in receipts), [row.text for row in receipts]
    assert len({row.json()["id"] for row in receipts}) == 3
    current = (await client.get(f"/laboratory/work-orders/{order['id']}")).json()
    assert current["status"] == "invoiced" and current["version"] == order["version"] + 1
    history = (await client.get(f"/laboratory/work-orders/{order['id']}/history")).json()
    assert len([row for row in history if row["new_status"] == "invoiced"]) == 1
