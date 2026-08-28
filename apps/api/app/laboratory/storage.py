from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


def resolve_laboratory_storage_path(root: Path, stored_path: str | Path) -> Path:
    """Resolve a laboratory path and reject locations outside the configured root."""
    root_resolved = root.resolve(strict=False)
    path = Path(stored_path)
    if not path.is_absolute():
        path = root_resolved / path
    path_resolved = path.resolve(strict=False)
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Caminho de documento fora do storage do laboratório.") from exc
    return path_resolved


def persist_laboratory_document(
    root: Path,
    *,
    company_code: str,
    work_order_number: str,
    extension: str,
    content: bytes,
) -> Path:
    """Persist a document inside a company/work-order scoped directory."""
    directory = resolve_laboratory_storage_path(
        root,
        Path(company_code) / work_order_number,
    )
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid4().hex}{extension}"
    target.write_bytes(content)
    return target


def remove_laboratory_document(root: Path, stored_path: str | Path) -> None:
    resolve_laboratory_storage_path(root, stored_path).unlink(missing_ok=True)


async def commit_laboratory_document(
    db: Any,
    document: Any,
    *,
    root: Path,
    stored_path: str | Path,
) -> None:
    """Commit the DB row and remove the just-written file if commit fails."""
    db.add(document)
    try:
        await db.commit()
    except Exception:
        try:
            remove_laboratory_document(root, stored_path)
        except OSError:
            logger.exception("Falha ao remover documento do laboratório após erro no commit.")
        try:
            await db.rollback()
        except Exception:
            logger.exception("Falha no rollback após erro ao salvar documento do laboratório.")
        raise

    # Commit already succeeded. If refresh fails, preserve the file because the
    # database row is durable and references it.
    await db.refresh(document)


async def delete_laboratory_document(
    db: Any,
    document: Any,
    *,
    root: Path,
) -> bool:
    """Delete the DB row first, then clean the file without creating a broken DB reference.

    Returns False if the DB deletion was committed but physical cleanup failed. The
    remaining file is then an orphan suitable for a later storage reconciliation,
    which is safer than keeping a live DB row that points to a missing file.
    """
    path = resolve_laboratory_storage_path(root, document.storage_path)
    await db.delete(document)
    try:
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            logger.exception("Falha no rollback após erro ao excluir documento do laboratório.")
        raise

    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Falha ao remover arquivo físico de documento do laboratório já excluído.")
        return False
    return True
