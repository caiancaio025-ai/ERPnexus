"""Regressão independente: exclusão de foto do Estoque na V45.

O carregamento por AST permite testar a função sem exigir PostgreSQL de produção.
"""
import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "apps/api/app/inventory/router.py"
EDITOR = ROOT / "apps/web/src/features/inventory/InventoryDashboard.tsx"
CSS = ROOT / "apps/web/src/features/inventory/inventory.css"


class InventoryItem: ...
class InventoryPhoto: ...


def load_delete_photo(storage: Path):
    source = ROUTER.read_text()
    tree = ast.parse(source)
    method = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "delete_photo")
    # Confirma a existência do endpoint de exclusão, não só de uma função helper.
    assert any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "delete"
               for d in method.decorator_list)
    method.decorator_list = []
    namespace = {
        "DB": None, "AsyncSession": object, "User": object,
        "Depends": lambda dependency: None,
        "require_module": lambda module: ("permissao", module),
        "InventoryItem": InventoryItem, "InventoryPhoto": InventoryPhoto,
        "STORAGE": storage, "HTTPException": HTTPException, "Response": Response,
        "Path": Path, "logging": logging,
    }
    compiled = compile(ast.Module(body=[method], type_ignores=[]), str(ROUTER), "exec")
    exec(compiled, namespace)
    return namespace["delete_photo"]


class DbFake:
    def __init__(self, item, photo, fail_commit=False):
        self.item, self.photo, self.fail_commit = item, photo, fail_commit
        self.deleted = []
        self.commits = 0

    async def get(self, model, _id):
        if model is InventoryItem:
            return self.item
        if model is InventoryPhoto:
            return self.photo
        raise AssertionError(model)

    async def delete(self, row):
        self.deleted.append(row)

    async def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("Falha de banco simulada")


def test_delete_only_chosen_photo_and_preserve_other(tmp_path):
    folder = tmp_path / "10"
    folder.mkdir()
    selected_file = folder / "foto-errada.jpg"
    another_file = folder / "foto-correta.jpg"
    selected_file.write_bytes(b"foto errada")
    another_file.write_bytes(b"foto correta")
    item = SimpleNamespace(id=10)
    photo = SimpleNamespace(id=22, item_id=10, filename=selected_file.name)
    db = DbFake(item, photo)
    result = asyncio.run(load_delete_photo(tmp_path)(10, 22, db=db, user=object()))
    assert result.status_code == 204
    assert db.commits == 1 and db.deleted == [photo]
    assert not selected_file.exists()
    assert another_file.read_bytes() == b"foto correta"


def test_cannot_delete_photo_from_another_item(tmp_path):
    folder = tmp_path / "10"
    folder.mkdir()
    path = folder / "foto.jpg"
    path.write_bytes(b"foto")
    db = DbFake(SimpleNamespace(id=10), SimpleNamespace(id=32, item_id=11, filename="foto.jpg"))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(load_delete_photo(tmp_path)(10, 32, db=db, user=object()))
    assert raised.value.status_code == 404
    assert not db.deleted and not db.commits and path.exists()


def test_missing_photo_does_not_change_item(tmp_path):
    db = DbFake(SimpleNamespace(id=10), None)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(load_delete_photo(tmp_path)(10, 404, db=db, user=object()))
    assert raised.value.status_code == 404
    assert db.commits == 0


def test_missing_item_returns_404(tmp_path):
    db = DbFake(None, SimpleNamespace(item_id=10, filename="x.jpg"))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(load_delete_photo(tmp_path)(10, 5, db=db, user=object()))
    assert raised.value.status_code == 404
    assert db.commits == 0


def test_commit_failure_does_not_delete_file(tmp_path):
    folder = tmp_path / "10"
    folder.mkdir()
    photo_file = folder / "foto.jpg"
    photo_file.write_bytes(b"original")
    db = DbFake(SimpleNamespace(id=10), SimpleNamespace(id=5, item_id=10, filename="foto.jpg"), fail_commit=True)
    with pytest.raises(RuntimeError, match="Falha de banco"):
        asyncio.run(load_delete_photo(tmp_path)(10, 5, db=db, user=object()))
    assert photo_file.read_bytes() == b"original"


def test_frontend_can_remove_uploaded_and_pending_photos():
    src = EDITOR.read_text()
    assert 'apiClient.delete<void>(`/inventory/items/${item.id}/photos/${photoId}`)' in src
    assert 'className="inv-photo-remove"' in src
    assert 'className="inv-remove-pending-photo"' in src
    assert 'window.confirm("Remover esta foto do item?' in src
    assert 'setSelected(previous => previous?.id === item.id' in src
    assert 'setPhotoError(errorText(cause))' in src
    assert 'role="alert"' in src
    assert 'html[data-sentico-theme="claro"]' in CSS.read_text()
