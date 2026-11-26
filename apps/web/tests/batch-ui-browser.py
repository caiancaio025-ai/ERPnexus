"""Focused Chromium regressions for joint billing and grouped quotes.

Runs the built UI with synthetic API responses. No real customer or server data.
Usage: python tests/batch-ui-browser.py --chromium /path/to/chromium --artifacts /tmp/report
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.request
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

WEB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fixtures', WEB / 'tests/browser-reliability.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class Api(fixtures.FixtureApi):
    def __init__(self):
        super().__init__()
        self.orders = [copy.deepcopy(self.order) for _ in range(3)]
        for index, row in enumerate(self.orders):
            row.update(id=100 + index, number=f'OS-00{100 + index}', opened_at='2026-11-26', equipment_serial=f'SERIE-{index + 1}')
        self.orders[2].update(customer_id=2, customer_name='Outro cliente')
        self.groups = []
        self.group_keys = []
        self.group_updates = []
        self.batch_keys = []
        self.batch_payloads = []
        self.conflict_next_update = False

    def option(self, row):
        return {**{key: row[key] for key in ('id', 'number', 'company_code', 'customer_id', 'customer_name', 'version', 'status', 'approved_value', 'exit_invoice', 'exit_invoice_2', 'exit_invoice_3')}, 'equipment_label': row['model'], 'total_registered': 0, 'remaining_to_issue': row['approved_value']}

    def group(self):
        return dict(id=1, group_id=1, code='OC-000001', revision=1, version=1, status='draft', title='Orçamento conjunto', company_code='universo_eletronica', customer_id=1, customer_name='Cliente de teste', work_order_ids=[100, 101],
            work_orders=[{**row, 'subtotal': '100.00', 'discount_amount': '0.00', 'total': '100.00'} for row in self.orders[:2]],
            service_code='3312102 / 14.01', technical_report='', services_description='', delivery_days=20, billing_days=21, billing_terms='21 dias', warranty_months=3, warranty_terms='3 meses', payment_terms='PIX', validity_days=30,
            return_condition='Devolução em 30 dias', consumer_clause='Cláusula de teste', supply_clause='Fornecimento', estimate_clause='Estimativa', discount_type='none', discount_value='0', discount_amount='0', subtotal='200.00', total='200.00', emitted_at=None,
            created_at=fixtures.STAMP, updated_at=fixtures.STAMP, items=[{'work_order_id': row['id'], 'description': 'Reparo', 'quantity': '1', 'unit_value': '100.00'} for row in self.orders[:2]])

    def handle(self, route):
        req = route.request
        parsed = urlparse(req.url)
        path, method = parsed.path.removeprefix('/api'), req.method
        query = parse_qs(parsed.query)
        data = None
        if path == '/laboratory/work-orders':
            data = {'items': self.orders, 'page': 1, 'page_size': 25, 'total': 3, 'pages': 1}
        elif re.fullmatch(r'/laboratory/work-orders/\d+', path):
            row = next(row for row in self.orders if row['id'] == int(path.rsplit('/', 1)[1]))
            if method == 'PATCH':
                self.patches.append(req.post_data_json)
                row.update(req.post_data_json)
                row['version'] += 1
            data = row
        elif path == '/finance/work-orders':
            ids = query.get('ids', [None])[0]
            data = [self.option(row) for row in self.orders if ids is None or str(row['id']) in ids.split(',')]
        elif path.endswith('/billing-readiness'):
            row = next(row for row in self.orders if row['id'] == int(path.split('/')[-2]))
            data = {'work_order_id': row['id'], 'work_order_number': row['number'], 'customer_id': row['customer_id'], 'customer_name': row['customer_name'], 'approved_value': row['approved_value'], 'items': []}
        elif path == '/finance/entries':
            data = {'items': [], 'page': 1, 'page_size': 50, 'total': 0, 'pages': 1}
        elif path == '/finance/billing-batches' and method == 'POST':
            self.batch_keys.append(req.headers.get('idempotency-key'))
            self.batch_payloads.append(req.post_data_json)
            if len(self.batch_keys) == 1:
                route.abort('failed')  # Commit may have happened; retry must reuse the key and body.
                return
            data = {'batch_id': 'batch-test', 'total_amount': '200.00', 'exit_invoice': 'NF-TESTE', 'work_orders': [{'work_order_id': row['id'], 'work_order_number': row['number'], 'amount': '100.00', 'obligation': {'id': row['id'], 'installments': []}} for row in self.orders[:2]]}
        elif path == '/laboratory/grouped-quotes' and method == 'POST':
            self.group_keys.append(req.headers.get('idempotency-key'))
            if not self.groups:
                self.groups = [self.group()]
                route.abort('failed')
                return
            data = self.groups[0]
        elif path == '/laboratory/grouped-quotes':
            data = self.groups
        elif re.fullmatch(r'/laboratory/grouped-quotes/\d+', path):
            data = next(row for row in self.groups if row['id'] == int(path.rsplit('/', 1)[1]))
            if method == 'PUT':
                self.group_updates.append(req.post_data_json)
                if self.conflict_next_update:
                    self.conflict_next_update = False
                    data.update(title='Título de outro operador', version=data['version'] + 1)
                    route.fulfill(status=409, content_type='application/json', body=json.dumps({'detail': 'Revisão alterada por outra operação.'}))
                    return
                data.update(req.post_data_json)
                data['version'] += 1
                data['subtotal'] = data['total'] = str(sum(float(row['quantity']) * float(row['unit_value']) for row in data['items']))
                if len(self.group_updates) == 1:
                    route.abort('failed')
                    return
            if method == 'DELETE':
                self.groups.remove(data)
                route.fulfill(status=204)
                return
        elif re.fullmatch(r'/laboratory/grouped-quotes/\d+/revisions', path):
            source = next(row for row in self.groups if row['id'] == int(path.split('/')[-2]))
            data = {**copy.deepcopy(source), 'id': len(self.groups) + 1, 'revision': len(self.groups) + 1, 'version': 1, 'status': 'draft', 'emitted_at': None}
            self.groups.append(data)
        elif re.fullmatch(r'/laboratory/grouped-quotes/\d+/(emit|pdf)', path):
            group = next(row for row in self.groups if row['id'] == int(path.split('/')[-2]))
            if path.endswith('/emit'):
                group.update(status='emitted', emitted_at=fixtures.STAMP, version=group['version'] + 1)
            route.fulfill(status=200, content_type='application/pdf', body=b'%PDF-1.4\n' + b'%synthetic pdf fixture\n' * 20)
            return
        if data is None:
            return super().handle(route)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(data))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chromium', required=True)
    parser.add_argument('--artifacts', required=True)
    parser.add_argument('--dev', action='store_true')
    args = parser.parse_args()
    out = Path(args.artifacts)
    out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = (out / 'preview.log').open('w')
    process = subprocess.Popen(['npm', 'run', 'dev' if args.dev else 'preview', '--', '--host', '127.0.0.1', '--port', str(port), '--strictPort'], cwd=WEB, stdout=log, stderr=log)
    base = f'http://127.0.0.1:{port}'
    checks, errors = [], []
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base, timeout=.2).close()
                break
            except OSError:
                time.sleep(.1)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            api = Api()
            # Dev-mode source paths also contain /shared/api/; only mock HTTP API routes.
            page.route('**/api/**', lambda route: api.handle(route) if urlparse(route.request.url).path.startswith('/api/') else route.continue_())
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base + '/laboratorio')
            try:
                page.get_by_role('checkbox', name='Selecionar OS-00100', exact=True).check(timeout=10000)
            except Exception:
                (out / 'failure.html').write_text(page.content())
                page.screenshot(path=str(out / 'failure.png'))
                print(json.dumps({'page_errors': errors, 'unhandled_routes': api.unknown}, ensure_ascii=False), flush=True)
                raise
            expect(page.locator('.lab-detail')).to_have_count(0)
            expect(page.get_by_role('checkbox', name='Selecionar OS-00102', exact=True)).to_be_disabled()
            page.get_by_role('checkbox', name='Selecionar OS-00101', exact=True).check()
            checks.append('row checkboxes preserve list; a different customer cannot join the selection')
            page.get_by_role('button', name='Criar orçamento conjunto', exact=True).click()
            dialog = page.locator('.grouped-quote-dialog')
            page.wait_for_function("() => document.querySelector('.grouped-quote-dialog')?.textContent.includes('Recarregar orçamento') || document.querySelector('.grouped-quote-dialog h2')?.textContent.includes('OC-000001')")
            if dialog.get_by_role('button', name='Recarregar orçamento').count():
                dialog.get_by_role('button', name='Recarregar orçamento').click()
            expect(dialog.get_by_role('heading', name='OC-000001 · Cliente de teste')).to_be_visible()
            assert len(api.group_keys) >= 2 and len(set(api.group_keys)) == 1 and api.group_keys[0]
            checks.append('ambiguous grouped-quote creation reuses its idempotency key')
            dialog.get_by_label('Descrição — OS-00100', exact=True).fill('Reparo do inversor A')
            dialog.get_by_label('Valor unitário (R$)', exact=True).nth(0).fill('125,50')
            dialog.get_by_role('textbox', name='Diagnóstico técnico / laudo', exact=True).fill('Diagnóstico comum preservado')
            dialog.get_by_role('button', name='Salvar rascunho', exact=True).click()
            expect(dialog.locator('.grouped-quote-notice')).to_contain_text('salva')
            assert api.group_updates[-1]['items'][0]['unit_value'] == 125.5
            assert api.group_updates[-1]['items'][1]['work_order_id'] == 101
            page.screenshot(path=str(out / 'grouped-quote-desktop.png'))
            assert len(api.group_updates) == 1
            checks.append('lost PUT acknowledgement is reconciled by GET; OS items/common fields/Brazilian money stay saved without write replay')
            api.conflict_next_update = True
            dialog.get_by_label('Título do documento').fill('Meu título ainda não salvo')
            dialog.get_by_role('button', name='Salvar rascunho', exact=True).click()
            expect(dialog.locator('.grouped-quote-error')).to_contain_text('Revisão alterada')
            expect(dialog.get_by_label('Título do documento')).to_have_value('Meu título ainda não salvo')
            page.once('dialog', lambda prompt: prompt.accept())
            dialog.get_by_role('button', name='Recarregar orçamento').click()
            expect(dialog.get_by_label('Título do documento')).to_have_value('Título de outro operador')
            checks.append('different concurrent content preserves local draft until explicit reload')
            page.set_viewport_size({'width': 390, 'height': 844})
            rect = dialog.bounding_box()
            assert rect['x'] >= 0 and rect['x'] + rect['width'] <= 391
            assert dialog.evaluate('(element) => element.scrollWidth <= element.clientWidth')
            page.screenshot(path=str(out / 'grouped-quote-mobile.png'))
            page.set_viewport_size({'width': 1440, 'height': 1000})
            with page.expect_download():
                dialog.get_by_role('button', name='Salvar e emitir PDF', exact=True).click()
            expect(dialog.get_by_role('button', name='Baixar PDF emitido')).to_be_visible()
            expect(dialog.get_by_label('Título do documento')).to_be_disabled()
            dialog.get_by_role('button', name='Nova revisão', exact=True).click()
            expect(dialog.get_by_label('Título do documento')).to_be_enabled()
            expect(dialog.get_by_role('textbox', name='Diagnóstico técnico / laudo', exact=True)).to_have_value('Diagnóstico comum preservado')
            dialog.get_by_role('button', name='Fechar orçamento conjunto', exact=True).click()
            checks.append('mobile dialog fits; emitted revision locks; new revision retains content')
            page.get_by_role('button', name='Orçamentos conjuntos', exact=True).click()
            page.locator('.grouped-quotes-list > button').first.click()
            expect(dialog.get_by_role('textbox', name='Diagnóstico técnico / laudo', exact=True)).to_have_value('Diagnóstico comum preservado')
            dialog.get_by_role('button', name='Fechar orçamento conjunto', exact=True).click()
            checks.append('group history reopens the latest editable revision')
            page.goto(base + '/financeiro?faturar_os=100,101')
            modal = page.locator('.finance-modal')
            expect(modal.get_by_label('Valor a faturar — OS-00100', exact=True)).to_have_value('100,00')
            modal.get_by_label('NFS-e', exact=True).fill('NF-TESTE')
            expect(modal.get_by_label('NF de saída nas OS', exact=True)).to_have_value('NF-TESTE')
            modal.get_by_role('button', name='Faturar 2 OS', exact=True).click()
            expect(modal.get_by_role('button', name='Faturar 2 OS', exact=True)).to_be_enabled()
            modal.get_by_role('button', name='Faturar 2 OS', exact=True).click()
            expect(page.locator('.billing-batch-success')).to_be_visible()
            assert len(api.batch_keys) == 2 and api.batch_keys[0] == api.batch_keys[1] and api.batch_keys[0]
            assert api.batch_payloads[0] == api.batch_payloads[1]
            assert [row['work_order_id'] for row in api.batch_payloads[-1]['work_orders']] == [100, 101]
            assert api.batch_payloads[-1]['exit_invoice'] == 'NF-TESTE'
            checks.append('billing deep-link loads exact IDs, syncs invoice field and preserves retry key/body')
            page.goto(base + '/laboratorio?os=100&aba=financial')
            detail = page.locator('.lab-detail')
            expect(detail.get_by_label('NF de saída 3', exact=True)).to_be_visible()
            detail.get_by_label('NF de saída 2', exact=True).fill('NF-SEGUNDA')
            detail.get_by_role('button', name='Salvar alterações', exact=True).click()
            expect(detail.get_by_role('button', name='Salvo', exact=True)).to_be_visible()
            assert api.patches[-1] == {'version': 1, 'exit_invoice_2': 'NF-SEGUNDA'}
            checks.append('three exit invoice fields are visible; existing OS PATCH sends only changed field/version')
            assert not errors, errors
            result = {'backend': 'synthetic API', 'react_mode': 'development StrictMode' if args.dev else 'production', 'passed': len(checks), 'checks': checks, 'page_errors': errors}
            (out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    main()
