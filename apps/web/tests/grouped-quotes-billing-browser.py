"""Real Chromium/API/PostgreSQL flow for grouped quotes and multi-OS billing.

Uses synthetic data in an explicitly configured disposable *_test database.
Starts both servers locally; no API mocks and no external application writes.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
COMPANY = 'universo_eletronica'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_ready(url, process):
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError('Local test server exited before readiness')
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.1)
    raise RuntimeError('Local test server did not become ready')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chromium', required=True)
    parser.add_argument('--artifacts', required=True, type=Path)
    args = parser.parse_args()
    database = os.environ.get('SENTICO_TEST_DATABASE_URL')
    if not database or database != os.environ.get('DATABASE_URL') or not (make_url(database).database or '').endswith('_test'):
        raise RuntimeError('Explicit disposable *_test database required')
    out = args.artifacts.resolve()
    out.mkdir(parents=True, exist_ok=True)
    api_port, web_port = free_port(), free_port()
    while api_port == web_port:
        web_port = free_port()
    base, api_base = f'http://127.0.0.1:{web_port}', f'http://127.0.0.1:{api_port}'
    env = {**os.environ, 'APP_ENV': 'development', 'ALLOWED_HOSTS': 'localhost,127.0.0.1',
           'CORS_ORIGINS': base, 'VITE_API_PROXY_TARGET': api_base}
    report = {'backend': 'Real FastAPI, disposable migrated PostgreSQL and Chromium; no API mocks',
              'status': 'running', 'checks': [], 'page_errors': [], 'server_errors': []}
    processes, streams = [], []
    page = None
    pw = browser = None

    def record(name, **details):
        report['checks'].append({'check': name, **details})
        print('PASS:', name, flush=True)
        (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))

    def decode(response):
        assert response.ok, f'HTTP {response.status}: {response.text()[:1500]}'
        return response.json()

    try:
        for name, command, cwd in (
            ('api', [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(api_port)], ROOT / 'apps/api'),
            ('web', ['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(web_port), '--strictPort'], ROOT / 'apps/web'),
        ):
            stream = (out / f'{name}.log').open('w')
            streams.append(stream)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=stream))
        wait_ready(api_base + '/health/ready', processes[0])
        wait_ready(base, processes[1])
        pw = sync_playwright().start()
        browser = pw.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(20000)
        page.on('dialog', lambda dialog: dialog.accept())
        page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
        page.on('response', lambda response: report['server_errors'].append({'status': response.status, 'path': urlparse(response.url).path}) if response.status >= 500 and '/api/' in response.url else None)
        decode(context.request.post(base + '/api/auth/login', data={
            'identifier': os.environ['SENTICO_E2E_USERNAME'], 'password': os.environ['SENTICO_E2E_PASSWORD'],
        }))

        customers = [decode(context.request.post(base + '/api/customers', data={
            'company_code': COMPANY, 'legal_name': name,
        })) for name in ('Cliente de três inversores E2E', 'Outro cliente E2E')]
        orders = []
        for index in range(4):
            customer = customers[0 if index < 3 else 1]
            orders.append(decode(context.request.post(base + '/api/laboratory/work-orders', data={
                'company_code': COMPANY, 'customer_id': customer['id'], 'customer_name': customer['legal_name'],
                'equipment_type': 'Inversor', 'manufacturer': 'Fabricante de teste', 'model': 'MODELO-IGUAL',
                'serial_number': f'SERIE-E2E-{index+1:03d}', 'reported_defect': 'Não liga; verificar entrada e placa de potência.',
                'approved_value': f'100.0{index+1}', 'entry_invoice': '123456',
                **({'exit_invoice': 'NF-ANTERIOR'} if index == 0 else {}),
            })))
        selected = orders[:3]
        page.goto(base + '/laboratorio')
        for order in selected:
            page.get_by_role('checkbox', name=f"Selecionar {order['number']}", exact=True).check()
        expect(page.locator('.lab-detail')).to_have_count(0)
        expect(page.get_by_role('checkbox', name=f"Selecionar {orders[3]['number']}", exact=True)).to_be_disabled()
        selection = page.get_by_role('region', name='OS selecionadas')
        expect(selection).to_contain_text('3 OS selecionada(s)')
        record('Laboratory selection keeps distinct equipment and rejects a different customer')

        with page.expect_response(lambda r: urlparse(r.url).path == '/api/laboratory/grouped-quotes' and r.request.method == 'POST') as created:
            page.get_by_role('button', name='Criar orçamento conjunto', exact=True).click()
        quote = decode(created.value)
        quote_path = f"/api/laboratory/grouped-quotes/{quote['id']}"
        dialog = page.locator('dialog.grouped-quote-dialog')
        expect(dialog.get_by_label('Título do documento', exact=True)).to_be_visible()
        expect(dialog.locator('.grouped-quote-order')).to_have_count(3)
        dialog.get_by_label('Título do documento', exact=True).fill('Manutenção conjunta de três inversores')
        dialog.get_by_label('Diagnóstico técnico / laudo', exact=True).fill('Equipamentos idênticos com falha de alimentação. Identificação individual preservada pelas séries e pelas OS.')
        dialog.get_by_label('Serviço a realizar', exact=True).fill('Substituição de componentes, limpeza, calibração e testes funcionais em cada equipamento.')
        for index, order in enumerate(selected):
            card = dialog.locator('.grouped-quote-order').filter(has=page.get_by_text(order['number'], exact=True))
            card.get_by_label(f"Descrição — {order['number']}", exact=True).fill('Manutenção do inversor e teste de carga')
            card.get_by_label('Valor unitário (R$)', exact=True).fill(f'100,0{index+1}')
        dialog.get_by_role('combobox', name=re.compile('^Desconto')).select_option('amount')
        dialog.get_by_label('Valor do desconto', exact=True).fill('0,05')
        with page.expect_response(lambda r: urlparse(r.url).path == quote_path and r.request.method == 'PUT') as saved:
            dialog.get_by_role('button', name='Salvar rascunho', exact=True).click()
        quote = decode(saved.value)
        assert Decimal(quote['subtotal']) == Decimal('300.06') and Decimal(quote['total']) == Decimal('300.01')
        assert sum(Decimal(row['total']) for row in quote['work_orders']) == Decimal('300.01')
        assert {row['id'] for row in quote['work_orders']} == {order['id'] for order in selected}
        page.screenshot(path=str(out / 'grouped-quote-desktop.png'), full_page=True)
        record('One draft for three same-model equipment units, exact discount and totals by OS', total=quote['total'])

        # The real API commits, then the browser loses that one response.
        # Reconciliation must acknowledge saved content without a second PUT.
        lost_response = {'commits': 0}
        def lose_saved_response(route):
            if route.request.method == 'PUT' and not lost_response['commits']:
                response = route.fetch()
                assert response.status == 200, response.text()
                lost_response['commits'] += 1
                route.abort('failed')
            else:
                route.continue_()
        page.route('**' + quote_path, lose_saved_response)
        dialog.get_by_label('Título do documento', exact=True).fill('Salvo apesar da resposta perdida')
        dialog.get_by_role('button', name='Salvar rascunho', exact=True).click()
        expect(dialog.locator('.grouped-quote-notice')).to_contain_text('salva')
        expect(dialog.locator('.grouped-quote-dirty')).to_have_count(0)
        expect(dialog.get_by_role('alert')).to_have_count(0)
        assert lost_response['commits'] == 1
        page.unroute('**' + quote_path, lose_saved_response)
        quote = decode(context.request.get(base + quote_path))
        assert quote['title'] == 'Salvo apesar da resposta perdida'
        record('Lost PUT response after real commit is reconciled without a duplicate save')

        # Two operators: a stale editor must preserve typing and explain the conflict.
        external = decode(context.request.put(base + quote_path, data={**quote, 'title': 'Título atualizado por outro operador'}))
        dialog.get_by_label('Título do documento', exact=True).fill('Texto local ainda não salvo')
        with page.expect_response(lambda r: urlparse(r.url).path == quote_path and r.request.method == 'PUT') as conflict:
            dialog.get_by_role('button', name='Salvar rascunho', exact=True).click()
        assert conflict.value.status == 409
        expect(dialog.get_by_role('alert')).to_be_visible()
        expect(dialog.get_by_label('Título do documento', exact=True)).to_have_value('Texto local ainda não salvo')
        assert decode(context.request.get(base + quote_path))['title'] == external['title']
        dialog.get_by_role('button', name='Recarregar orçamento', exact=True).click()
        expect(dialog.get_by_label('Título do documento', exact=True)).to_have_value(external['title'])
        record('Stale grouped quote edit returns conflict and preserves unsaved typing')

        before_preview = [decode(context.request.get(base + f"/api/laboratory/work-orders/{row['id']}")) for row in selected]
        with context.expect_page() as popup, page.expect_response(lambda r: urlparse(r.url).path == quote_path + '/pdf') as preview:
            dialog.get_by_role('button', name='Visualizar PDF', exact=True).click()
        assert preview.value.status == 200 and preview.value.body().startswith(b'%PDF')
        (out / 'grouped-preview.pdf').write_bytes(preview.value.body())
        popup.value.close()
        assert [decode(context.request.get(base + f"/api/laboratory/work-orders/{row['id']}"))['version'] for row in selected] == [row['version'] for row in before_preview]
        record('PDF preview leaves every OS and draft unchanged')

        with page.expect_download() as downloaded, page.expect_response(lambda r: urlparse(r.url).path == quote_path + '/emit') as emitted:
            dialog.get_by_role('button', name='Salvar e emitir PDF', exact=True).click()
        assert emitted.value.status == 200
        downloaded.value.save_as(out / 'grouped-emitted.pdf')
        emitted_bytes = (out / 'grouped-emitted.pdf').read_bytes()
        assert emitted_bytes.startswith(b'%PDF') and len(emitted_bytes) > 1000
        expect(dialog.get_by_role('button', name='Nova revisão', exact=True)).to_be_visible()
        expect(dialog.get_by_label('Título do documento', exact=True)).to_be_disabled()
        quote = decode(context.request.get(base + quote_path))
        assert quote['status'] == 'emitted'
        for order, allocation in zip(selected, quote['work_orders'], strict=True):
            updated = decode(context.request.get(base + f"/api/laboratory/work-orders/{order['id']}"))
            assert Decimal(updated['quoted_value']) == Decimal(allocation['total'])
            assert Decimal(updated['approved_value']) == Decimal(order['approved_value'])
        assert context.request.get(base + quote_path + '/pdf').body() == emitted_bytes
        record('Emitted PDF stores one immutable document and each OS keeps its approved amount', sha256=hashlib.sha256(emitted_bytes).hexdigest())

        with page.expect_response(lambda r: urlparse(r.url).path == quote_path + '/revisions' and r.request.method == 'POST') as revision:
            dialog.get_by_role('button', name='Nova revisão', exact=True).click()
        revision_quote = decode(revision.value)
        assert revision_quote['revision'] == 2 and revision_quote['status'] == 'draft'
        expect(dialog.get_by_label('Título do documento', exact=True)).to_be_enabled()
        dialog.get_by_role('button', name='Fechar orçamento conjunto', exact=True).click()
        record('New revision is editable while the original issued document stays available')

        for order in selected:
            page.get_by_role('checkbox', name=f"Selecionar {order['number']}", exact=True).check()
        page.get_by_role('button', name='Faturar selecionadas', exact=True).click()
        form = page.locator('.finance-modal')
        expect(form.locator('.billing-order-card')).to_have_count(3)
        form.get_by_label('Descrição', exact=True).fill('Manutenção conjunta — três inversores')
        form.get_by_label('NFS-e', exact=True).fill('486001')
        expect(form.get_by_label('NF de saída nas OS', exact=False)).to_have_value('486001')
        form.get_by_role('button', name='Parcelado', exact=True).click()
        form.get_by_label('Quantidade', exact=True).fill('3')
        form.get_by_role('button', name='Dividir valor igualmente', exact=True).click()
        expect(form.locator('.finance-installment-list article')).to_have_count(3)
        form.get_by_role('button', name='Sugerir vencimentos mensais', exact=True).click()
        page.screenshot(path=str(out / 'billing-three-orders.png'), full_page=True)
        with page.expect_response(lambda r: urlparse(r.url).path == '/api/finance/billing-batches' and r.request.method == 'POST') as billed:
            form.get_by_role('button', name='Faturar 3 OS', exact=True).click()
        batch = decode(billed.value)
        assert len(batch['work_orders']) == 3 and Decimal(batch['total_amount']) == Decimal('300.06')
        assert all(len(row['obligation']['installments']) == 3 for row in batch['work_orders'])
        for position in range(3):
            assert sum(Decimal(row['obligation']['installments'][position]['amount']) for row in batch['work_orders']) == Decimal('100.02')
        expect(page.locator('.billing-batch-success')).to_contain_text('Faturamento concluído: 3 OS')
        replay = decode(context.request.post(base + '/api/finance/billing-batches', data=billed.value.request.post_data_json,
            headers={'Idempotency-Key': billed.value.request.headers['idempotency-key']}))
        assert [row['obligation']['id'] for row in replay['work_orders']] == [row['obligation']['id'] for row in batch['work_orders']]
        for index, order in enumerate(selected):
            updated = decode(context.request.get(base + f"/api/laboratory/work-orders/{order['id']}"))
            assert updated['status'] == 'invoiced'
            if index == 0:
                assert updated['exit_invoice'] == 'NF-ANTERIOR' and updated['exit_invoice_2'] == '486001'
            else:
                assert updated['exit_invoice'] == '486001'
            receivables = decode(context.request.get(base + f"/api/finance/work-orders/{order['id']}/receivables"))
            assert Decimal(receivables['total_registered']) == Decimal(order['approved_value'])
        record('Three OS billed with three installments; exact receivables, NF synchronization and safe retry', batch_id=batch['batch_id'])

        page.goto(base + f"/laboratorio?os={selected[0]['id']}&aba=financial")
        detail = page.locator('.lab-detail')
        expect(detail).to_be_visible()
        detail.get_by_role('button', name='Valores', exact=True).click()
        expect(detail.get_by_label('NF de saída', exact=True)).to_have_value('NF-ANTERIOR')
        expect(detail.get_by_label('NF de saída 2', exact=True)).to_have_value('486001')
        detail.get_by_label('NF de saída 3', exact=True).fill('NF-MANUAL-003')
        with page.expect_response(lambda r: urlparse(r.url).path == f"/api/laboratory/work-orders/{selected[0]['id']}" and r.request.method == 'PATCH') as invoice_saved:
            detail.get_by_role('button', name='Salvar alterações', exact=True).click()
        assert decode(invoice_saved.value)['exit_invoice_3'] == 'NF-MANUAL-003'
        page.reload()
        expect(detail.get_by_label('NF de saída 3', exact=True)).to_have_value('NF-MANUAL-003')
        assert context.request.get(base + quote_path + '/pdf').body() == emitted_bytes
        page.screenshot(path=str(out / 'laboratory-exit-invoices.png'), full_page=True)
        record('Laboratory exposes all three exit invoices, saves edits and keeps issued quote bytes unchanged')

        detail.get_by_role('button', name='Orçamento', exact=True).click()
        panel = detail.locator('.grouped-quotes-panel')
        expect(panel.get_by_text(quote['code'], exact=False)).to_be_visible()
        panel.get_by_role('button', name=re.compile(re.escape(quote['code']))).click()
        expect(page.locator('dialog.grouped-quote-dialog').get_by_role('combobox', name=re.compile('^Revisão'))).to_contain_text('revisão 2')
        page.set_viewport_size({'width': 390, 'height': 844})
        dialog = page.locator('dialog.grouped-quote-dialog')
        expect(dialog).to_be_visible()
        bounds = dialog.bounding_box()
        assert bounds and bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 391
        assert dialog.evaluate('(x) => x.scrollWidth <= x.clientWidth + 1')
        page.screenshot(path=str(out / 'grouped-quote-mobile.png'), full_page=True)
        record('Grouped history reopens from a linked OS and its editor fits a mobile viewport')
        assert not report['page_errors'], report['page_errors']
        assert not report['server_errors'], report['server_errors']
        report['status'] = 'passed'
        browser.close()
    except Exception:
        report['status'] = 'failed'
        report['error'] = traceback.format_exc()
        if page:
            try:
                page.screenshot(path=str(out / 'failure.png'), full_page=True)
                (out / 'failure.html').write_text(page.content())
            except Exception:
                pass
        raise
    finally:
        (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        if browser:
            browser.close()
        if pw:
            pw.stop()
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for stream in streams:
            stream.close()


if __name__ == '__main__':
    main()
