"""Read-only migration fingerprints and receipt-schema checks, without Docker."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location("deploy_v48_inventory_helper", Path(__file__).parents[1] / "deploy_v48.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
BASE = "20261123_02"
TARGET = "20261126_01"


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def mappings(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return self.value

    def one(self):
        return self.value

    def one_or_none(self):
        return self.value

    def __iter__(self):
        return iter((row,) for row in self.value)


@pytest.fixture
def database(monkeypatch):
    import sqlalchemy

    state = SimpleNamespace(
        revision=TARGET, readonly="on", queries=[], options=None, disposed=False,
        column={"required": True, "type": "int4", "default_value": "1"},
        constraints=[
            {"kind": "u", "columns": ["purchase_order_id", "receipt_unit_index"], "definition": "UNIQUE (purchase_order_id, receipt_unit_index)"},
            {"kind": "u", "columns": ["material_request_id", "receipt_unit_index"], "definition": "UNIQUE (material_request_id, receipt_unit_index)"},
            {"kind": "c", "columns": ["receipt_unit_index"], "definition": "CHECK ((receipt_unit_index > 0))"},
        ],
        rows={"inventory_items": ['{"id": 1, "quantity": 1, "unit_cost": 12.50}'],
              "inventory_movements": ['{"id": 1, "quantity": 1, "receipt_unit_index": 1, "unit_cost": 12.50}']},
        counts={"inventory_items": 1, "inventory_movements": 1},
    )

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execution_options(self, **options):
            assert options == {"stream_results": True}
            return self

        def execute(self, statement):
            sql = str(statement)
            state.queries.append(sql)
            assert sql.startswith("SELECT ")
            if "transaction_read_only" in sql:
                return Result(state.readonly)
            if "alembic_version" in sql:
                return Result([state.revision])
            if "pg_attribute a JOIN pg_type" in sql:
                return Result(state.column)
            if "FROM pg_constraint c" in sql:
                return Result(state.constraints)
            table = "inventory_movements" if "public.inventory_movements" in sql else "inventory_items"
            if "count(*) AS rows" in sql:
                return Result({"rows": state.counts[table], "quantity": 1, "value": "12.50"})
            assert "ORDER BY id" in sql
            if table == "inventory_movements":
                assert ("jsonb_build_object('receipt_unit_index', 1)" in sql) == (state.revision == BASE)
            return Result(state.rows[table])

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            state.disposed = True

    def create_engine(url, **options):
        state.options = options
        return Engine()

    monkeypatch.setattr(sqlalchemy, "create_engine", create_engine)
    monkeypatch.setattr(helper, "_load_settings", lambda: SimpleNamespace(database_url="postgresql+psycopg://fixture:secret@db/fixture"))
    return state


def test_old_and_new_snapshots_match_only_with_preserved_rows_and_default_unit_index(database):
    database.revision = BASE
    before = helper.inventory_snapshot(BASE)
    database.revision = TARGET
    after = helper.inventory_snapshot(TARGET)
    assert before == after
    for table, snapshot in after.items():
        expected = hashlib.sha256((database.rows[table][0] + "\n").encode()).hexdigest()
        assert snapshot == {"rows": 1, "quantity": "1", "value": "12.50", "sha256": expected}
    assert database.disposed
    assert database.options["isolation_level"] == "REPEATABLE READ"
    assert "default_transaction_read_only=on" in database.options["connect_args"]["options"]
    assert "timezone=UTC" in database.options["connect_args"]["options"]
    assert all(sql.startswith("SELECT ") for sql in database.queries)


@pytest.mark.parametrize("replacement", [
    '{"id": 1, "quantity": 2, "receipt_unit_index": 1, "unit_cost": 12.50}',
    '{"id": 1, "quantity": 1, "receipt_unit_index": 1, "unit_cost": 12.51}',
    '{"id": 1, "quantity": 1, "receipt_unit_index": 2, "unit_cost": 12.50}',
])
def test_changed_quantity_cost_or_historical_unit_index_changes_fingerprint(database, replacement):
    before = helper.inventory_snapshot(TARGET)
    database.rows["inventory_movements"] = [replacement]
    assert helper.inventory_snapshot(TARGET) != before


@pytest.mark.parametrize("column", [
    None,
    {"required": False, "type": "int4", "default_value": "1"},
    {"required": True, "type": "int8", "default_value": "1"},
    {"required": True, "type": "int4", "default_value": None},
    {"required": True, "type": "int4", "default_value": "2"},
])
def test_target_revision_without_correct_required_column_is_rejected(database, column):
    database.column = column
    with pytest.raises(helper.CheckError, match="coluna"):
        helper.inventory_snapshot(TARGET)
    assert database.disposed


@pytest.mark.parametrize("change", ["missing-purchase", "missing-request", "missing-check", "legacy-unique", "wrong-check"])
def test_marker_alone_does_not_accept_missing_or_incompatible_receipt_constraints(database, change):
    if change.startswith("missing-"):
        index = {"missing-purchase": 0, "missing-request": 1, "missing-check": 2}[change]
        del database.constraints[index]
    elif change == "legacy-unique":
        database.constraints.append({"kind": "u", "columns": ["purchase_order_id"], "definition": "UNIQUE (purchase_order_id)"})
    else:
        database.constraints[2]["definition"] = "CHECK ((receipt_unit_index >= 0))"
    with pytest.raises(helper.CheckError, match="restrições"):
        helper.inventory_snapshot(TARGET)
    assert database.disposed


def test_snapshot_rejects_non_readonly_connection_and_revision_drift(database):
    database.readonly = "off"
    with pytest.raises(helper.CheckError, match="somente leitura"):
        helper.inventory_snapshot(TARGET)
    database.readonly = "on"
    database.revision = BASE
    with pytest.raises(helper.CheckError, match="revisão"):
        helper.inventory_snapshot(TARGET)


def test_snapshot_rejects_missing_rows_even_when_cost_totals_match(database):
    database.counts["inventory_movements"] = 2
    with pytest.raises(helper.CheckError, match="contagem"):
        helper.inventory_snapshot(TARGET)


def test_snapshot_cli_sanitizes_driver_errors_without_exposing_database_url(monkeypatch, capsys):
    def broken(_):
        raise RuntimeError("postgresql://operator:secret@private/database")
    monkeypatch.setattr(helper, "inventory_snapshot", broken)
    assert helper.main(["inventory-snapshot", TARGET]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "secret" not in output.err and "private" not in output.err


def test_inventory_snapshot_with_real_disposable_postgresql(monkeypatch):
    url = os.environ.get("SENTICO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured disposable PostgreSQL database")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    assert os.environ.get("DATABASE_URL") == url and make_url(url).database.endswith("_test")
    monkeypatch.setattr(helper, "_load_settings", lambda: SimpleNamespace(database_url=url))
    engine = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
    try:
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            counts = {table: connection.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one()
                      for table in ("inventory_items", "inventory_movements")}
        snapshot = helper.inventory_snapshot(revision)
        assert {table: row["rows"] for table, row in snapshot.items()} == counts
        assert all(len(row["sha256"]) == 64 for row in snapshot.values())
    finally:
        engine.dispose()
