from pathlib import Path

import pytest


ROUTERS = (
    Path("app/customers/router.py"),
    Path("app/finance/router.py"),
    Path("app/laboratory/router.py"),
    Path("app/purchasing/router.py"),
)


@pytest.mark.parametrize("router_path", ROUTERS)
def test_upload_routes_do_not_buffer_entire_file(router_path: Path) -> None:
    source = router_path.read_text(encoding="utf-8")

    assert "await file.read(MAX_UPLOAD_SIZE + 1)" not in source


@pytest.mark.parametrize("router_path", ROUTERS)
def test_upload_routes_use_shared_streaming_writer(router_path: Path) -> None:
    source = router_path.read_text(encoding="utf-8")

    assert "persist_streamed_upload" in source
    assert "UploadTooLarge" in source
