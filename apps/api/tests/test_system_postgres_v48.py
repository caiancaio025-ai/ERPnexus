"""Cross-module HTTP regression on the migrated, disposable PostgreSQL database."""
import asyncio
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import httpx
import pytest
from reportlab.pdfgen import canvas

from app.core.db import session_factory
from app.notifications.models import Notification
from sqlalchemy import select

pytestmark = pytest.mark.integration
COMPANY = "universo_eletronica"


async def ok(client, method, path, status=200, **kwargs):
    response = await client.request(method, path, **kwargs)
    assert response.status_code == status, f"{method} {path}: {response.status_code} {response.text[:1800]}"
    return response.json() if response.content else None


async def customer(client):
    return await ok(client, "POST", "/customers", 201, json={
        "company_code": COMPANY, "legal_name": f"Cliente teste {uuid4().hex[:12]}",
        "city": "Recife", "state": "PE",
    })


async def work_order(client, **extra):
    c = await customer(client)
    return await ok(client, "POST", "/laboratory/work-orders", 201, json={
        "company_code": COMPANY, "customer_id": c["id"], "customer_name": c["legal_name"],
        "reported_defect": "Falha intermitente de alimentação", "equipment_type": "Inversor",
        **extra,
    })


def pdf_bytes():
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawString(40, 800, "Documento sintetico de teste V48")
    document.save()
    return output.getvalue()


@pytest.mark.parametrize("path", [
    "/auth/me", "/health/live", "/health/ready", "/dashboard/summary",
    "/customers/page", "/customers", "/employees/access",
    "/employees?company_code=universo_eletronica", "/finance/summary",
    "/finance/entries", "/finance/date-bounds", "/finance/audit",
    "/finance/work-orders", "/purchasing/summary", "/purchasing/orders",
    "/purchasing/suppliers", "/purchasing/material-requests", "/purchasing/stock-options?company_code=universo_eletronica",
    "/purchasing/reports/spending?start_date=2026-01-01&end_date=2026-12-31",
    "/laboratory/summary", "/laboratory/work-orders", "/laboratory/periods",
    "/laboratory/technicians", "/laboratory/workflow-options", "/laboratory/locations/map",
    "/laboratory/settings/companies", "/laboratory/settings/locations",
    "/inventory/map", "/inventory/items", "/commercial/companies",
    "/commercial/equipment", "/commercial/quotes", "/commercial/preventive-orders",
    "/commercial/asset-map", "/notifications", "/notifications/history",
    "/notifications/actors", "/notifications/push/config",
])
async def test_authenticated_module_reads(postgres_client, path):
    response = await postgres_client.get(path)
    assert response.status_code == 200, f"{path}: {response.text[:1200]}"
    assert response.headers.get("X-Request-ID")
    assert response.json() is not None


async def test_customer_contacts_billing_notes_and_document_roundtrip(postgres_client):
    c = await customer(postgres_client)
    cid = c["id"]
    saved = await ok(postgres_client, "PUT", f"/customers/{cid}", json={
        "legal_name": c["legal_name"], "city": "Jaboatão", "state": "PE", "phone": "81999990000",
    })
    assert saved["city"] == "Jaboatão"
    contact = await ok(postgres_client, "POST", f"/customers/{cid}/contacts", 201, json={"name": "Compras teste", "is_primary": True})
    await ok(postgres_client, "PUT", f"/customers/{cid}/contacts/{contact['id']}", json={"name": "Compras atualizado", "is_primary": True})
    billing = await ok(postgres_client, "PUT", f"/customers/{cid}/billing", json={"payment_term_days": 30})
    assert billing["payment_term_days"] == 30
    note = await ok(postgres_client, "POST", f"/customers/{cid}/notes", 201, json={"text": "Registro de homologação sintética"})
    assert note["customer_id"] == cid
    uploaded = await ok(postgres_client, "POST", f"/customers/{cid}/documents", 201,
        data={"category": "general"}, files={"file": ("documento.pdf", pdf_bytes(), "application/pdf")})
    assert uploaded["customer_id"] == cid
    loaded = await ok(postgres_client, "GET", f"/customers/{cid}")
    assert loaded["contacts"][0]["name"] == "Compras atualizado"
    await ok(postgres_client, "DELETE", f"/customers/{cid}/contacts/{contact['id']}", 204)
    loaded = await ok(postgres_client, "GET", f"/customers/{cid}")
    assert loaded["contacts"] == []


async def test_long_valid_equipment_fields_do_not_abort_os_notifications(postgres_client):
    order = await work_order(postgres_client, equipment_type="E" * 120, manufacturer="F" * 120, model="M" * 160)
    edited = await ok(postgres_client, "PATCH", f"/laboratory/work-orders/{order['id']}", json={
        "version": order["version"], "internal_notes": "Persistido", "quoted_value": "1.250,50",
    })
    assert Decimal(edited["quoted_value"]) == Decimal("1250.50")
    loaded = await ok(postgres_client, "GET", f"/laboratory/work-orders/{order['id']}")
    assert loaded["internal_notes"] == "Persistido"
    assert loaded["equipment_id"] == order["equipment_id"]
    assert loaded["manufacturer"] == "F" * 120
    async with session_factory() as db:
        notification = await db.scalar(select(Notification).where(Notification.work_order_id == order["id"]).order_by(Notification.id.desc()))
        assert len(notification.equipment_name) <= 250
        assert "M" * 160 in notification.details
    label = await postgres_client.get(f"/laboratory/work-orders/{order['id']}/label.pdf")
    assert label.status_code == 200 and label.content.startswith(b"%PDF-")


