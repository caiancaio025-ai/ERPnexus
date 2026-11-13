from app.core.file_validation import validate_upload


def test_pdf_upload_accepts_standard_pdf_mime() -> None:
    detected = validate_upload(b"%PDF-1.7\nNEXUS", "comprovante.pdf", "application/pdf")
    assert detected.mime_type == "application/pdf"
    assert detected.extension == ".pdf"


def test_pdf_upload_accepts_common_windows_pdf_alias() -> None:
    detected = validate_upload(b"%PDF-1.7\nNEXUS", "comprovante.pdf", "application/x-pdf")
    assert detected.mime_type == "application/pdf"


def test_finance_upload_contract_accepts_pdf_and_images() -> None:
    samples = (
        (b"%PDF-1.7\nNEXUS", "arquivo.pdf", "application/pdf"),
        (b"\xff\xd8\xff\xe0NEXUS", "foto.jpg", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nNEXUS", "foto.png", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPNEXUS", "foto.webp", "image/webp"),
    )
    for content, filename, mime in samples:
        assert validate_upload(content, filename, mime).mime_type
