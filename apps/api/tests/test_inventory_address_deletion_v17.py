"""Exclusão física de endereços sem destruir o histórico de localização."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.inventory.models import InventoryContainer, InventoryItem, InventoryLocationHistory, InventorySlot
from app.inventory.schemas import ContainerUpdate


def load_actual_router_functions():
    """Usa o código real dos handlers sem inicializar o banco PostgreSQL."""
    source = (Path(__file__).parents[1] / "app/inventory/router.py").read_text()
    tree = ast.parse(source)
    names = {"delete_container", "edit_container", "location_history"}
    nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    for node in nodes:
        node.decorator_list = []
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    namespace = {
        "select": select, "or_": or_, "IntegrityError": IntegrityError,
        "HTTPException": HTTPException, "InventoryContainer": InventoryContainer,
        "InventoryItem": InventoryItem, "InventorySlot": InventorySlot,
        "InventoryLocationHistory": InventoryLocationHistory,
        "DB": None, "Depends": lambda _: None, "require_module": lambda _: None,
        "_model": lambda obj: {c.name: getattr(obj, c.name) for c in obj.__table__.columns},
    }
    exec(compile(module, "router.py", "exec"), namespace)
    return namespace["delete_container"], namespace["edit_container"], namespace["location_history"]


delete_container, edit_container, location_history = load_actual_router_functions()


def session_fixture(*, active=True, history=None):
    container = InventoryContainer(id=8, area_id=1, type_id=1, code="A", name="Estante A", rows=1,
                                   columns=5, layout_row=1, layout_column=1, layout_span=3, is_active=active)
    slots = [InventorySlot(id=10, container_id=8, code="A1", name="Posição A1", row=1, column=1, is_active=active),
             InventorySlot(id=11, container_id=8, code="A2", name="Posição A2", row=1, column=2, is_active=active)]
    db = MagicMock()
    db.get = AsyncMock(return_value=container)
    results = []
    for rows in (slots, history or []):
        scalars = MagicMock()
        scalars.all.return_value = rows
        results.append(scalars)
    db.scalars = AsyncMock(side_effect=results)
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.delete = AsyncMock()
    return db, container, slots


@pytest.mark.asyncio
async def test_used_address_is_really_deleted_with_historical_snapshots():
    event1 = InventoryLocationHistory(id=100, item_id=1, previous_slot_id=10, new_slot_id=11,
                                      moved_by=1, previous_slot_code=None, new_slot_code=None)
    event2 = InventoryLocationHistory(id=101, item_id=1, previous_slot_id=11, new_slot_id=None,
                                      moved_by=1, previous_slot_code="A2", new_slot_code=None)
    db, container, slots = session_fixture(history=[event1, event2])
    result = await delete_container(8, db=db, user=SimpleNamespace())
    assert result["outcome"] == "deleted"
    assert event1.previous_slot_id is None and event1.previous_slot_code == "A1"
    assert event1.new_slot_id is None and event1.new_slot_code == "A2"
    assert event2.previous_slot_id is None and event2.previous_slot_code == "A2"
    assert event2.new_slot_id is None
    assert db.delete.await_count == 3
    assert db.flush.await_count == 2
    db.commit.assert_awaited_once()
    assert container.is_active
    assert all(s.is_active for s in slots)


@pytest.mark.asyncio
async def test_unused_address_is_physically_deleted():
    db, _, _ = session_fixture()
    result = await delete_container(8, db=db, user=SimpleNamespace())
    assert result["outcome"] == "deleted"
    assert db.delete.await_count == 3
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_archived_address_can_be_removed_definitively():
    db, _, _ = session_fixture(active=False)
    result = await delete_container(8, db=db, user=SimpleNamespace())
    assert result["outcome"] == "deleted"
    assert db.delete.await_count == 3


@pytest.mark.asyncio
async def test_fk_failure_does_not_archive_or_claim_success():
    db, container, slots = session_fixture()
    db.commit.side_effect = IntegrityError("DELETE inventory_slots", {}, ValueError("fk"))
    with pytest.raises(HTTPException) as error:
        await delete_container(8, db=db, user=SimpleNamespace())
    assert error.value.status_code == 409
    assert "Não foi possível excluir definitivamente" in error.value.detail
    assert container.is_active and all(slot.is_active for slot in slots)
    db.rollback.assert_awaited_once()
    assert db.commit.await_count == 1


@pytest.mark.asyncio
async def test_current_items_block_physical_removal():
    db, _, _ = session_fixture()
    db.scalar.side_effect = [None, 22]
    with pytest.raises(HTTPException) as error:
        await delete_container(8, db=db, user=SimpleNamespace())
    assert error.value.status_code == 409
    assert "itens" in error.value.detail
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_child_locations_block_physical_removal():
    db, _, _ = session_fixture()
    db.scalar.side_effect = [99]
    with pytest.raises(HTTPException) as error:
        await delete_container(8, db=db, user=SimpleNamespace())
    assert error.value.status_code == 409
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_historical_location_display_works_after_deletion():
    event = InventoryLocationHistory(id=100, item_id=1, previous_slot_id=None,
                                     new_slot_id=None, previous_slot_code="A1",
                                     new_slot_code="A2", moved_by=1)
    db = MagicMock()
    record_query = MagicMock()
    record_query.all.return_value = [event]
    slot_query = MagicMock()
    slot_query.all.return_value = []
    db.scalars = AsyncMock(side_effect=[record_query, slot_query])
    result = await location_history(1, db=db)
    assert result[0]["from"] == "A1"
    assert result[0]["to"] == "A2"


@pytest.mark.asyncio
async def test_restore_reactivates_positions_and_container():
    # Fluxo de restauração legado continua existindo para endereços arquivados anteriormente.
    db, container, slots = session_fixture(active=False)
    payload = ContainerUpdate(name="Estante A", layout_row=1, layout_column=1, layout_span=3, is_active=True)
    result = await edit_container(8, payload, db=db, user=SimpleNamespace())
    assert result["is_active"] is True
    assert all(slot.is_active for slot in slots)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_edit_cannot_archive_address_with_items():
    db, container, _ = session_fixture()
    db.scalar.side_effect = [None, 19]
    payload = ContainerUpdate(name="Estante A", layout_row=1, layout_column=1, layout_span=3, is_active=False)
    with pytest.raises(HTTPException) as error:
        await edit_container(8, payload, db=db, user=SimpleNamespace())
    assert error.value.status_code == 409
    assert container.is_active
    db.commit.assert_not_awaited()


def test_snapshot_migration_has_existing_history_backfill():
    migration = Path(__file__).parents[1] / "migrations/versions/20261112_01_inventory_location_history_snapshots.py"
    text = migration.read_text()
    assert 'down_revision: str | None = "20261028_01"' in text
    assert 'previous_slot_code = s.code' in text
    assert 'new_slot_code = s.code' in text
    assert 'op.add_column("inventory_location_history"' in text

@pytest.mark.asyncio
async def test_database_restrict_fk_real_delete_with_history():
    """SQLite com FKs ON: confirma operação física e preservação do evento."""
    from decimal import Decimal
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session
    from app.auth.models import User
    from app.laboratory.models import LaboratoryWorkOrder  # necessário para resolver FKs do metadata
    from app.inventory.models import InventoryArea, InventoryLocationType, InventoryComponentSubtype, InventoryComponentFormat

    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    for model in [User, InventoryArea, InventoryLocationType, InventoryComponentSubtype,
                  InventoryComponentFormat, InventoryContainer, InventorySlot,
                  InventoryItem, InventoryLocationHistory]:
        model.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(User(id=1, name="Teste", email="teste@local", username="testador",
                         password_hash="hash", role="gestao", modules=["estoque"]))
        session.add(InventoryArea(id=1, code="ALM", name="Almoxarifado", is_active=True))
        session.add(InventoryLocationType(id=1, code="estante", name="Estante", is_active=True))
        session.flush()
        session.add(InventoryContainer(id=8, area_id=1, type_id=1, code="A", name="Estante A",
                                       rows=1, columns=5, is_active=False))
        session.flush()
        session.add(InventorySlot(id=10, container_id=8, code="A1", name="A1",
                                  row=1, column=1, is_active=False))
        session.flush()
        session.add(InventoryItem(id=15, stock_code="0015", company_code="teste",
                                  name="Componente", category="componentes", mode="bulk",
                                  quantity=0, unit_cost=Decimal("1"), unit="UN", slot_id=None,
                                  created_by=1, is_active=True))
        session.flush()
        session.add(InventoryLocationHistory(id=20, item_id=15, previous_slot_id=10,
                                             new_slot_id=None, moved_by=1))
        session.commit()

        class SessionAdapter:
            async def get(self, *args, **kwargs): return session.get(*args, **kwargs)
            async def scalar(self, *args, **kwargs): return session.scalar(*args, **kwargs)
            async def scalars(self, *args, **kwargs): return session.scalars(*args, **kwargs)
            async def flush(self, *args, **kwargs): return session.flush(*args, **kwargs)
            async def delete(self, *args, **kwargs): return session.delete(*args, **kwargs)
            async def commit(self, *args, **kwargs): return session.commit(*args, **kwargs)
            async def rollback(self, *args, **kwargs): return session.rollback(*args, **kwargs)

        result = await delete_container(8, db=SessionAdapter(), user=SimpleNamespace())
        assert result["outcome"] == "deleted"
        session.expire_all()
        assert session.get(InventoryContainer, 8) is None
        assert session.get(InventorySlot, 10) is None
        history = session.get(InventoryLocationHistory, 20)
        assert history.previous_slot_id is None
        assert history.previous_slot_code == "A1"
        assert session.get(InventoryItem, 15) is not None
    engine.dispose()