def finance_payload(**changes):
    return {
        "entry_type": "expense", "company_code": COMPANY, "counterparty_name": "Fornecedor teste",
        "description": "Despesa de homologação", "amount": "123.45", "issue_date": "2026-11-25",
        "posting_date": "2026-11-25", "due_date": "2026-12-25", "bank_name": "Bradesco",
        "expense_kind": "supplier", **changes,
    }


async def test_finance_concurrent_idempotency_edit_settle_and_delete(postgres_client):
    key = uuid4().hex
    payload = finance_payload(description="D" * 180)
    responses = await asyncio.gather(*[
        postgres_client.post("/finance/entries", json=payload, headers={"Idempotency-Key": key}) for _ in range(4)
    ])
    assert [r.status_code for r in responses] == [201] * 4, [r.text for r in responses]
    assert len({r.json()["id"] for r in responses}) == 1
    entry = responses[0].json()
    eid = entry["id"]
    different = await postgres_client.post("/finance/entries", json={**payload, "amount": "1.00"}, headers={"Idempotency-Key": key})
    assert different.status_code == 409
    edited = await ok(postgres_client, "PUT", f"/finance/entries/{eid}", json={**payload, "description": "Editada e persistida", "status": "pending"})
    assert edited["description"] == "Editada e persistida"
    paid = await ok(postgres_client, "POST", f"/finance/entries/{eid}/settle", json={"settlement_date": "2026-11-25"})
    assert paid["status"] == "paid"
    restored = await ok(postgres_client, "POST", f"/finance/entries/{eid}/unsettle")
    assert restored["status"] == "pending"
    uploaded = await ok(postgres_client, "POST", f"/finance/entries/{eid}/attachment", files={"file": ("teste.pdf", pdf_bytes(), "application/pdf")})
    assert uploaded["attachment_name"] == "teste.pdf"
    attachment = await postgres_client.get(f"/finance/entries/{eid}/attachment")
    assert attachment.status_code == 200 and attachment.content.startswith(b"%PDF-")
    await ok(postgres_client, "DELETE", f"/finance/entries/{eid}", 204)
    assert (await postgres_client.get(f"/finance/entries/{eid}")).status_code == 404


async def test_finance_installments_sum_and_period_closure(postgres_client):
    data = finance_payload()
    data.pop("amount");data.pop("due_date")
    data.update(total_amount="100.00", installments=[
        {"installment_number": 1, "amount": "33.33", "due_date": "2027-01-10"},
        {"installment_number": 2, "amount": "33.33", "due_date": "2027-02-10"},
        {"installment_number": 3, "amount": "33.34", "due_date": "2027-03-10"},
    ])
    result = await ok(postgres_client, "POST", "/finance/obligations", 201, json=data, headers={"Idempotency-Key": uuid4().hex})
    assert len(result["installments"]) == 3
    assert sum(Decimal(i["amount"]) for i in result["installments"]) == Decimal("100.00")
    loaded = await ok(postgres_client, "GET", f"/finance/obligations/{result['id']}")
    assert loaded["installment_count"] == 3
    closure = {"company_code": "solucoes_eletronica", "year": 2025, "month": 2, "notes": "Teste de fechamento"}
    await ok(postgres_client, "POST", "/finance/closures/close", json=closure)
    blocked = await postgres_client.post("/finance/entries", json=finance_payload(company_code="solucoes_eletronica", posting_date="2025-02-10", issue_date="2025-02-10", due_date="2025-03-10"))
    assert blocked.status_code == 409
    await ok(postgres_client, "POST", "/finance/closures/reopen", json=closure)


async def test_employee_lifecycle_and_history_persist(postgres_client):
    employee = await ok(postgres_client, "POST", "/employees", 201, json={
        "company_code": COMPANY, "full_name": "Colaborador teste V48",
        "document": str(int(uuid4().hex[:12], 16)).zfill(14)[-11:], "department": "Laboratório",
        "position": "Técnico", "salary_base": "2500.00", "hiring_date": "2026-01-05",
    })
    eid = employee["id"]
    edited = await ok(postgres_client, "PUT", f"/employees/{eid}", json={"position": "Técnico sênior", "salary_base": "2800.00"})
    assert edited["position"] == "Técnico sênior"
    terminated = await ok(postgres_client, "POST", f"/employees/{eid}/terminate", json={"termination_date": "2026-11-25", "reason_end": "Encerramento teste"})
    assert terminated["is_active"] is False
    assert len(terminated["employment_history"]) == 1
    restored = await ok(postgres_client, "POST", f"/employees/{eid}/reactivate")
    assert restored["is_active"] is True and restored["termination_date"] is None
    loaded = await ok(postgres_client, "GET", f"/employees/{eid}")
    assert loaded["position"] == "Técnico sênior"


