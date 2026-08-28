from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.customers.storage import (
    commit_customer_document,
    delete_customer_document,
    persist_customer_document,
    remove_customer_document,
    resolve_customer_storage_path,
)


def test_persist_customer_document_creates_scoped_file(tmp_path: Path) -> None:
    target = persist_customer_document(
        tmp_path / "customers",
        customer_id=7,
        extension=".pdf",
        content=b"%PDF-1.7\n",
    )

    assert target.parent == tmp_path / "customers" / "7"
    assert target.suffix == ".pdf"
    assert target.read_bytes() == b"%PDF-1.7\n"


def test_resolve_customer_storage_path_rejects_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "customers"
    root.mkdir()
    outside = tmp_path / "outside.pdf"

    with pytest.raises(ValueError):
        resolve_customer_storage_path(root, outside)


def test_remove_customer_document_tolerates_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "customers"
    root.mkdir()
    remove_customer_document(root, root / "2" / "missing.pdf")


@pytest.mark.asyncio
async def test_commit_customer_document_removes_file_when_commit_fails(tmp_path: Path) -> None:
    root = tmp_path / "customers"
    target = persist_customer_document(
        root,
        customer_id=2,
        extension=".pdf",
        content=b"%PDF-1.7\n",
    )
    document = SimpleNamespace(id=None)
    db = SimpleNamespace(
        add=MagicMock(),
        commit=AsyncMock(side_effect=RuntimeError("commit failed")),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await commit_customer_document(
            db,
            document,
            root=root,
            stored_path=target,
        )

    assert not target.exists()
    db.add.assert_called_once_with(document)
    db.rollback.assert_awaited_once()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_customer_document_rejects_external_path_before_db_change(
    tmp_path: Path,
) -> None:
    root = tmp_path / "customers"
    root.mkdir()
    document = SimpleNamespace(storage_path=str(tmp_path / "outside.pdf"))
    db = SimpleNamespace(delete=AsyncMock(), commit=AsyncMock())

    with pytest.raises(ValueError):
        await delete_customer_document(db, document, root=root)

    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_customer_document_tolerates_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "customers"
    root.mkdir()
    document = SimpleNamespace(storage_path=str(root / "2" / "missing.pdf"))
    db = SimpleNamespace(delete=AsyncMock(), commit=AsyncMock())

    cleaned = await delete_customer_document(db, document, root=root)

    assert cleaned is True
    db.delete.assert_awaited_once_with(document)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_commit_customer_document_keeps_file_when_refresh_fails_after_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "customers"
    target = persist_customer_document(
        root,
        customer_id=3,
        extension=".pdf",
        content=b"%PDF-1.7\n",
    )
    document = SimpleNamespace(id=10)
    db = SimpleNamespace(
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=RuntimeError("refresh failed")),
        rollback=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="refresh failed"):
        await commit_customer_document(
            db,
            document,
            root=root,
            stored_path=target,
        )

    assert target.exists()
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()
