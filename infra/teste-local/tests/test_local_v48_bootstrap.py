"""Focused guards and an opt-in smoke against a disposable native PostgreSQL."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps/api"
SPEC = importlib.util.spec_from_file_location("local_v48_bootstrap", Path(__file__).parents[1] / "bootstrap_v48.py")
helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helper
SPEC.loader.exec_module(helper)


def environment():
    return {
        "APP_ENV": "development", "SENTICO_LOCAL_TEST_RUN": "v48",
        "SENTICO_LOCAL_TEST_INSTANCE": "a" * 48, "SENTICO_LOCAL_TEST_PASSWORD": "c" * 32,
        "DATABASE_URL": "postgresql+psycopg://sentico_v48_test:" + "b" * 64 + "@db:5432/sentico_v48_test",
    }


def test_accepts_only_explicit_local_contract_without_exposing_credentials():
    config = helper.local_config(environment())
    assert config.instance == "a" * 48
    assert "b" * 64 not in repr(config) and "c" * 32 not in repr(config)
    assert helper.migration_plan(API)[-1] == helper.TARGET


@pytest.mark.parametrize("key,value", [
    ("APP_ENV", "production"), ("SENTICO_LOCAL_TEST_RUN", ""),
    ("SENTICO_LOCAL_TEST_INSTANCE", "a" * 47), ("SENTICO_LOCAL_TEST_PASSWORD", "123"),
    ("DATABASE_URL", "postgresql+psycopg://sentico_v48_test:" + "b" * 64 + "@localhost:5432/sentico_v48_test"),
    ("DATABASE_URL", "postgresql+psycopg://sentico_v48_test:" + "b" * 64 + "@db:5432/postgres"),
    ("DATABASE_URL", "postgresql+psycopg://postgres:" + "b" * 64 + "@db:5432/sentico_v48_test"),
    ("DATABASE_URL", "postgresql+psycopg://sentico_v48_test:short@db:5432/sentico_v48_test"),
    ("DATABASE_URL", "postgresql+psycopg://sentico_v48_test:" + "b" * 64 + "@db:5432/sentico_v48_test?options=unsafe"),
])
def test_rejects_nonlocal_or_incomplete_environment_before_connecting(key, value):
    env = {**environment(), key: value}
    with pytest.raises(helper.BootstrapError):
        helper.local_config(env)


def test_cli_never_echoes_external_exception_or_database_credentials(monkeypatch, capsys):
    secret = environment()["DATABASE_URL"]
    def failure():
        raise RuntimeError(secret)
    monkeypatch.setattr(helper, "bootstrap", failure)
    assert helper.main() == 1
    captured = capsys.readouterr()
    assert "BOOTSTRAP_TESTE_V48=ERRO" in captured.err
    assert secret not in captured.err and "b" * 64 not in captured.err and "RuntimeError" not in captured.err


def test_native_postgres_fresh_ready_upgrade_repeat_and_foreign_database_refusal(monkeypatch):
    if os.environ.get("SENTICO_LOCAL_BOOTSTRAP_PG_SMOKE") != "1":
        pytest.skip("Smoke nativo exige PostgreSQL descartável explicitamente habilitado.")
    initial_url = os.environ.get("DATABASE_URL", "")
    root_url = make_url(initial_url)
    assert initial_url == os.environ.get("SENTICO_TEST_DATABASE_URL")
    assert root_url.host == "127.0.0.1" and root_url.database == "sentico_test" and root_url.username == "sentico_test"
    admin = create_engine(initial_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    with admin.connect() as connection:
        connection.execute(text("CREATE ROLE sentico_v48_test LOGIN PASSWORD '" + "b" * 64 + "'"))
        connection.execute(text("CREATE DATABASE sentico_v48_test OWNER sentico_v48_test"))
    admin.dispose()
    native_url = root_url.set(username=helper.DATABASE, password="b" * 64, database=helper.DATABASE).render_as_string(hide_password=False)
    native_engine = create_engine(native_url, poolclass=NullPool)
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SENTICO_DEV_TEST_ACCOUNT", "0")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "sentico_v48_local_smoke")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,api")
    # Only these test adapters replace transport. Product URL/identity guards
    # still run unchanged and PostgreSQL sees the expected real role/database.
    monkeypatch.setattr(helper, "open_engine", lambda config: create_engine(native_url, poolclass=NullPool))
    calls = []
    def native_upgrade(revision, workdir):
        calls.append(revision)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision], cwd=workdir,
                       env={**os.environ, "DATABASE_URL": native_url}, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    monkeypatch.setattr(helper, "upgrade", native_upgrade)
    # Reproduce the previous package's ready installation using its real
    # migrations, then update with the current package without re-seeding it.
    initial_revision = "20261126_02"
    initial_plan = helper.migration_plan(API)
    initial_plan = initial_plan[:initial_plan.index(initial_revision) + 1]
    with monkeypatch.context() as old_package:
        old_package.setattr(helper, "TARGET", initial_revision)
        old_package.setattr(helper, "migration_plan", lambda workdir: initial_plan)
        helper.bootstrap(API)
    assert calls == [helper.BASELINE, initial_revision]
    with native_engine.connect() as connection:
        owner = connection.execute(text("SELECT * FROM users")).mappings().one()
        assert owner["username"] == "teste_v48" and owner["role"] == "gestao" and owner["is_active"]
        assert {"compras", "estoque", "financeiro", "configuracoes", "colaboradores"}.issubset(owner["modules"])
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == initial_revision
        names = set(connection.execute(text("SELECT trade_name FROM commercial_company_profiles")).scalars())
        assert names == {"Universo Eletrônica", "Universo Automação", "Soluções Eletrônica"}
        assert connection.scalar(text("SELECT count(*) FROM purchase_orders")) == 0
        supplier_count = connection.scalar(text("SELECT count(*) FROM purchase_suppliers"))
        preserved_tables = ("users", "commercial_company_profiles", "purchase_suppliers", helper.MARKER)
        before_upgrade = {
            table: connection.execute(text(f"SELECT to_jsonb(t) FROM public.{table} t ORDER BY id")).scalars().all()
            for table in preserved_tables
        }
    calls.clear()
    helper.bootstrap(API)
    assert calls == [helper.TARGET]
    with native_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == helper.TARGET
        assert {
            table: connection.execute(text(f"SELECT to_jsonb(t) FROM public.{table} t ORDER BY id")).scalars().all()
            for table in preserved_tables
        } == before_upgrade
        assert connection.scalar(text("SELECT count(*) FROM laboratory_quote_groups")) == 0
    # A real cookie login confirms that the synthetic owner has useful access.
    monkeypatch.setenv("DATABASE_URL", native_url)
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"identifier": "teste_v48", "password": "c" * 32})
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "gestao"
        assert client.get("/auth/me").status_code == 200
        assert client.get("/finance/entries").status_code == 200
        assert len(client.get("/laboratory/settings/companies").json()) == 3
        assert "sentico_v48_local_smoke" in response.cookies
    monkeypatch.setenv("DATABASE_URL", environment()["DATABASE_URL"])
    from argon2 import PasswordHasher
    changed_hash = PasswordHasher().hash("senha-alterada-pelo-usuario-local")
    with native_engine.begin() as connection:
        connection.execute(text("UPDATE users SET name='Gestor alterado',password_hash=:hash WHERE id=:id"), {"hash": changed_hash, "id": owner["id"]})
        connection.execute(text("UPDATE commercial_company_profiles SET trade_name='Nome preservado' WHERE company_code='universo_eletronica'"))
        connection.execute(text("INSERT INTO purchase_suppliers (name,origin,is_active) VALUES ('Fornecedor ficticio preservado','national',true)"))
    calls.clear()
    helper.bootstrap(API)
    assert calls == []
    with native_engine.connect() as connection:
        after = connection.execute(text("SELECT id,name,password_hash FROM users")).mappings().one()
        assert after == {"id": owner["id"], "name": "Gestor alterado", "password_hash": changed_hash}
        assert connection.scalar(text("SELECT count(*) FROM purchase_suppliers")) == supplier_count + 1
        assert connection.scalar(text("SELECT trade_name FROM commercial_company_profiles WHERE company_code='universo_eletronica'")) == "Nome preservado"
    monkeypatch.setenv("SENTICO_LOCAL_TEST_INSTANCE", "d" * 48)
    with pytest.raises(helper.BootstrapError, match="outra instalação"):
        helper.bootstrap(API)
    monkeypatch.setenv("SENTICO_LOCAL_TEST_INSTANCE", "a" * 48)
    with native_engine.begin() as connection:
        connection.execute(text(f"DROP TABLE {helper.MARKER}"))
    with pytest.raises(helper.BootstrapError, match="não vazio"):
        helper.bootstrap(API)
    assert calls == []
    with native_engine.connect() as connection:
        assert connection.scalar(text("SELECT password_hash FROM users WHERE id=:id"), {"id": owner["id"]}) == changed_hash
        assert connection.scalar(text("SELECT count(*) FROM purchase_suppliers")) == supplier_count + 1
    native_engine.dispose()
