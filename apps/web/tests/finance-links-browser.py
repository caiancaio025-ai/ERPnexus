"""Financial modal regressions with deterministic API fixtures, no production data.

python tests/finance-links-browser.py --chromium /path/to/chromium --dev --artifacts /tmp/finance-links
"""
from __future__ import annotations
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
        self.orders = []
        for index in range(3):
            row = copy.deepcopy(self.order)
            row.update(id=100 + index, number=f'OS-00{100 + index}', version=2, approved_value='1000.00', model=f'CFW-{index + 1}', exit_invoice='1750' if index == 0 else None)
            if index == 2:
                row.update(customer_id=2, customer_name='Outro cliente')
            self.orders.append(row)
        self.entries = {501: self.entry(501, 300), 601: self.entry(601, 100, 901, 1), 602: self.entry(602, 100, 901, 2)}
        self.groups = {901: {'id': 901, 'version': 5, 'ids': [601, 602], 'links': [{'work_order_id': 100, 'amount': 200}], 'locked': False}}
        self.entries[501]['work_orders'] = [self.link({'work_order_id': 100, 'amount': 300})]
        self.events = []
        self.create_keys = []
        self.idempotency = {}
        self.drop_create = False
        self.drop_update = False
        self.conflict_update = False
        self.fail_metadata = True
        self.next_id = 700

    def entry(self, ident, amount, obligation=None, number=None):
        return dict(id=ident, version=1, obligation_id=obligation, installment_number=number,
            entry_type='income', company_code='universo_eletronica', invoice_type=None, series='1',
            nfse_number='340', nfe_number='1750', counterparty_name='Cliente de teste', description='Faturamento existente',
            amount=amount, issue_date='2026-11-26', posting_date='2026-11-26', due_date='2026-12-26',
            bank_name='Bradesco', expense_kind=None, document_number=None, payment_code=None, notes=None,
            status='pending', settlement_date=None, work_order_id=100, work_orders=[],
            work_order_links_editable=True, work_order_links_lock_reason=None,
            created_at=fixtures.STAMP, updated_at=fixtures.STAMP)

    def link(self, payload):
        order = next(row for row in self.orders if row['id'] == payload['work_order_id'])
        return dict(work_order_id=order['id'], work_order_number=order['number'], company_code=order['company_code'],
            customer_id=order['customer_id'], customer_name=order['customer_name'], equipment_label=order['model'],
            amount=f"{float(payload['amount']):.2f}", version=order['version'], approved_value=order['approved_value'],
            exit_invoice=order['exit_invoice'], exit_invoice_2=order['exit_invoice_2'], exit_invoice_3=order['exit_invoice_3'],
            billing_confirmation=copy.deepcopy(payload.get('billing_confirmation')))

    def output(self, ident):
        entry = copy.deepcopy(self.entries[ident])
        if entry['obligation_id']:
            group = self.groups[entry['obligation_id']]
            total = sum(float(self.entries[value]['amount']) for value in group['ids'])
            links = [self.link(link) for link in group['links']]
            share_left = round(float(entry['amount']) * 100)
            shares = []
            for index, link in enumerate(links):
                cents = share_left if index == len(links) - 1 else round(float(link['amount']) / total * float(entry['amount']) * 100)
                shares.append({**link, 'amount': f'{cents / 100:.2f}'})
                share_left -= cents
            entry.update(work_orders=shares, obligation_work_orders=links, obligation_total_amount=f'{total:.2f}', obligation_version=group['version'])
            if group['locked']:
                entry.update(work_order_links_editable=False, work_order_links_lock_reason='Outra parcela deste faturamento já foi baixada. Preserve os vínculos até a baixa ser estornada.')
        entry['work_order_id'] = entry['work_orders'][0]['work_order_id'] if len(entry['work_orders']) == 1 else None
        return entry

    def option(self, row):
        return {**{key: row[key] for key in ('id', 'number', 'company_code', 'customer_id', 'customer_name', 'version', 'status', 'approved_value', 'exit_invoice', 'exit_invoice_2', 'exit_invoice_3')}, 'equipment_label': row['model'], 'total_registered': 300, 'remaining_to_issue': 700}

    def apply_links(self, payload):
        for link in payload.get('work_orders', []):
            order = next(row for row in self.orders if row['id'] == link['work_order_id'])
            invoice = payload.get('exit_invoice')
            if invoice and invoice not in [order['exit_invoice'], order['exit_invoice_2'], order['exit_invoice_3']]:
                for key in ('exit_invoice', 'exit_invoice_2', 'exit_invoice_3'):
                    if not order[key]:
                        order[key] = invoice
                        order['version'] += 1
                        break

    def handle(self, route):
        req = route.request
        parsed = urlparse(req.url)
        path, method = parsed.path.removeprefix('/api'), req.method
        query = parse_qs(parsed.query)
        status, data = 200, None
        if path == '/finance/work-orders':
            if self.fail_metadata and 'ids' in query:
                status, data = 503, {'detail': 'Consulta secundária indisponível'}
            else:
                ids = query.get('ids', [None])[0]
                data = [self.option(row) for row in self.orders if ids is None or str(row['id']) in ids.split(',')]
        elif path.endswith('/billing-readiness'):
            row = next(row for row in self.orders if row['id'] == int(path.split('/')[-2]))
            data = {'work_order_id': row['id'], 'work_order_number': row['number'], 'customer_id': row['customer_id'], 'customer_name': row['customer_name'], 'approved_value': row['approved_value'], 'items': []}
        elif path == '/finance/entries' and method == 'GET':
            data = {'items': [self.output(ident) for ident in self.entries], 'page': 1, 'page_size': 50, 'total': len(self.entries), 'pages': 1}
        elif path in ('/finance/entries', '/finance/obligations') and method == 'POST':
            body = req.post_data_json
            self.events.append((method, path, body))
            key = req.headers.get('idempotency-key')
            self.create_keys.append(key)
            if key in self.idempotency:
                data = self.idempotency[key]
            else:
                self.apply_links(body)
                if path.endswith('/entries'):
                    self.next_id += 1
                    ident = self.next_id
                    entry = self.entry(ident, body['amount'])
                    entry.update({k: v for k, v in body.items() if k not in ('work_orders', 'exit_invoice')})
                    entry['work_orders'] = [self.link(link) for link in body.get('work_orders', [])]
                    self.entries[ident] = entry
                    data = self.output(ident)
                else:
                    group_id = 902
                    ids = []
                    for row in body['installments']:
                        self.next_id += 1
                        ident = self.next_id
                        entry = self.entry(ident, row['amount'], group_id, row['installment_number'])
                        entry.update({k: v for k, v in body.items() if k not in ('work_orders', 'exit_invoice', 'total_amount', 'installments')})
                        entry.update(row)
                        self.entries[ident] = entry
                        ids.append(ident)
                    self.groups[group_id] = {'id': group_id, 'version': 1, 'ids': ids, 'links': body['work_orders'], 'locked': False}
                    data = {'id': group_id, 'version': 1, 'installments': [self.output(ident) for ident in ids]}
                self.idempotency[key] = data
                if self.drop_create:
                    self.drop_create = False
                    route.abort('failed')
                    return
        elif re.fullmatch(r'/finance/entries/\d+', path):
            ident = int(path.rsplit('/', 1)[1])
            if method == 'PUT':
                body = req.post_data_json
                self.events.append((method, path, body))
                entry = self.entries[ident]
                group = self.groups.get(entry['obligation_id'])
                if self.conflict_update:
                    self.conflict_update = False
                    entry.update(description='Alteração de outro operador', notes='Observação do outro operador', version=entry['version'] + 1)
                if body.get('version') != entry['version'] or (group and body.get('obligation_version') != group['version']):
                    status, data = 409, {'detail': 'Lançamento alterado por outra operação. Recarregue a versão salva.'}
                else:
                    self.apply_links(body)
                    entry.update({k: v for k, v in body.items() if k not in ('work_orders', 'exit_invoice', 'version', 'obligation_version', 'obligation_total_amount')})
                    entry['version'] += 1
                    if 'work_orders' in body:
                        if group:
                            assert round(sum(float(link['amount']) for link in body['work_orders']), 2) == round(float(body['obligation_total_amount']), 2) or not body['work_orders']
                            group['links'] = copy.deepcopy(body['work_orders'])
                        else:
                            entry['work_orders'] = [self.link(link) for link in body['work_orders']]
                    if group:
                        group['version'] += 1
                    data = self.output(ident)
                    if self.drop_update:
                        self.drop_update = False
                        route.abort('failed')
                        return
            else:
                data = self.output(ident)
        elif re.fullmatch(r'/finance/obligations/\d+', path):
            group = self.groups[int(path.rsplit('/', 1)[1])]
            data = {'id': group['id'], 'version': group['version'], 'installments': [self.output(ident) for ident in group['ids']]}
        elif path.endswith('/receivables'):
            ident = int(path.split('/')[-2])
            rows = []
            for entry_id in self.entries:
                entry = self.output(entry_id)
                link = next((link for link in entry['work_orders'] if link['work_order_id'] == ident), None)
                if link:
                    rows.append({**entry, 'work_order_amount': link['amount']})
            total = sum(float(row['work_order_amount']) for row in rows)
            order = next(row for row in self.orders if row['id'] == ident)
            data = dict(work_order_id=ident, work_order_number=order['number'], company_code=order['company_code'], customer_name=order['customer_name'], approved_value=1000, total_registered=total, total_received=0, total_pending=total, remaining_to_issue=1000-total, installments=rows)
        if data is None:
            return super().handle(route)
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))


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
            page.set_default_timeout(10000)
            api = Api()
            page.route('**/api/**', lambda route: api.handle(route) if urlparse(route.request.url).path.startswith('/api/') else route.continue_())
            page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                def open_entry(ident):
                    page.goto(base + f'/financeiro?lancamento={ident}')
                    expect(page.locator('.finance-modal')).to_be_visible()
                    return page.locator('.finance-modal')

                def add_order(modal, number):
                    modal.get_by_label('Buscar Ordem de Serviço', exact=True).fill('OS')
                    if modal.locator('.billing-order-card').count():
                        expect(modal.locator('.billing-orders-results').get_by_role('button', name=re.compile('OS-00102'))).to_be_disabled()
                    modal.locator('.billing-orders-results').get_by_role('button', name=re.compile(number)).click()

                modal = open_entry(501)
                expect(modal.get_by_role('button', name='Dar baixa', exact=True)).to_be_visible()
                expect(modal.get_by_role('button', name='Excluir', exact=True)).to_be_visible()
                expect(modal.get_by_label('Valor', exact=True)).to_have_value('300,00')
                expect(modal.locator('.billing-metadata-warning')).to_be_visible()
                expect(modal.locator('.billing-order-card')).to_have_count(1)
                expect(modal.locator('.billing-order-values')).to_contain_text('1.000,00')
                checks.append('existing links survive secondary metadata failure and remain editable')
                add_order(modal, 'OS-00101')
                expect(modal.get_by_label('Valor', exact=True)).to_have_value('300,00')
                modal.get_by_label('Valor atribuído — OS-00101', exact=True).fill('100,00')
                modal.get_by_role('button', name='Salvar alterações', exact=True).click()
                expect(modal.locator('.finance-modal-error')).to_contain_text('soma dos valores')
                assert not api.events
                modal.get_by_label('Valor atribuído — OS-00100', exact=True).fill('200,00')
                for ident in (100, 101):
                    card = modal.locator('.billing-order-card').filter(has_text=f'OS-00{ident}')
                    expect(card.get_by_role('link', name='Ver orçamento da OS', exact=True)).to_have_attribute('href', f'/laboratorio?os={ident}&aba=quote')
                    expect(card.get_by_role('link', name='Ver valor aprovado', exact=True)).to_have_attribute('target', '_blank')
                expect(modal.get_by_label('NF de saída nas OS', exact=True)).to_have_value('1750')
                api.drop_update = True
                modal.get_by_role('button', name='Salvar alterações', exact=True).click()
                expect(modal).to_have_count(0)
                writes = [event for event in api.events if event[0] == 'PUT']
                assert len(writes) == 1 and len(api.entries) == 3
                assert writes[0][2]['amount'] == 300 and [row['amount'] for row in writes[0][2]['work_orders']] == [200, 100]
                checks.append('same existing invoice gains two OS without changing total or creating entries; lost PUT response reconciles by GET')

                api.fail_metadata = False
                modal = open_entry(501)
                api.conflict_update = True
                modal.get_by_role('textbox', name='Observações', exact=True).fill('Minha edição pendente')
                modal.get_by_role('button', name='Salvar alterações', exact=True).click()
                expect(modal.locator('.finance-modal-error')).to_contain_text('outra operação')
                expect(modal.get_by_role('textbox', name='Observações', exact=True)).to_have_value('Minha edição pendente')
                page.once('dialog', lambda prompt: prompt.accept())
                modal.get_by_role('button', name='Recarregar lançamento', exact=True).click()
                expect(modal.get_by_role('textbox', name='Observações', exact=True)).to_have_value('Observação do outro operador')
                checks.append('different concurrent contents preserve typed changes until explicit reload')
                page.set_viewport_size({'width': 390, 'height': 844})
                rect = modal.bounding_box()
                assert rect['x'] >= 0 and rect['x'] + rect['width'] <= 391
                assert modal.evaluate('(element) => element.scrollWidth <= element.clientWidth')
                page.screenshot(path=str(out / 'existing-receipt-mobile.png'))
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.screenshot(path=str(out / 'existing-receipt-desktop.png'))
                modal.get_by_role('button', name='Remover OS-00101 do faturamento', exact=True).click()
                expect(modal.get_by_label('Valor', exact=True)).to_have_value('300,00')
                expect(modal.get_by_label('Valor atribuído — OS-00100', exact=True)).to_have_value('300,00')
                modal.get_by_role('button', name='Remover OS-00100 do faturamento', exact=True).click()
                expect(modal.get_by_label('Valor', exact=True)).to_have_value('300,00')
                modal.get_by_role('button', name='Salvar alterações', exact=True).click()
                expect(modal).to_have_count(0)
                assert api.entries[501]['work_orders'] == [] and api.entries[501]['amount'] == 300
                checks.append('removing some or all links keeps the invoice amount; mobile dialog fits')

                page.get_by_role('button', name='Nova receita', exact=True).click()
                modal = page.locator('.finance-modal')
                modal.get_by_label('Valor', exact=True).fill('200,00')
                add_order(modal, 'OS-00100')
                add_order(modal, 'OS-00101')
                modal.get_by_role('button', name='Dividir total entre as OS', exact=True).click()
                modal.get_by_label('NFS-e', exact=True).fill('NF-NOVA')
                api.drop_create = True
                modal.get_by_role('button', name='Salvar lançamento', exact=True).click()
                expect(modal.locator('.finance-modal-error')).to_be_visible()
                modal.get_by_role('button', name='Salvar lançamento', exact=True).click()
                expect(modal).to_have_count(0)
                assert len(api.create_keys) == 2 and api.create_keys[0] == api.create_keys[1] and api.create_keys[0]
                assert len(api.entries) == 4
                assert not any('/billing-batches' in event[1] for event in api.events)
                checks.append('new multi-OS invoice uses normal POST and one stable idempotency key after lost acknowledgement')

                page.get_by_role('button', name='Nova receita', exact=True).click()
                modal = page.locator('.finance-modal')
                modal.get_by_role('button', name='Parcelado', exact=True).click()
                modal.get_by_label('Valor total', exact=True).fill('100,01')
                add_order(modal, 'OS-00100')
                add_order(modal, 'OS-00101')
                modal.get_by_role('button', name='Dividir total entre as OS', exact=True).click()
                modal.get_by_label('NFS-e', exact=True).fill('NF-PARCELAS')
                modal.get_by_label('Quantidade', exact=True).fill('3')
                modal.get_by_role('button', name='Dividir valor igualmente', exact=True).click()
                modal.get_by_role('button', name='Sugerir vencimentos mensais', exact=True).click()
                modal.get_by_role('button', name='Salvar 3 parcelas', exact=True).click()
                expect(modal).to_have_count(0)
                posts = [event for event in api.events if event[1] == '/finance/obligations']
                assert len(posts) == 1 and len(api.groups[902]['ids']) == 3
                assert posts[0][2]['total_amount'] == 100.01 and len(posts[0][2]['work_orders']) == 2
                assert round(sum(row['amount'] for row in posts[0][2]['installments']), 2) == 100.01
                checks.append('new multi-OS installment plan creates one obligation with three installments, not three per OS')

                modal = open_entry(601)
                expect(modal.get_by_label('Valor da parcela', exact=True)).to_have_value('100,00')
                expect(modal.locator('.billing-orders-scope')).to_contain_text('200,00')
                add_order(modal, 'OS-00101')
                modal.get_by_role('button', name='Dividir total entre as OS', exact=True).click()
                expect(modal.get_by_label('Valor da parcela', exact=True)).to_have_value('100,00')
                modal.get_by_role('button', name='Salvar alterações', exact=True).click()
                expect(modal).to_have_count(0)
                update = api.events[-1][2]
                assert update['obligation_total_amount'] == 200 and update['amount'] == 100 and update['obligation_version'] == 5
                assert api.groups[901]['ids'] == [601, 602] and [api.entries[ident]['amount'] for ident in (601, 602)] == [100, 100]
                checks.append('editing an existing installment updates whole-invoice links while preserving every installment ID and amount')
                modal = open_entry(601)
                modal.get_by_label('Valor da parcela', exact=True).fill('120,00')
                expect(modal.locator('.billing-orders-scope')).to_contain_text('220,00')
                modal.get_by_role('button', name='Dividir total entre as OS', exact=True).click()
                modal.get_by_role('button', name='Salvar alterações', exact=True).click()
                expect(modal).to_have_count(0)
                assert api.events[-1][2]['obligation_total_amount'] == 220 and api.entries[602]['amount'] == 100
                checks.append('explicit installment amount correction computes the new invoice total and preserves sibling installments')
                api.groups[901]['locked'] = True
                modal = open_entry(601)
                expect(modal.locator('.billing-orders-lock')).to_contain_text('Outra parcela')
                expect(modal.get_by_label('Buscar Ordem de Serviço', exact=True)).to_have_count(0)
                expect(modal.get_by_label('Valor atribuído — OS-00100', exact=True)).to_be_disabled()
                expect(modal.get_by_label('Valor da parcela', exact=True)).to_be_disabled()
                expect(modal.get_by_label('NF de saída nas OS', exact=True)).to_be_disabled()
                modal.get_by_role('textbox', name='Observações', exact=True).fill('Correção documental permitida')
                modal.get_by_role('button', name='Salvar alterações', exact=True).click()
                expect(modal).to_have_count(0)
                assert 'work_orders' not in api.events[-1][2] and 'exit_invoice' not in api.events[-1][2]
                checks.append('sibling settlement lock explains restriction and omits protected links on documentary edits')

                page.goto(base + '/financeiro?os=100')
                expect(page.locator('.finance-linked-list')).to_contain_text('Total do título:')
                expect(page.locator('.finance-linked-list').get_by_role('button').first).to_be_visible()
                checks.append('OS receivables show the allocated share while retaining the full invoice amount for editing')
                assert not errors, errors
            except Exception:
                page.screenshot(path=str(out / 'failure.png'))
                (out / 'failure.html').write_text(page.content())
                (out / 'failure.json').write_text(json.dumps({'checks': checks, 'errors': errors, 'events': api.events, 'unknown_routes': api.unknown}, indent=2, ensure_ascii=False))
                raise
            result = {'passed': len(checks), 'checks': checks, 'page_errors': errors, 'unknown_routes': api.unknown}
            (out / 'results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False))
            print(json.dumps(result, ensure_ascii=False), flush=True)
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == '__main__':
    main()
