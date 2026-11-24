"""Regressoes das evidencias de envio e retorno por peca da V46.

Ensaios isolados de transacao: nao substituem homologacao PostgreSQL/Docker.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.schema import MetaData, Table, Column
from sqlalchemy import Integer, String
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations

from app.laboratory.schemas import PaintingPhotoOutput


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def router_module():
    """Importa a rota para ensaios unitarios sem inicializar Postgres local.

    O Docker/PSYCOPG sao verificados apenas na homologacao integrada.
    """
    import sys
    import types
    import importlib

    fake_db = types.ModuleType("app.core.db")

    async def fake_get_db():
        yield None

    fake_db.get_db = fake_get_db
    fake_db.session_factory = lambda: None
    fake_db.database_is_ready = lambda: None
    previous = sys.modules.get("app.core.db")
    sys.modules["app.core.db"] = fake_db
    try:
        yield importlib.import_module("app.laboratory.router")
    finally:
        if previous is None:
            sys.modules.pop("app.core.db", None)
        else:
            sys.modules["app.core.db"] = previous
MIGRATION = ROOT / "migrations" / "versions" / "20261123_02_mechanical_painting_item_photos.py"
FRONTEND = ROOT.parent / "web" / "src" / "features" / "laboratory" / "components" / "MechanicsPanel.tsx"


def test_migration_preserves_legacy_photos_and_adds_optional_item_fk():
    import importlib.util

    source = MIGRATION.read_text()
    assert 'down_revision = "20261123_01"' in source
    spec = importlib.util.spec_from_file_location("migration_v46", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    Table("laboratory_mechanical_painting_items", metadata, Column("id", Integer, primary_key=True))
    Table("laboratory_mechanical_painting_photos", metadata,
          Column("id", Integer, primary_key=True), Column("phase", String(20)),
          Column("document_id", Integer))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO laboratory_mechanical_painting_photos(id,phase,document_id) VALUES (1,'outbound',50)"))
        operations = Operations(MigrationContext.configure(connection))
        previous_op = module.op
        module.op = operations
        try:
            module.upgrade()
        finally:
            module.op = previous_op
        legacy = connection.execute(text("SELECT id,item_id,phase FROM laboratory_mechanical_painting_photos WHERE id=1")).one()
        assert legacy == (1, None, "outbound")
        connection.execute(text("INSERT INTO laboratory_mechanical_painting_photos(id,phase,document_id,item_id) VALUES (2,'return',51,9)"))
        assert connection.execute(text("SELECT item_id FROM laboratory_mechanical_painting_photos WHERE id=2")).scalar_one() == 9
        assert "item_id" in {col["name"] for col in inspect(connection).get_columns("laboratory_mechanical_painting_photos")}
    engine.dispose()


def test_schema_accepts_new_and_historical_photos():
    base = {
        "id": 4,
        "document_id": 28,
        "phase": "return",
        "position": 1,
        "caption": None,
        "original_name": "retorno.jpg",
        "mime_type": "image/jpeg",
        "created_at": datetime.now(UTC),
    }
    assert PaintingPhotoOutput(**base).item_id is None
    assert PaintingPhotoOutput(**base, item_id=23).item_id == 23


class FakeSession:
    def __init__(self, *, item_dispatch=7, fail_commit=False):
        self.item_dispatch = item_dispatch
        self.fail_commit = fail_commit
        self.objects = []
        self.commits = 0
        self.rollbacks = 0
        self.photo = None

    async def get(self, model, pk):
        from app.laboratory.models import LaboratoryMechanicalPaintingItem
        if model is LaboratoryMechanicalPaintingItem:
            return SimpleNamespace(dispatch_id=self.item_dispatch) if pk == 19 else None
        return None

    def add(self, obj):
        self.objects.append(obj)
        if obj.__class__.__name__ == "LaboratoryMechanicalPaintingPhoto":
            self.photo = obj

    async def flush(self):
        for obj in self.objects:
            if obj.__class__.__name__ == "LaboratoryDocument":
                obj.id = 30

    async def scalar(self, statement):
        return 0

    async def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("falha simulada no banco")
        self.photo.id = 88
        self.photo.created_at = datetime.now(UTC)

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        pass


def run(coro):
    return asyncio.run(coro)


def test_upload_item_photo_commits_document_and_link_together_and_returns_ids(router_module, monkeypatch, tmp_path):
    file_path = tmp_path / "retorno.jpg"

    async def fake_stream(file, *, directory, max_size):
        file_path.write_bytes(b"JPEG")
        return SimpleNamespace(path=file_path, mime_type="image/jpeg", size_bytes=4, checksum_sha256="a" * 64)

    async def dispatch(db, dispatch_id):
        return SimpleNamespace(id=7, status="sent", work_order_id=5)

    async def order(db, order_id):
        return SimpleNamespace(id=5, company_code="PE", number="OS-31455")

    monkeypatch.setattr(router_module, "persist_streamed_upload", fake_stream)
    monkeypatch.setattr(router_module, "_painting_dispatch_or_404", dispatch)
    monkeypatch.setattr(router_module, "_work_order_or_404", order)
    monkeypatch.setattr(router_module, "UPLOAD_ROOT", tmp_path)

    session = FakeSession()
    photo = run(router_module.upload_mechanics_painting_photo(
        dispatch_id=7,
        item_id=19,
        phase="return",
        file=SimpleNamespace(filename="retorno.jpg"),
        user=SimpleNamespace(id=2),
        db=session,
    ))
    assert file_path.is_file()
    assert session.commits == 1
    assert session.rollbacks == 0
    assert photo.item_id == 19
    assert photo.phase == "return"
    assert photo.document_id == 30
    assert photo.id == 88


def test_upload_rollback_does_not_leave_orphan_file(router_module, monkeypatch, tmp_path):
    file_path = tmp_path / "envio.jpg"

    async def fake_stream(file, *, directory, max_size):
        file_path.write_bytes(b"JPEG")
        return SimpleNamespace(path=file_path, mime_type="image/jpeg", size_bytes=4, checksum_sha256="b" * 64)

    async def dispatch(db, dispatch_id):
        return SimpleNamespace(id=7, status="draft", work_order_id=5)

    async def order(db, order_id):
        return SimpleNamespace(id=5, company_code="PE", number="OS-31455")

    monkeypatch.setattr(router_module, "persist_streamed_upload", fake_stream)
    monkeypatch.setattr(router_module, "_painting_dispatch_or_404", dispatch)
    monkeypatch.setattr(router_module, "_work_order_or_404", order)
    monkeypatch.setattr(router_module, "UPLOAD_ROOT", tmp_path)

    session = FakeSession(fail_commit=True)
    with pytest.raises(RuntimeError, match="falha simulada"):
        run(router_module.upload_mechanics_painting_photo(
            dispatch_id=7, item_id=19, phase="outbound",
            file=SimpleNamespace(filename="envio.jpg"),
            user=SimpleNamespace(id=2), db=session,
        ))
    assert not file_path.exists()
    assert session.rollbacks == 1
    assert session.commits == 1


def test_rejects_item_from_another_dispatch_before_file_storage(router_module, monkeypatch):
    async def dispatch(db, dispatch_id):
        return SimpleNamespace(id=7, status="draft", work_order_id=5)

    async def order(db, order_id):
        return SimpleNamespace(id=5, company_code="PE", number="OS-31455")

    monkeypatch.setattr(router_module, "_painting_dispatch_or_404", dispatch)
    monkeypatch.setattr(router_module, "_work_order_or_404", order)
    session = FakeSession(item_dispatch=200)
    with pytest.raises(HTTPException) as exc:
        run(router_module.upload_mechanics_painting_photo(
            dispatch_id=7, item_id=19, phase="outbound",
            file=SimpleNamespace(filename="envio.jpg"),
            user=SimpleNamespace(id=2), db=session,
        ))
    assert exc.value.status_code == 404
    assert session.commits == 0


def test_returned_items_still_render_both_phases_and_confirm_persistence():
    ui = FRONTEND.read_text()
    assert 'photo.item_id === item.id' in ui
    assert 'title="Evidência da saída"' in ui
    assert 'title="Foto do retorno (opcional)"' in ui
    assert 'row.status !== "draft" && <PhotoBlock' in ui
    assert 'disabled={row.status !== "sent"}' in ui
    assert 'recordedIds.has(photo.id)' in ui
    assert 'item_id=${itemId}' in ui
