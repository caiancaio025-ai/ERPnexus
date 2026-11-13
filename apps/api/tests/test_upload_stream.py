from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from app.core.file_validation import InvalidUpload
from app.core.upload_stream import UploadTooLarge, persist_streamed_upload


class FakeUpload:
    def __init__(
        self,
        content: bytes,
        *,
        filename: str = "document.pdf",
        content_type: str = "application/pdf",
        fail_after_reads: int | None = None,
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._offset = 0
        self._reads = 0
        self._fail_after_reads = fail_after_reads
        self.requested_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self._reads += 1
        self.requested_sizes.append(size)
        if self._fail_after_reads is not None and self._reads > self._fail_after_reads:
            raise OSError("upload stream unavailable")
        if self._offset >= len(self._content):
            return b""
        end = len(self._content) if size < 0 else self._offset + size
        chunk = self._content[self._offset:end]
        self._offset += len(chunk)
        return chunk


@pytest.mark.asyncio
async def test_persist_streamed_upload_uses_bounded_chunks_and_checksum(tmp_path: Path) -> None:
    content = b"%PDF-1.7\n" + (b"NEXUS" * 40)
    upload = FakeUpload(content)

    result = await persist_streamed_upload(
        upload,
        directory=tmp_path / "uploads",
        filename_prefix="42-",
        max_size=4096,
        chunk_size=32,
    )

    assert result.path.parent == tmp_path / "uploads"
    assert result.path.name.startswith("42-")
    assert result.path.suffix == ".pdf"
    assert result.path.read_bytes() == content
    assert result.mime_type == "application/pdf"
    assert result.size_bytes == len(content)
    assert result.checksum_sha256 == sha256(content).hexdigest()
    assert upload.requested_sizes
    assert max(upload.requested_sizes) == 32
    assert not list(result.path.parent.glob("*.upload"))
    assert not list(result.path.parent.glob(".*.upload"))


@pytest.mark.asyncio
async def test_persist_streamed_upload_rejects_oversize_and_removes_temporary_file(
    tmp_path: Path,
) -> None:
    upload = FakeUpload(b"%PDF-1.7\n" + (b"x" * 80))
    directory = tmp_path / "uploads"

    with pytest.raises(UploadTooLarge):
        await persist_streamed_upload(
            upload,
            directory=directory,
            max_size=40,
            chunk_size=32,
        )

    assert directory.exists()
    assert list(directory.iterdir()) == []


@pytest.mark.asyncio
async def test_persist_streamed_upload_rejects_invalid_signature_before_storage(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "uploads"
    upload = FakeUpload(b"not-a-supported-file", filename="fake.pdf")

    with pytest.raises(InvalidUpload):
        await persist_streamed_upload(
            upload,
            directory=directory,
            max_size=4096,
            chunk_size=32,
        )

    assert not directory.exists()


@pytest.mark.asyncio
async def test_persist_streamed_upload_cleans_temporary_file_when_read_fails(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "uploads"
    upload = FakeUpload(
        b"%PDF-1.7\n" + (b"x" * 80),
        fail_after_reads=1,
    )

    with pytest.raises(OSError, match="upload stream unavailable"):
        await persist_streamed_upload(
            upload,
            directory=directory,
            max_size=4096,
            chunk_size=32,
        )

    assert directory.exists()
    assert list(directory.iterdir()) == []


@pytest.mark.asyncio
async def test_persist_streamed_upload_preserves_extension_and_mime_consistency(
    tmp_path: Path,
) -> None:
    upload = FakeUpload(
        b"\x89PNG\r\n\x1a\n" + (b"x" * 32),
        filename="image.jpg",
        content_type="image/jpeg",
    )

    with pytest.raises(InvalidUpload, match="extensão"):
        await persist_streamed_upload(
            upload,
            directory=tmp_path / "uploads",
            max_size=4096,
            chunk_size=32,
        )