async def test_collaborator_access_role_permission_and_logout(postgres_client):
    username = f"lab_{uuid4().hex[:12]}"
    access = await ok(postgres_client, "POST", "/employees/access", 201, json={
        "first_name": "Tecnico", "last_name": "Teste", "phone": "81999990000",
        "role": "lab", "username": username, "password": "V48-temporary-password",
    })
    from app.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver") as lab:
        await ok(lab, "POST", "/auth/login", json={"identifier": username, "password": "V48-temporary-password"})
        assert (await lab.get("/laboratory/work-orders")).status_code == 200
        assert (await lab.get("/finance/entries")).status_code == 403
        assert (await lab.post("/employees/access", json={"first_name": "Outro", "last_name": "Teste", "phone": "81999990000", "role": "gestao", "username": "unauthorized", "password": "V48-temporary-password"})).status_code == 403
        await ok(lab, "POST", "/auth/logout", 204)
        assert (await lab.get("/auth/me")).status_code == 401
    changed = await ok(postgres_client, "PUT", f"/employees/access/{access['user_id']}", json={"phone": "81988880000", "is_active": False})
    assert changed["is_active"] is False


async def test_commercial_asset_create_edit_label_and_remove(postgres_client):
    payload = {"company_code": COMPANY, "equipment_type": "Inversor", "manufacturer": "WEG", "model": "CFW", "quantity": 1, "unit_cost": "200.00", "sale_price": "300.00", "stock_status": "available"}
    asset = await ok(postgres_client, "POST", "/commercial/equipment", 201, json=payload)
    aid = asset["id"]
    edited = await ok(postgres_client, "PUT", f"/commercial/equipment/{aid}", json={**payload, "notes": "Patrimônio revisado"})
    assert edited["notes"] == "Patrimônio revisado"
    label = await postgres_client.get(f"/commercial/equipment/{aid}/label.pdf")
    assert label.status_code == 200 and label.content.startswith(b"%PDF-")
    await ok(postgres_client, "DELETE", f"/commercial/equipment/{aid}", 204)


async def test_inventory_edit_movement_and_photo_roundtrip(postgres_client):
    order = await work_order(postgres_client)
    item = await ok(postgres_client, "POST", "/inventory/items", 201, json={"company_code": COMPANY, "name": "Capacitor teste", "mode": "bulk", "quantity": 5, "unit_cost": "12.50"})
    iid = item["id"]
    edited = await ok(postgres_client, "PUT", f"/inventory/items/{iid}", json={"name": "Capacitor revisado", "category": "outros", "unit_cost": "13.00", "notes": "Salvo"})
    assert edited["name"] == "Capacitor revisado" and edited["updated_at"]
    await ok(postgres_client, "POST", f"/inventory/items/{iid}/issue", json={"quantity": 2, "work_order_id": order["id"]})
    movements = await ok(postgres_client, "GET", f"/inventory/items/{iid}/movements")
    issued = next(m for m in movements if m["kind"] == "issue")
    await ok(postgres_client, "POST", f"/inventory/items/{iid}/return", json={"quantity": 1, "work_order_id": order["id"], "reversal_of_id": issued["id"]})
    results = await ok(postgres_client, "GET", "/inventory/items", params={"search": "Capacitor revisado"})
    items = results["items"] if isinstance(results, dict) else results
    persisted = next(i for i in items if i["id"] == iid)
    assert persisted["quantity"] == 4
    from PIL import Image
    output = BytesIO();Image.new("RGB", (40, 30), "blue").save(output, format="PNG")
    photo = await ok(postgres_client, "POST", f"/inventory/items/{iid}/photos", 201, files={"file": ("foto.png", output.getvalue(), "image/png")})
    assert photo["id"]
    await ok(postgres_client, "DELETE", f"/inventory/items/{iid}/photos/{photo['id']}", 204)
    assert (await postgres_client.get(f"/inventory/photos/{photo['id']}")).status_code == 404


async def test_reports_and_notifications(postgres_client):
    await work_order(postgres_client)
    for path, signature in [("/finance/reports/pdf", b"%PDF-"), ("/finance/reports/xlsx", b"PK")]:
        result = await postgres_client.get(path)
        assert result.status_code == 200 and result.content.startswith(signature), result.text[:800] if result.status_code != 200 else path
    summary = await ok(postgres_client, "GET", "/notifications")
    assert summary["items"] and summary["unread_count"] > 0
    one = summary["items"][0]
    read = await ok(postgres_client, "POST", f"/notifications/{one['id']}/read")
    assert read["is_read"] is True
    await ok(postgres_client, "POST", "/notifications/read-all")
    assert (await ok(postgres_client, "GET", "/notifications"))["unread_count"] == 0
