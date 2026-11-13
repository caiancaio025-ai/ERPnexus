from pathlib import Path

import pytest

from app.finance.storage import persist_attachment


def test_persist_attachment_creates_company_directory_and_file(tmp_path: Path) -> None:
    content = b"%PDF-1.7\nNEXUS TEST"
    target = persist_attachment(
        tmp_path / "finance",
        company_code="universo_eletronica",
        entry_id=42,
        extension=".pdf",
        content=content,
    )

    assert target.parent == tmp_path / "finance" / "universo_eletronica"
    assert target.name.startswith("42-")
    assert target.suffix == ".pdf"
    assert target.read_bytes() == content


def test_persist_attachment_propagates_storage_failure(tmp_path: Path) -> None:
    blocked_root = tmp_path / "blocked"
    blocked_root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(OSError):
        persist_attachment(
            blocked_root,
            company_code="universo_eletronica",
            entry_id=43,
            extension=".pdf",
            content=b"%PDF-1.7\n",
        )
