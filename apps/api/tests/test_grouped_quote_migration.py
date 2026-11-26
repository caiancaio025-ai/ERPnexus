"""Real incremental upgrade with legacy OS, individual quote and receivables.

Opt-in because this test needs CREATE DATABASE on an explicitly disposable
PostgreSQL server. It never downgrades or restores the caller's database.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

API = Path(__file__).resolve().parents[1]

LEGACY_FIXTURE = r'''
from fastapi.testclient import TestClient
from app.main import app

def checked(response):
    assert response.status_code < 300, response.text
    return response.json()

with TestClient(app) as client:
    checked(client.post('/auth/login', json={'identifier': 'migration_owner', 'password': 'Migration-only-test!'}))
    customer = checked(client.post('/customers', json={
        'company_code': 'universo_eletronica', 'legal_name': 'Cliente sintético anterior à migração',
    }))
    order = checked(client.post('/laboratory/work-orders', json={
        'company_code': 'universo_eletronica', 'customer_id': customer['id'],
        'customer_name': customer['legal_name'], 'equipment_type': 'Inversor',
        'manufacturer': 'Fabricante de teste', 'model': 'MODELO-ANTERIOR',
        'serial_number': 'SERIE-LEGADA-001', 'reported_defect': 'Não liga',
        'approved_value': '123.45', 'entry_invoice': 'ENTRADA-ANTERIOR',
        'exit_invoice': 'SAIDA-ANTERIOR',
    }))
    checked(client.post(f"/laboratory/work-orders/{order['id']}/quotes", json={
        'technical_report': 'Laudo anterior à migração, com conteúdo preservado.',
        'services_description': 'Reparo do equipamento.',
        'payment_terms': 'PIX', 'return_condition': 'Devolução após 30 dias.',
        'consumer_clause': 'Garantia legal.', 'supply_clause': 'Prazo sujeito a insumos.',
        'estimate_clause': 'Proposta prévia com aprovação do cliente.',
        'items': [{'description': 'Serviço anterior', 'quantity': '1', 'unit_value': '123.45'}],
    }))
    checked(client.post('/finance/entries', headers={'Idempotency-Key': 'migration-preserved-entry'}, json={
        'entry_type': 'income', 'company_code': 'universo_eletronica',
        'work_order_id': order['id'], 'nfse_number': 'SAIDA-ANTERIOR',
        'counterparty_name': customer['legal_name'], 'description': 'Receita anterior à migração',
        'amount': '123.45', 'issue_date': '2026-11-26', 'posting_date': '2026-11-26',
        'due_date': '2026-12-26', 'bank_name': 'Itaú',
    }))
'''


def _fingerprints(engine):
    with engine.connect() as connection:
        tables = connection.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename <> 'alembic_version' ORDER BY tablename"
        )).scalars().all()
        result = {}
        for table in tables:
            quoted = connection.dialect.identifier_preparer.quote(table)
            rows = connection.execute(text(f"SELECT to_jsonb(t)::text FROM public.{quoted} t ORDER BY 1")).scalars()
            digest = hashlib.sha256()
            count = 0
            for row in rows:
                digest.update(row.encode('utf-8') + b'\n')
                count += 1
            result[table] = (count, digest.hexdigest())
        return result


def test_incremental_grouped_quote_migration_preserves_all_existing_rows():
    if os.environ.get('SENTICO_MIGRATION_PG_SMOKE') != '1':
        pytest.skip('Migration rehearsal needs explicitly enabled disposable PostgreSQL.')
    url = os.environ.get('SENTICO_TEST_DATABASE_URL', '')
    parsed = make_url(url)
    assert url == os.environ.get('DATABASE_URL') and (parsed.database or '').endswith('_test')
    assert parsed.host == '127.0.0.1' and parsed.username == 'sentico_test'
    name = f'sentico_grouped_upgrade_{uuid4().hex[:12]}_test'
    admin = create_engine(url, isolation_level='AUTOCOMMIT', poolclass=NullPool)
    migration_url = parsed.set(database=name).render_as_string(hide_password=False)
    engine = create_engine(migration_url, poolclass=NullPool)
    created = False
    env = {
        **os.environ, 'DATABASE_URL': migration_url, 'SENTICO_TEST_DATABASE_URL': migration_url,
        'APP_ENV': 'development', 'ALLOWED_HOSTS': 'testserver,127.0.0.1,localhost',
        'SENTICO_DEV_TEST_ACCOUNT': '0',
    }

    def run(*arguments):
        result = subprocess.run([sys.executable, *arguments], cwd=API, env=env,
                                text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr

    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE {name}'))
            created = True
        run('-m', 'alembic', 'upgrade', '20261009_01')
        from app.auth.security import hash_password
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (name,email,username,password_hash,role,modules,is_active) "
                "VALUES ('Migration owner','migration@example.invalid','migration_owner',:hash,'gestao','[]',true)"
            ), {'hash': hash_password('Migration-only-test!')})
        run('-m', 'alembic', 'upgrade', '20261126_01')
        run('-c', LEGACY_FIXTURE)
        before = _fingerprints(engine)
        assert all(before[table][0] > 0 for table in (
            'users', 'laboratory_customers', 'laboratory_work_orders', 'laboratory_quotes',
            'laboratory_quote_items', 'financial_entries', 'financial_audit_events',
        ))
        run('-m', 'alembic', 'upgrade', '20261126_02')
        after = _fingerprints(engine)
        assert {table: after[table] for table in before} == before
        assert set(after) - set(before) == {
            'laboratory_quote_groups', 'laboratory_grouped_quotes',
            'laboratory_grouped_quote_work_orders', 'laboratory_grouped_quote_items',
        }
        assert all(after[table][0] == 0 for table in set(after) - set(before))
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '20261126_02'
        run('-m', 'alembic', 'upgrade', 'head')
        assert _fingerprints(engine) == after
    finally:
        engine.dispose()
        if created:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE {name} WITH (FORCE)'))
        admin.dispose()
