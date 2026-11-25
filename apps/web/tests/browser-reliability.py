"""Browser regressions with deterministic local API fixtures (no production data).

Run after npm ci && npm run build. Requires Python Playwright and Chromium.
python tests/browser-reliability.py --chromium /usr/bin/chromium --artifacts /tmp/sentico-ui
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

WEB = Path(__file__).resolve().parents[1]
STAMP = "2026-11-25T12:00:00Z"
# Gestão has access by role even on legacy accounts with no explicit module list.
USER = {"id": 1, "name": "Validação Sêntico", "email": None, "username": "qa", "role": "gestao", "modules": [], "is_active": True}
COMPANY = {"id": 1, "company_code": "universo_eletronica", "legal_name": "Empresa de teste", "trade_name": "Teste", "document": None, "state_registration": None, "email": None, "phone": None, "address": None, "city": "Recife", "state": "PE", "is_active": True, "created_at": STAMP, "updated_at": STAMP}
CUSTOMER = {"id": 1, "company_code": "universo_eletronica", "legal_name": "Cliente de teste", "trade_name": "Cliente de teste", "document": None, "phone": None, "email": None, "address": None, "city": "Recife", "state": "PE", "is_active": True}


def work_order():
    fields = "equipment_serial equipment_type manufacturer model power voltage equipment_notes entry_invoice entry_invoice_2 entry_invoice_3 entry_invoice_access_key exit_invoice exit_invoice_2 exit_invoice_3 exit_invoice_access_key warranty_invoice warranty_invoice_2 warranty_invoice_3 warranty_entry_invoice_1 warranty_entry_invoice_2 warranty_entry_invoice_3 warranty_exit_invoice_1 warranty_exit_invoice_2 warranty_exit_invoice_3 warranty_entry_invoice_access_key_1 warranty_entry_invoice_access_key_2 warranty_entry_invoice_access_key_3 warranty_exit_invoice_access_key_1 warranty_exit_invoice_access_key_2 warranty_exit_invoice_access_key_3 storage_location entry_condition accessories_received assigned_technician_id completed_at delivered_at internal_notes customer_notes inactivation_reason inactivated_at"
    result = dict.fromkeys(fields.split(), None)
    result.update(id=100, number="OS-00100", company_code="universo_eletronica", customer_id=1, customer_name=CUSTOMER["legal_name"], equipment_id=1, equipment_type="Inversor", model="CFW700", status="received", priority="normal", reported_defect="Não liga", substatuses=[], version=1, parts_cost="0.00", quoted_value="100.00", approved_value="100.00", is_inactive=False, opened_at=STAMP, created_at=STAMP, updated_at=STAMP)
    return result


class FixtureApi:
    def __init__(self):
        self.order = work_order()
        self.purchases = []
        self.purchase_posts = []
        self.purchase_puts = []
        self.attachments = 0
        self.patches = []
        self.fail_history = False
        self.hold_order_list = False
        self.pending_order_lists = []
        self.quote = None
        self.quote_posts = 0
        self.quote_puts = 0
        self.fail_quote_confirmation = False
        self.hold_os_reads = False
        self.pending_os_reads = []
        self.hold_location = False
        self.pending_location = []
        self.unknown = []

    def handle(self, route):
        request = route.request
        path = urlparse(request.url).path.removeprefix("/api")
        method = request.method
        status, data = 200, []
        if path == "/auth/me": data = USER
        elif path in ("/notifications", "/notifications/history"):
            data = {"items": [], "unread_count": 0, "total": 0, "page": 1, "page_size": 25}
        elif path == "/dashboard/summary":
            data = {"schema_version": "3", "filtered_period": False, "audience": "gestao", "work_queues": [], "alerts": [], "purchase_events": [], "quick_actions": [], "monthly_equipment_entries": {"month_label": "Novembro", "count": 0}}
        elif path == "/purchasing/summary":
            data = dict.fromkeys(["total_open", "overdue", "due_soon", "delivered_month", "total_value_open"], 0)
        elif path == "/purchasing/suppliers":
            data = [{"id": 1, "name": "Fornecedor QA", "origin": "national", "is_active": True}]
        elif path == "/purchasing/stock-options": data = {"items": [], "formats": []}
        elif path == "/purchasing/orders" and method == "POST":
            self.purchase_posts.append(request.post_data_json)
            data = {**request.post_data_json, "id": 1, "code": "PC-00001", "supplier_name": "Fornecedor QA", "created_at": STAMP, "updated_at": STAMP, "delivered_at": None}
            self.purchases = [data]
        elif path == "/purchasing/orders": data = self.purchases
        elif path == "/purchasing/orders/1" and method == "PUT":
            self.purchase_puts.append(request.post_data_json)
            data = {**self.purchases[0], **request.post_data_json}
            self.purchases = [data]
        elif path == "/purchasing/orders/1/attachment":
            self.attachments += 1
            if self.attachments == 1: status, data = 500, {"detail": "Falha simulada no anexo"}
            else: data = self.purchases[0]
        elif path in ("/laboratory/settings/companies", "/commercial/companies"): data = [COMPANY]
        elif path in ("/laboratory/settings/locations", "/commercial/asset-locations"):
            data = {"areas": [], "racks": [], "locations": []}
        elif path == "/laboratory/periods": data = {"latest_month": 11, "latest_year": 2026, "years": [2026]}
        elif path == "/laboratory/summary":
            data = {**dict.fromkeys("total_open analyzed awaiting_approval approved awaiting_analysis in_repair in_testing high_priority completed_month".split(), 0), "approved_total": "100.00", "awaiting_approval_total": "0.00"}
        elif path in ("/laboratory/customers", "/customers"): data = [CUSTOMER]
        elif path == "/customers/page": data = {"items": [CUSTOMER], "page": 1, "page_size": 100, "total": 1, "pages": 1}
        elif path == "/laboratory/work-orders":
            if self.hold_order_list:
                self.pending_order_lists.append(route)
                return
            data = {"items": [self.order], "page": 1, "page_size": 25, "total": 1, "pages": 1}
        elif path == "/laboratory/work-orders/100" and method == "PATCH":
            payload = request.post_data_json
            self.patches.append(payload)
            if payload["version"] != self.order["version"]: status, data = 409, {"detail": "A O.S. foi alterada por outra operação."}
            else:
                self.order.update({k: v for k, v in payload.items() if k != "version"})
                self.order["version"] += 1
                data = self.order
        elif path == "/laboratory/locations/next":
            if self.hold_location:
                self.pending_location.append(route)
                return
            data = {"location": "A1"}
        elif path == "/laboratory/work-orders/100":
            if self.hold_os_reads:
                self.pending_os_reads.append(route)
                return
            data = self.order
        elif path.endswith("/history") or path.endswith("/location-history"):
            if self.fail_history and path.startswith("/laboratory/"): status, data = 503, {"detail": "Histórico temporariamente indisponível"}
        elif path == "/laboratory/quotes/write-contract": data = {"contract": "quote-save-v42"}
        elif path == "/laboratory/work-orders/100/quotes" and method == "POST":
            self.quote_posts += 1
            payload = request.post_data_json
            total = sum(item["quantity"] * item["unit_value"] for item in payload["items"])
            self.quote = {**payload, "id": 9, "work_order_id": 100, "revision": 1, "status": "draft", "emitted_at": None, "subtotal": f"{total:.2f}", "total": f"{total:.2f}", "created_at": STAMP, "updated_at": STAMP}
            data = self.quote
        elif path == "/laboratory/quotes/9" and method == "PUT":
            self.quote_puts += 1
            payload = request.post_data_json
            total = sum(item["quantity"] * item["unit_value"] for item in payload["items"])
            self.quote = {**self.quote, **payload, "subtotal": f"{total:.2f}", "total": f"{total:.2f}"}
            data = self.quote
        elif path == "/laboratory/work-orders/100/quotes":
            if self.fail_quote_confirmation and self.quote: status, data = 503, {"detail": "Consulta de conferência indisponível"}
            else: data = [self.quote] if self.quote else []
        elif path == "/inventory/map": data = {**{key: [] for key in "categories subtypes formats areas types containers slots".split()}, "companies": [{"code": "universo_eletronica", "name": "Empresa de teste"}], "unlocated": 0}
        elif path == "/commercial/asset-map": data = {**dict.fromkeys("total_positions occupied_positions free_positions located_assets assets_without_location".split(), 0), "slots": []}
        elif path == "/finance/summary":
            data = {**dict.fromkeys("current_balance period_income period_expense period_result settled_income settled_expense pending_income pending_expense overdue_income overdue_expense period_entry_count period_income_count period_expense_count projected_balance overdue_count due_soon_count".split(), 0), **{key: [] for key in "kpis urgent_events income_events expense_events cash_flow forecast_flow weekly_forecast_13w aging monthly_flow".split()}, "period_start": "2026-11-01", "period_end": "2026-11-25", "date_basis": "posting"}
        elif path == "/finance/date-bounds": data = {"min_date": None, "max_date": None, "count": 0, "date_basis": "posting"}
        elif path.endswith("/receivables"):
            data = {"work_order_id": 100, "work_order_number": "OS-00100", "company_code": "universo_eletronica", "customer_name": CUSTOMER["legal_name"], "approved_value": self.order["approved_value"], "total_registered": "0.00", "total_received": "0.00", "total_pending": "0.00", "remaining_to_issue": self.order["approved_value"], "installments": []}
        elif path in ("/notifications/actors", "/purchasing/material-requests", "/laboratory/technicians", "/laboratory/workflow-options", "/inventory/items", "/commercial/equipment", "/commercial/quotes", "/commercial/preventive-orders", "/employees/access", "/finance/closures", "/finance/alerts", "/laboratory/work-orders/100/materials"):
            data = []
        else:
            self.unknown.append((method, path))
        route.fulfill(status=status, content_type="application/json", body=json.dumps(data), headers={"X-Request-ID": "browser-regression-48"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium", default=None)
    parser.add_argument("--artifacts", default=tempfile.mkdtemp(prefix="sentico-ui-"))
    args = parser.parse_args()
    output = Path(args.artifacts)
    output.mkdir(parents=True, exist_ok=True)
    base = "http://127.0.0.1:4173"
    log = (output / "preview.log").open("w")
    server = subprocess.Popen(["npm", "run", "preview", "--", "--host", "127.0.0.1", "--port", "4173", "--strictPort"], cwd=WEB, stdout=log, stderr=subprocess.STDOUT)
    results = []
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base, timeout=.2).close()
                break
            except (OSError, TimeoutError): time.sleep(.1)
        else: raise RuntimeError("Preview did not start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
            context = browser.new_context(viewport={"width": 1440, "height": 1050})
            page = context.new_page()
            page.set_default_timeout(10000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            fixture = FixtureApi()
            page.route("**/api/**", fixture.handle)
            page.goto(base + "/compras?view=new")
            page.get_by_label("Título / descrição da compra*", exact=True).fill("Capacitor de teste")
            page.get_by_label("Valor total (R$)*", exact=True).fill("1234.56")
            page.locator("input[type=file]").set_input_files({"name": "teste.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 fixture"})
            page.get_by_role("button", name="Salvar compra no sistema", exact=True).click()
            expect(page.get_by_text(re.compile("Somente o anexo não foi enviado"))).to_be_visible()
            assert len(fixture.purchase_posts) == 1
            assert fixture.purchase_posts[0]["total_amount"] == 1234.56
            page.screenshot(path=str(output / "purchase-attachment-preserved.png"), full_page=True)
            page.get_by_role("button", name="Salvar alterações", exact=True).click()
            expect(page.get_by_text("Compra atualizada.", exact=True)).to_be_visible()
            assert len(fixture.purchase_posts) == 1 and len(fixture.purchase_puts) == 1 and fixture.attachments == 2
            results.append("purchase attachment failure retries same purchase: one POST, one PUT, two attachments")

            page.goto(base + "/laboratorio?os=100")
            page.get_by_role("button", name="Dados técnicos", exact=True).click()
            page.get_by_label("Modelo", exact=True).fill("ATV630")
            fixture.fail_history = True
            fixture.hold_order_list = True
            with page.expect_request(lambda request: urlparse(request.url).path == "/api/laboratory/work-orders" and request.method == "GET"):
                page.get_by_role("button", name="Salvar alterações", exact=True).click()
            expect(page.locator(".lab-detail").get_by_text(re.compile("O.S. salva. O histórico"))).to_be_visible()
            expect(page.get_by_label("Modelo", exact=True)).to_be_enabled()
            assert fixture.pending_order_lists
            fixture.hold_order_list = False
            for held in fixture.pending_order_lists:
                held.fulfill(content_type="application/json", body=json.dumps({"items": [fixture.order], "page": 1, "page_size": 25, "total": 1, "pages": 1}))
            fixture.pending_order_lists.clear()
            results.append("background list refresh does not lock OS editing after a confirmed save")
            assert fixture.patches[-1] == {"model": "ATV630", "version": 1}
            assert fixture.order["model"] == "ATV630"
            expect(page.get_by_label("Modelo", exact=True)).to_have_value("ATV630")
            page.screenshot(path=str(output / "os-saved-history-unavailable.png"), full_page=True)
            results.append("OS partial edit saved even when post-save history lookup fails")
            fixture.fail_history = False
            fixture.order["approved_value"] = "200.00"
            fixture.order["version"] += 1
            page.get_by_label("Observações internas", exact=True).fill("Revisão técnica concluída")
            with page.expect_response(lambda response: response.request.method == "PATCH" and response.status == 200):
                page.locator(".lab-detail-footer").get_by_role("button").last.click()
            expect(page.locator(".lab-alert.success")).to_contain_text("atualizada")
            assert fixture.order["version"] == 4
            assert fixture.order["approved_value"] == "200.00"
            assert fixture.order["internal_notes"] == "Revisão técnica concluída"
            assert fixture.patches[-2]["version"] == 2 and fixture.patches[-1]["version"] == 3
            results.append("OS disjoint version conflict rebases only changed field and preserves financial value")

            fixture.order["model"] = "MODELO COLEGA"
            fixture.order["version"] += 1
            page.get_by_label("Modelo", exact=True).fill("MEU MODELO")
            before = len(fixture.patches)
            page.locator(".lab-detail-footer").get_by_role("button").last.click()
            expect(page.locator(".lab-detail").get_by_text(re.compile("nos mesmos campos"))).to_be_visible()
            assert len(fixture.patches) == before + 1
            assert fixture.order["model"] == "MODELO COLEGA"
            expect(page.get_by_label("Modelo", exact=True)).to_have_value("MEU MODELO")
            page.screenshot(path=str(output / "os-concurrent-conflict-preserved.png"), full_page=True)
            results.append("OS same-field conflict retains local draft and blocks overwrite")

            page.goto(base + "/laboratorio?os=100")
            fixture.hold_location = True
            page.get_by_role("button", name="Sugerir melhor posição", exact=True).click()
            page.get_by_label("Defeito informado").fill("Defeito digitado durante a consulta da posição")
            assert fixture.pending_location
            fixture.pending_location.pop().fulfill(content_type="application/json", body=json.dumps({"location": "A1"}))
            expect(page.get_by_label("Defeito informado")).to_have_value("Defeito digitado durante a consulta da posição")
            with page.expect_response(lambda response: response.request.method == "PATCH" and response.status == 200):
                page.locator(".lab-detail-footer").get_by_role("button").last.click()
            assert fixture.order["reported_defect"] == "Defeito digitado durante a consulta da posição"
            assert fixture.order["storage_location"] == "A1"
            results.append("delayed location suggestion preserves text typed while the query is pending")

            page.get_by_role("button", name="Orçamento", exact=True).click()
            page.get_by_label("Diagnóstico técnico / laudo").fill("Laudo que deve salvar ao trocar de aba")
            fixture.hold_os_reads = True
            page.get_by_role("button", name="Dados técnicos", exact=True).click()
            expect(page.get_by_label("Modelo", exact=True)).to_be_visible()
            assert fixture.quote_posts == 1 and fixture.quote["technical_report"] == "Laudo que deve salvar ao trocar de aba"
            results.append("unsaved quote is persisted before leaving its tab")
            page.get_by_label("Modelo", exact=True).fill("LOCAL AFTER QUOTE")
            fixture.order["model"] = "REMOTE AFTER QUOTE"
            fixture.order["version"] += 1
            assert fixture.pending_os_reads
            fixture.hold_os_reads = False
            for held in fixture.pending_os_reads:
                held.fulfill(content_type="application/json", body=json.dumps(fixture.order))
            fixture.pending_os_reads.clear()
            expect(page.locator(".lab-detail").get_by_text(re.compile("nos mesmos campos"))).to_be_visible()
            expect(page.get_by_label("Modelo", exact=True)).to_have_value("LOCAL AFTER QUOTE")
            before = len(fixture.patches)
            page.locator(".lab-detail-footer").get_by_role("button").last.click()
            expect(page.locator(".lab-detail").get_by_text(re.compile("nos mesmos campos"))).to_be_visible()
            page.wait_for_load_state("networkidle")
            assert len(fixture.patches) == before + 1 and fixture.order["model"] == "REMOTE AFTER QUOTE"
            results.append("delayed quote refresh cannot advance baseline over a conflicting local edit")

            fixture.quote = None
            fixture.quote_posts = 0
            page.goto(base + "/laboratorio?os=100&aba=quote")
            page.get_by_label("Diagnóstico técnico / laudo").fill("Rascunho confirmado apesar de falha de consulta")
            fixture.fail_quote_confirmation = True
            page.get_by_role("button", name="Salvar rascunho", exact=True).click()
            expect(page.locator(".lab-quote-error")).to_contain_text("Consulta de conferência indisponível")
            assert fixture.quote_posts == 1
            fixture.fail_quote_confirmation = False
            page.get_by_role("button", name="Salvar rascunho", exact=True).click()
            expect(page.locator(".lab-quote-save-confirmation")).to_contain_text("salva e conferida")
            assert fixture.quote_posts == 1 and fixture.quote_puts == 1
            results.append("quote confirmation failure retries PUT on the saved draft instead of duplicating a revision")

            for route in ["/painel", "/compras", "/laboratorio", "/estoque", "/comercial", "/financeiro", "/clientes", "/colaboradores", "/notificacoes"]:
                page.goto(base + route)
                expect(page.locator("h1").first).to_be_visible()
                page.wait_for_load_state("networkidle")
                assert not page.get_by_text("Algo deu errado", exact=False).count(), route
                assert not errors, errors
                results.append(f"module navigation renders: {route}")
            browser.close()
            assert not fixture.unknown, fixture.unknown
        result = {"passed": len(results), "checks": results, "page_errors": errors, "fixture": "mocked API only; database verified separately"}
        (output / "browser-results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        server.terminate()
        server.wait(timeout=10)
        log.close()


if __name__ == "__main__": main()
