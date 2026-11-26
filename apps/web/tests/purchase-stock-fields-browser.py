"""Inline stock fields correction: real API/PostgreSQL/Chromium, disposable test database only.

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

            assert decode(context.request.get(base+'/api/health/version'))['revision'] == 'v48-20261126-faturamento-estoque'
            category = decode(context.request.post(base+'/api/inventory/categories', data={'code':'teste_recebimento','name':'Ventiladores de teste'}))
            subtype = decode(context.request.post(base+'/api/inventory/subtypes', data={'category':category['code'],'code':'axial_teste','name':'Axial de teste'}))
            fmt = decode(context.request.post(base+'/api/inventory/formats', data={'category':category['code'],'code':'120mm_teste','name':'120 mm teste'}))
            area = decode(context.request.post(base+'/api/inventory/areas', data={'code':'AREA_E2E','name':'Área E2E'}))
            kind = decode(context.request.post(base+'/api/inventory/types', data={'code':'caixa_e2e','name':'Caixa E2E'}))
            container = decode(context.request.post(base+'/api/inventory/containers', data={'area_id':area['id'],'type_id':kind['id'],'code':'CAIXA_E2E','name':'Caixa de recebimento','rows':1,'columns':2}))
            catalog = decode(context.request.get(base+f'/api/purchasing/stock-options?company_code={COMPANY}'))
            slot = next(row for row in catalog['slots'] if row['container_id'] == container['id'])

            request = decode(context.request.post(base+'/api/purchasing/material-requests', data={
                'company_code': COMPANY, 'item_name': 'Ventiladores de homologação', 'quantity': 10,
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
            modal.get_by_label('Nome do item', exact=True).fill('Ventilador individual UI')
            modal.get_by_label('Controle', exact=True).select_option('serialized')
            expect(modal.locator('.purchase-stock-receipt-summary')).to_contain_text('10 unidades')
            expect(modal.get_by_label('Série do fabricante (opcional)', exact=True)).to_have_count(0)
            modal.get_by_label('Tipo de componente', exact=True).select_option(category['code'])
            modal.get_by_label('Posição física', exact=True).fill(slot['code'])
            modal.get_by_role('option', name=slot['code']+' · '+slot['name'], exact=False).click()
            modal.get_by_label('Descrição', exact=True).fill('Ventilador 220V para reposição')
            modal.get_by_text('Mais detalhes do item', exact=True).click()
            modal.get_by_label('Subtipo', exact=True).select_option(str(subtype['id']))
            modal.get_by_label('Formato / encapsulamento', exact=True).select_option(str(fmt['id']))
            modal.get_by_label('Fabricante', exact=True).fill('Marca de teste')
            modal.get_by_label('Modelo', exact=True).fill('VENT-120')
            page.screenshot(path=str(out/'request-individual-10.png'), full_page=True)
            lost = {'commits':0}
            def lose_patch_response(route):
                if route.request.method == 'PATCH' and lost['commits'] == 0:
                    response = route.fetch()
                    assert response.status == 200, response.text()
                    lost['commits'] += 1
                    route.abort('failed')
                else:
                    route.continue_()
            page.route('**'+request_path, lose_patch_response)
            modal.get_by_role('button', name='Salvar dados sem mudar status', exact=True).click()
            expect(page.locator('.material-request-modal')).to_have_count(0)
            page.unroute('**'+request_path, lose_patch_response)
            assert lost['commits'] == 1
            saved_request = decode(context.request.get(base+request_path))
            assert saved_request['quantity'] == 10 and saved_request['inventory_mode'] == 'serialized'
            assert saved_request['inventory_details']['slot_id'] == slot['id']
            assert saved_request['inventory_details']['model'] == 'VENT-120'
            assert not decode(context.request.get(base+'/api/inventory/items?search='+quote('Ventilador individual UI')))
            record('SC draft saves complete stock details without receiving; lost acknowledgement reconciled by GET with one PATCH')
            page.goto(request_url)
            modal = page.locator('.material-request-modal')
            expect(modal.get_by_label('Controle', exact=True)).to_have_value('serialized')
            expect(modal.get_by_label('Tipo de componente', exact=True)).to_have_value(category['code'])
            expect(modal.get_by_label('Posição física', exact=True)).to_have_value(slot['code']+' · '+slot['name'])
            modal.get_by_text('Mais detalhes do item', exact=True).click()
            expect(modal.get_by_label('Modelo', exact=True)).to_have_value('VENT-120')
            expect(modal.get_by_label('Subtipo', exact=True)).to_have_value(str(subtype['id']))
            lost['commits'] = 0
            page.route('**'+request_path, lose_patch_response)
            modal.get_by_role('button', name='Recebido', exact=True).click()
            expect(page.locator('.material-request-modal')).to_have_count(0)
            page.unroute('**'+request_path, lose_patch_response)
            assert lost['commits'] == 1 and decode(context.request.get(base+request_path))['status'] == 'received'
            inventory_url = base+'/api/inventory/items?search='+quote('Ventilador individual UI')
            items = decode(context.request.get(inventory_url))
            assert len(items) == 10 and sum(item['quantity'] for item in items) == 10
            assert len({item['stock_code'] for item in items}) == 10
            assert all(item['mode'] == 'serialized' and item['quantity'] == 1 and item['manufacturer_serial'] is None for item in items)
            assert all(item['slot_id'] == slot['id'] and item['subtype_id'] == subtype['id'] and item['format_id'] == fmt['id'] and item['manufacturer'] == 'Marca de teste' and item['model'] == 'VENT-120' and item['notes'] == 'Ventilador 220V para reposição' and item['unit'] == 'UN' for item in items)
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

            page.goto(base+'/estoque')
            page.get_by_role('button', name='Cadastrar item', exact=True).click()
            manual = page.locator('form.inv-dialog')
            expect(manual.locator('.inventory-item-fields').first).to_be_visible()
            manual.get_by_label('Nome do item', exact=True).fill('Cadastro avulso compartilhado')
            manual.get_by_label('Tipo de componente', exact=True).select_option(category['code'])
            manual.get_by_label('Quantidade inicial', exact=True).fill('5')
            manual.get_by_label('Descrição', exact=True).fill('Mesmo formulário de identificação do recebimento')
            with page.expect_response(lambda r: urlparse(r.url).path == '/api/inventory/items' and r.request.method == 'POST') as manual_response:
                manual.get_by_role('button', name='Salvar item', exact=True).click()
            manual_item = decode(manual_response.value)
            assert manual_item['quantity'] == 5 and manual_item['category'] == category['code']
            record('Direct stock entry uses the same fields and saves a bulk item')

            supplier = decode(context.request.post(base+'/api/purchasing/suppliers', data={'name': 'Fornecedor UI V48 recebimento', 'origin': 'national'}))
            for mode, quantity, name in [('serialized', 3, 'Pedido individual UI V48'), ('serialized', 1, 'Pedido único sem série UI V48'), ('bulk', 10, 'Pedido por quantidade UI V48')]:
                page.goto(base+'/compras?view=new')
                page.get_by_label('Título / descrição da compra*', exact=True).fill(name)
                page.get_by_label('Quantidade*', exact=True).fill(str(quantity))
                page.get_by_label('Valor total (R$)*', exact=True).fill(str(quantity*4)+',00')
                page.get_by_label('Loja/fornecedor*', exact=False).select_option(str(supplier['id']))
                page.get_by_label('Destino do material', exact=True).select_option('new')
                page.get_by_label('Nome do item', exact=True).fill(name)
                page.get_by_label('Controle', exact=True).select_option(mode)
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

            # An existing bulk item receives only the purchase quantity, with the same identity.
            existing_request = decode(context.request.post(base+'/api/purchasing/material-requests', data={'company_code':COMPANY,'item_name':'Somar ao cadastro existente','quantity':4,'inventory_destination':'existing','inventory_item_id':manual_item['id']}))
            existing_path=f"/api/purchasing/material-requests/{existing_request['id']}"
            for status in ('approved','purchasing','purchased'):
                decode(context.request.patch(base+existing_path,data={'status':status,'unit_cost':'1.00'}))
            page.goto(base+f"/compras?view=requests&solicitacao={existing_request['id']}")
            modal=page.locator('.material-request-modal')
            expect(modal.get_by_label('Destino do material',exact=True)).to_have_value('existing')
            with page.expect_response(lambda r: urlparse(r.url).path == existing_path and r.request.method=='PATCH') as existing_received:
                modal.get_by_role('button',name='Recebido',exact=True).click()
            decode(existing_received.value)
            matching=decode(context.request.get(base+'/api/inventory/items?search='+quote('Cadastro avulso compartilhado')))
            assert len(matching)==1 and matching[0]['id']==manual_item['id'] and matching[0]['quantity']==9
            record('Existing-item destination adds quantity to the same stock identity')

            page.set_viewport_size({'width':390,'height':844})
            page.goto(request_url)
            modal=page.locator('.material-request-modal')
            expect(modal.get_by_label('Nome do item',exact=True)).to_be_visible()
            target=modal.locator('.purchase-stock-target')
            assert target.evaluate('(x)=>x.scrollWidth<=x.clientWidth+1')
            page.screenshot(path=str(out/'purchase-stock-mobile.png'),full_page=True)
            record('Shared stock fields fit a mobile purchase editor')

            assert not report['page_errors'], report['page_errors']
            assert not report['http_errors'], report['http_errors']
            modal.get_by_role('button', name='Fechar', exact=True).click()
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
