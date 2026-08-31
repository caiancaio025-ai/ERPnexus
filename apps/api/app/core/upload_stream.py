from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from app.core.file_validation import DetectedFileType, validate_upload

DEFAULT_UPLOAD_CHUNK_SIZE = 1024 * 1024
_MIN_SIGNATURE_CHUNK_SIZE = 16


class UploadReader(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


class UploadTooLarge(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StreamedUpload:
    path: Path
    mime_type: str
    extension: str
    size_bytes: int
    checksum_sha256: str


def _write_chunk(handle: BinaryIO, chunk: bytes) -> None:
    handle.write(chunk)


def _flush_and_sync(handle: BinaryIO) -> None:
    handle.flush()
    os.fsync(handle.fileno())


async def persist_streamed_upload(
    file: UploadReader,
    *,
    directory: Path,
    filename_prefix: str = "",
    max_size: int,
    chunk_size: int = DEFAULT_UPLOAD_CHUNK_SIZE,
) -> StreamedUpload:
    """Persist an upload with bounded memory and atomic publication.

    The upload is validated from its binary signature before filesystem creation,
    then copied in bounded chunks into a temporary file. The temporary file is
    atomically renamed to its final extension only after the entire stream fits
    within ``max_size`` and has been flushed successfully.
    """
    if max_size <= 0:
        raise ValueError("max_size deve ser maior que zero.")
    if chunk_size < _MIN_SIGNATURE_CHUNK_SIZE:
        raise ValueError(f"chunk_size deve ser de pelo menos {_MIN_SIGNATURE_CHUNK_SIZE} bytes.")

    first_chunk = await file.read(chunk_size)
    if len(first_chunk) > max_size:
        raise UploadTooLarge("Arquivo excede o limite permitido.")

    detected: DetectedFileType = validate_upload(
        first_chunk,
        file.filename,
        file.content_type,
    )

    token = uuid4().hex
    temporary = directory / f".{token}.upload"
    target = directory / f"{filename_prefix}{token}{detected.extension}"
    total = 0
    digest = sha256()
    handle: BinaryIO | None = None

    try:
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
        handle = await asyncio.to_thread(temporary.open, "xb")

        chunk = first_chunk
        while chunk:
            total += len(chunk)
            if total > max_size:
                raise UploadTooLarge("Arquivo excede o limite permitido.")
            digest.update(chunk)
            await asyncio.to_thread(_write_chunk, handle, chunk)
            chunk = await file.read(chunk_size)

        await asyncio.to_thread(_flush_and_sync, handle)
        await asyncio.to_thread(handle.close)
        handle = None
        await asyncio.to_thread(os.replace, temporary, target)
    except Exception:
        if handle is not None:
            try:
                await asyncio.to_thread(handle.close)
            except OSError:
                pass
        try:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
        except OSError:
            pass
        raise

    return StreamedUpload(
        path=target,
        mime_type=detected.mime_type,
        extension=detected.extension,
        size_bytes=total,
        checksum_sha256=digest.hexdigest(),
    )
