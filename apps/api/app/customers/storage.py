from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


def persist_customer_document(
    root: Path,
    *,
    customer_id: int,
    extension: str,
    content: bytes,
) -> Path:
    """Persist a customer document under its customer-scoped directory."""
    directory = root / str(customer_id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid4().hex}{extension}"
    target.write_bytes(content)
    return target


def resolve_customer_storage_path(root: Path, stored_path: str | Path) -> Path:
    """Resolve a stored path and reject paths outside the customer storage root."""
    root_resolved = root.resolve(strict=False)
    path = Path(stored_path)
    if not path.is_absolute():
        path = root_resolved / path
    path_resolved = path.resolve(strict=False)
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Caminho de documento fora do storage de clientes.") from exc
    return path_resolved


def remove_customer_document(root: Path, stored_path: str | Path) -> None:
    resolve_customer_storage_path(root, stored_path).unlink(missing_ok=True)


async def commit_customer_document(
    db: Any,
    document: Any,
    *,
    root: Path,
    stored_path: str | Path,
) -> None:
    """Commit the document row and compensate the filesystem if the DB commit fails."""
    db.add(document)
    try:
        await db.commit()
    except Exception:
        try:
            remove_customer_document(root, stored_path)
        except OSError:
            logger.exception("Falha ao remover documento de cliente após erro no commit.")
        try:
            await db.rollback()
        except Exception:
            logger.exception("Falha no rollback após erro ao salvar documento de cliente.")
        raise
    await db.refresh(document)


async def delete_customer_document(
    db: Any,
    document: Any,
    *,
    root: Path,
) -> bool:
    """Delete the DB row first; then remove the file without risking a broken DB reference.

    Returns False when the database deletion is committed but physical cleanup fails. In
    that case the remaining file is an orphan, which is safer than a live database row
    pointing to a missing file and can be removed by a storage audit later.
    """
    path = resolve_customer_storage_path(root, document.storage_path)
    await db.delete(document)
    await db.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Falha ao remover arquivo físico de documento de cliente já excluído.")
        return False
    return True
