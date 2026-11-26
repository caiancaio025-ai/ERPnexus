"""V48 follow-up: real API/PostgreSQL/Chromium, disposable test database only.

DATABASE_URL and SENTICO_TEST_DATABASE_URL must select the same migrated *_test
DB with the test login supplied via SENTICO_E2E_USERNAME/PASSWORD. The runner
starts both local servers and never targets a public URL. Requires Playwright.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from urllib.parse import quote, urlparse

from playwright.sync_api import expect, sync_playwright
from sqlalchemy.engine import make_url

REPO = Path(__file__).resolve().parents[3]
WEB = REPO / 'apps/web'
API = REPO / 'apps/api'
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
    url = os.environ.get('SENTICO_TEST_DATABASE_URL')
    if not url or url != os.environ.get('DATABASE_URL') or not (make_url(url).database or '').endswith('_test'):
        raise RuntimeError('Explicit disposable *_test database required')
    username = os.environ['SENTICO_E2E_USERNAME']
    password = os.environ['SENTICO_E2E_PASSWORD']
    out = args.artifacts.resolve()
    out.mkdir(parents=True, exist_ok=True)
    api_port, web_port = free_port(), free_port()
    while web_port == api_port:
        web_port = free_port()
    base = f'http://127.0.0.1:{web_port}'
    api_base = f'http://127.0.0.1:{api_port}'
    env = {**os.environ, 'APP_ENV': 'development', 'ALLOWED_HOSTS': '127.0.0.1,localhost',
           'CORS_ORIGINS': base, 'VITE_API_PROXY_TARGET': api_base}
    report = {'backend': 'real FastAPI and disposable migrated PostgreSQL; no API mocks',
              'checks': [], 'page_errors': [], 'http_errors': [], 'status': 'running'}
    processes = []
    streams = []
    page = None

    def record(name, **details):
        report['checks'].append({'check': name, **details})
        print('PASS:', name, flush=True)
        (out/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))

    def decode(response):
        assert response.ok, f'HTTP {response.status}: {response.text()[:1200]}'
        return response.json()

    try:
        for name, command, cwd in [
            ('api', [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(api_port)], API),
            ('web', ['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(web_port), '--strictPort'], WEB),
        ]:
            stream = (out/f'{name}.log').open('w')
            streams.append(stream)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=stream))
        wait_ready(api_base+'/health/ready', processes[0])
        wait_ready(base, processes[1])
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1440, 'height': 1050})
            page = context.new_page()
            page.set_default_timeout(20000)
            page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
            page.on('response', lambda response: report['http_errors'].append({'status': response.status, 'path': urlparse(response.url).path}) if response.status >= 400 and '/api/' in response.url else None)
            auth = decode(context.request.post(base+'/api/auth/login', data={'identifier': username, 'password': password}))
            assert auth['name']

            for route in ('/painel', '/compras', '/laboratorio', '/estoque', '/comercial', '/financeiro', '/clientes', '/colaboradores', '/notificacoes'):
                page.goto(base+route)
                header = page.locator('.sentico-header-actions')
                expect(header).to_have_count(1)
                expect(header.get_by_role('button', name='Aparência', exact=True)).to_be_visible()
                expect(header.get_by_role('button', name='Sair do sistema', exact=True)).to_be_visible()
                expect(page.locator('.sentico-sidebar .sentico-tema')).to_have_count(0)
                bounds = header.locator('.sentico-appearance-trigger, .sentico-header-user, .sentico-header-logout').evaluate_all('(items) => items.map(x => ({left:x.getBoundingClientRect().left, right:x.getBoundingClientRect().right}))')
                assert bounds[0]['right'] <= bounds[1]['left'] and bounds[1]['right'] <= bounds[2]['left']
                record('header appearance/user/logout order and sidebar space', route=route)

            page.goto(base+'/compras')
            appearance = page.get_by_role('button', name='Aparência', exact=True)
            appearance.click()
            panel = page.get_by_role('dialog', name='Aparência', exact=True)
            expect(panel).to_be_visible()
            panel.get_by_role('button', name='Tema claro', exact=True).click()
            expect(page.locator('html')).to_have_attribute('data-sentico-theme', 'claro')
            panel.get_by_label('Temas comemorativos').select_option('natal')
            panel.get_by_label('Animar decoração').uncheck()
            page.keyboard.press('Escape')
            expect(panel).not_to_be_visible()
            expect(appearance).to_be_focused()
            page.reload()
            expect(page.locator('html')).to_have_attribute('data-sentico-theme', 'claro')
            page.get_by_role('button', name='Aparência', exact=True).click()
            panel = page.get_by_role('dialog', name='Aparência', exact=True)
            expect(panel.get_by_label('Temas comemorativos')).to_have_value('natal')
            expect(panel.get_by_label('Animar decoração')).not_to_be_checked()
            page.screenshot(path=str(out/'appearance-light-desktop.png'), full_page=False)
            panel.get_by_role('button', name='Tema escuro', exact=True).click()
            expect(page.locator('html')).to_have_attribute('data-sentico-theme', 'escuro')
            panel.get_by_label('Temas comemorativos').select_option('desativado')
            page.locator('.purchasing-header h1').click()
            expect(panel).not_to_be_visible()
            record('appearance light/dark/season/animation persistence and Escape/outside close')

            page.set_viewport_size({'width': 390, 'height': 844})
            page.get_by_role('button', name='Aparência', exact=True).click()
            panel = page.get_by_role('dialog', name='Aparência', exact=True)
            expect(panel).to_be_visible()
            box = panel.bounding_box()
            assert box and box['x'] >= 0 and box['x']+box['width'] <= 391
            assert page.locator('body').evaluate('(x) => x.scrollWidth <= window.innerWidth + 1')
            page.screenshot(path=str(out/'appearance-dark-mobile.png'), full_page=False)
            panel.get_by_role('button', name='Fechar aparência', exact=True).click()
            record('mobile appearance fits viewport and can be closed')
            page.set_viewport_size({'width': 1440, 'height': 1050})

            request = decode(context.request.post(base+'/api/purchasing/material-requests', data={
                'company_code': COMPANY, 'item_name': 'Fita adesiva homologação V48', 'quantity': 10,
                'priority': 'normal', 'technical_note': 'Dados sintéticos do teste de recebimento',
            }))
            request_path = f"/api/purchasing/material-requests/{request['id']}"
            for status in ('approved', 'purchasing', 'purchased'):
                decode(context.request.patch(base+request_path, data={'status': status, 'unit_cost': '2.50'}))
            request_url = base+f"/compras?view=requests&solicitacao={request['id']}"
            page.goto(request_url)
            modal = page.locator('.material-request-modal')
            expect(modal.get_by_role('heading', name=request['item_name'], exact=True)).to_be_visible()
            modal.get_by_label('Destino do material').select_option('new')
            modal.get_by_label('Nome no Estoque', exact=True).fill('Fita adesiva individual UI V48')
            modal.get_by_label('Controle', exact=False).select_option('serialized')
            expect(modal.locator('.purchase-stock-receipt-summary')).to_contain_text('10 unidades')
            expect(modal.get_by_label('Série do fabricante (opcional)', exact=True)).to_have_count(0)
            page.screenshot(path=str(out/'request-individual-10.png'), full_page=True)
            with page.expect_response(lambda r: urlparse(r.url).path == request_path and r.request.method == 'PATCH') as saved:
                modal.get_by_role('button', name='Salvar dados sem mudar status', exact=True).click()
            saved_request = decode(saved.value)
            assert saved_request['quantity'] == 10 and saved_request['inventory_mode'] == 'serialized'
            page.goto(request_url)
            modal = page.locator('.material-request-modal')
            expect(modal.get_by_label('Controle', exact=False)).to_have_value('serialized')
            with page.expect_response(lambda r: urlparse(r.url).path == request_path and r.request.method == 'PATCH') as received:
                modal.get_by_role('button', name='Recebido', exact=True).click()
            assert decode(received.value)['status'] == 'received'
            inventory_url = base+'/api/inventory/items?search='+quote('Fita adesiva individual UI V48')
            items = decode(context.request.get(inventory_url))
            assert len(items) == 10 and sum(item['quantity'] for item in items) == 10
            assert len({item['stock_code'] for item in items}) == 10
            assert all(item['mode'] == 'serialized' and item['quantity'] == 1 and item['manufacturer_serial'] is None for item in items)
            decode(context.request.patch(base+request_path, data={'status': 'received'}))
            assert len(decode(context.request.get(inventory_url))) == 10
            record('save/reopen/receive SC quantity10 without OEM; ten unique codes; repeated receipt unchanged', stock_codes=[item['stock_code'] for item in items])

            page.goto(base+'/estoque')
            item = items[0]
            page.get_by_placeholder('Pesquisar peça, etiqueta, série, tipo ou posição').fill(item['stock_code'])
            page.get_by_role('button', name='Editar '+item['name'], exact=True).click()
            form = page.locator('form.inv-dialog')
            serial = form.get_by_label('Série do fabricante (opcional)', exact=True)
            expect(serial).to_be_enabled()
            serial.fill('OEM-UI-V48-001')
            with page.expect_response(lambda r: urlparse(r.url).path == f"/api/inventory/items/{item['id']}" and r.request.method == 'PUT') as updated:
                form.get_by_role('button', name='Salvar item', exact=True).click()
            updated_item = decode(updated.value)
            assert updated_item['manufacturer_serial'] == 'OEM-UI-V48-001'
            assert updated_item['stock_code'] == item['stock_code'] and updated_item['quantity'] == 1
            page.reload()
            expect(page.get_by_text('Série: OEM-UI-V48-001', exact=True)).to_be_visible()
            record('add optional manufacturer serial later through stock UI; internal identity preserved')

            supplier = decode(context.request.post(base+'/api/purchasing/suppliers', data={'name': 'Fornecedor UI V48 recebimento', 'origin': 'national'}))
            for mode, quantity, name in [('serialized', 3, 'Pedido individual UI V48'), ('serialized', 1, 'Pedido único sem série UI V48'), ('bulk', 10, 'Pedido por quantidade UI V48')]:
                page.goto(base+'/compras?view=new')
                page.get_by_label('Título / descrição da compra*', exact=True).fill(name)
                page.get_by_label('Quantidade*', exact=True).fill(str(quantity))
                page.get_by_label('Valor total (R$)*', exact=True).fill(str(quantity*4)+',00')
                page.get_by_label('Loja/fornecedor*', exact=False).select_option(str(supplier['id']))
                page.get_by_label('Quando chegar, enviar para:', exact=False).select_option('new')
                page.get_by_label('Nome técnico do novo item no Estoque (independente do pedido)', exact=True).fill(name)
                page.get_by_label('Tipo de controle', exact=False).select_option(mode)
                page.get_by_label('Status atual', exact=False).select_option('delivered')
                if mode == 'serialized' and quantity == 1:
                    expect(page.get_by_label('Série do fabricante (opcional)', exact=True)).to_have_value('')
                with page.expect_response(lambda r: urlparse(r.url).path == '/api/purchasing/orders' and r.request.method == 'POST') as created:
                    page.get_by_role('button', name='Salvar compra no sistema', exact=True).click()
                purchase = decode(created.value)
                assert purchase['quantity'] == quantity and purchase['inventory_serial'] is None
                stock = decode(context.request.get(base+'/api/inventory/items?search='+quote(name)))
                assert len(stock) == (quantity if mode == 'serialized' else 1)
                assert sum(part['quantity'] for part in stock) == quantity
                page.goto(base+f"/compras?pedido={purchase['id']}")
                expect(page.get_by_label('Quantidade*', exact=True)).to_have_value(str(quantity))
                expect(page.get_by_label('Quantidade*', exact=True)).to_be_disabled()
                record('PC delivered through UI and persisted/reopened', mode=mode, quantity=quantity, items=len(stock))

            assert not report['page_errors'], report['page_errors']
            assert not report['http_errors'], report['http_errors']
            page.get_by_role('button', name='Sair do sistema', exact=True).click()
            expect(page.get_by_role('heading', name='Iniciar sessão', exact=True)).to_be_visible()
            record('header logout ends session')
            report['status'] = 'passed'
            browser.close()
    except Exception:
        report['status'] = 'failed'
        report['failure'] = traceback.format_exc()
        if page is not None:
            try:
                page.screenshot(path=str(out/'failure.png'), full_page=True)
            except Exception:
                pass
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for stream in streams:
            stream.close()
    print(json.dumps({'status': report['status'], 'passed': len(report['checks'])}), flush=True)


if __name__ == '__main__':
    main()
