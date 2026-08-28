from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.laboratory.storage import (
    commit_laboratory_document,
    delete_laboratory_document,
    persist_laboratory_document,
    remove_laboratory_document,
    resolve_laboratory_storage_path,
)


def test_persist_laboratory_document_creates_scoped_file(tmp_path: Path) -> None:
    root = tmp_path / "laboratory"
    target = persist_laboratory_document(
        root,
        company_code="universo_eletronica",
        work_order_number="OS-30481",
        extension=".png",
        content=b"\x89PNG\r\n\x1a\n",
    )

    assert target.parent == root / "universo_eletronica" / "OS-30481"
    assert target.suffix == ".png"
    assert target.read_bytes() == b"\x89PNG\r\n\x1a\n"


def test_persist_laboratory_document_rejects_scope_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "laboratory"
    root.mkdir()

    with pytest.raises(ValueError):
        persist_laboratory_document(
            root,
            company_code="..",
            work_order_number="outside",
            extension=".pdf",
            content=b"%PDF-1.7\n",
        )


def test_resolve_laboratory_storage_path_rejects_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "laboratory"
    root.mkdir()
    outside = tmp_path / "outside.png"

    with pytest.raises(ValueError):
        resolve_laboratory_storage_path(root, outside)


def test_remove_laboratory_document_tolerates_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "laboratory"
    root.mkdir()
    remove_laboratory_document(root, root / "universo_eletronica" / "OS-1" / "missing.png")


@pytest.mark.asyncio
async def test_commit_laboratory_document_removes_file_when_commit_fails(tmp_path: Path) -> None:
    root = tmp_path / "laboratory"
    target = persist_laboratory_document(
        root,
        company_code="universo_eletronica",
        work_order_number="OS-30481",
        extension=".png",
        content=b"\x89PNG\r\n\x1a\n",
    )
    document = SimpleNamespace(id=None)
    db = SimpleNamespace(
        add=MagicMock(),
        commit=AsyncMock(side_effect=RuntimeError("commit failed")),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await commit_laboratory_document(db, document, root=root, stored_path=target)

    assert not target.exists()
    db.add.assert_called_once_with(document)
    db.rollback.assert_awaited_once()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_commit_laboratory_document_keeps_file_when_refresh_fails_after_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "laboratory"
    target = persist_laboratory_document(
        root,
        company_code="universo_eletronica",
        work_order_number="OS-30481",
        extension=".png",
        content=b"\x89PNG\r\n\x1a\n",
    )
    document = SimpleNamespace(id=2)
    db = SimpleNamespace(
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=RuntimeError("refresh failed")),
        rollback=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="refresh failed"):
        await commit_laboratory_document(db, document, root=root, stored_path=target)

    assert target.exists()
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_laboratory_document_rejects_external_path_before_db_change(
    tmp_path: Path,
) -> None:
    root = tmp_path / "laboratory"
    root.mkdir()
    document = SimpleNamespace(storage_path=str(tmp_path / "outside.png"))
    db = SimpleNamespace(delete=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())

    with pytest.raises(ValueError):
        await delete_laboratory_document(db, document, root=root)

    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_laboratory_document_tolerates_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "laboratory"
    root.mkdir()
    document = SimpleNamespace(storage_path=str(root / "universo_eletronica" / "OS-1" / "missing.png"))
    db = SimpleNamespace(delete=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())

    cleaned = await delete_laboratory_document(db, document, root=root)

    assert cleaned is True
    db.delete.assert_awaited_once_with(document)
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_laboratory_document_keeps_file_when_commit_fails(tmp_path: Path) -> None:
    root = tmp_path / "laboratory"
    target = persist_laboratory_document(
        root,
        company_code="universo_eletronica",
        work_order_number="OS-30481",
        extension=".png",
        content=b"\x89PNG\r\n\x1a\n",
    )
    document = SimpleNamespace(storage_path=str(target))
    db = SimpleNamespace(
        delete=AsyncMock(),
        commit=AsyncMock(side_effect=RuntimeError("commit failed")),
        rollback=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await delete_laboratory_document(db, document, root=root)

    assert target.exists()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_laboratory_document_reports_cleanup_failure_after_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "laboratory"
    target = persist_laboratory_document(
        root,
        company_code="universo_eletronica",
        work_order_number="OS-30481",
        extension=".png",
        content=b"\x89PNG\r\n\x1a\n",
    )
    document = SimpleNamespace(storage_path=str(target))
    db = SimpleNamespace(delete=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())

    with patch.object(Path, "unlink", side_effect=OSError("filesystem unavailable")):
        cleaned = await delete_laboratory_document(db, document, root=root)

    assert cleaned is False
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()
