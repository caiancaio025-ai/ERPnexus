import pytest

from app.core.file_validation import InvalidUpload, validate_upload


@pytest.mark.parametrize(
    ("content", "filename", "reported_mime", "expected_mime", "expected_extension"),
    [
        (b"%PDF-1.7\nbody", "document.pdf", "application/pdf", "application/pdf", ".pdf"),
        (b"\xff\xd8\xff\xe0JPEG", "photo.jpeg", "image/jpeg", "image/jpeg", ".jpg"),
        (b"\x89PNG\r\n\x1a\nPNG", "image.png", "image/png", "image/png", ".png"),
        (b"RIFF\x04\x00\x00\x00WEBPVP8 ", "image.webp", "image/webp", "image/webp", ".webp"),
    ],
)
def test_validate_upload_accepts_supported_signatures(
    content: bytes,
    filename: str,
    reported_mime: str,
    expected_mime: str,
    expected_extension: str,
) -> None:
    detected = validate_upload(content, filename, reported_mime)
    assert detected.mime_type == expected_mime
    assert detected.extension == expected_extension


def test_validate_upload_rejects_fake_pdf() -> None:
    with pytest.raises(InvalidUpload, match="Assinatura"):
        validate_upload(b"not-a-pdf", "invoice.pdf", "application/pdf")


def test_validate_upload_rejects_extension_mismatch() -> None:
    with pytest.raises(InvalidUpload, match="extensão"):
        validate_upload(b"%PDF-1.7\n", "invoice.jpg", "application/pdf")


def test_validate_upload_rejects_mime_mismatch() -> None:
    with pytest.raises(InvalidUpload, match="MIME"):
        validate_upload(b"%PDF-1.7\n", "invoice.pdf", "image/png")


def test_validate_upload_accepts_generic_browser_mime() -> None:
    detected = validate_upload(b"%PDF-1.7\n", "invoice.pdf", "application/octet-stream")
    assert detected.mime_type == "application/pdf"
