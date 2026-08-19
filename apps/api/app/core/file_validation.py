from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DetectedFileType:
    mime_type: str
    extension: str


PDF = DetectedFileType("application/pdf", ".pdf")
JPEG = DetectedFileType("image/jpeg", ".jpg")
PNG = DetectedFileType("image/png", ".png")
WEBP = DetectedFileType("image/webp", ".webp")

_ALLOWED_BY_EXTENSION = {
    ".pdf": PDF,
    ".jpg": JPEG,
    ".jpeg": JPEG,
    ".png": PNG,
    ".webp": WEBP,
}
_ALLOWED_MIME = {item.mime_type for item in _ALLOWED_BY_EXTENSION.values()}
_GENERIC_MIME = {None, "", "application/octet-stream"}


class InvalidUpload(ValueError):
    pass


def detect_file_type(content: bytes) -> DetectedFileType | None:
    """Detect supported file types from their binary signatures, never from headers."""
    if content.startswith(b"%PDF-"):
        return PDF
    if content.startswith(b"\xff\xd8\xff"):
        return JPEG
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return WEBP
    return None


def validate_upload(
    content: bytes,
    filename: str | None,
    reported_mime: str | None,
) -> DetectedFileType:
    """Validate signature plus optional filename/MIME consistency for a supported upload."""
    detected = detect_file_type(content)
    if detected is None:
        raise InvalidUpload("Assinatura do arquivo inválida ou formato não suportado.")

    extension = Path(filename or "").suffix.lower()
    if extension:
        expected = _ALLOWED_BY_EXTENSION.get(extension)
        if expected is None:
            raise InvalidUpload("Extensão não permitida. Use PDF, JPG, PNG ou WEBP.")
        if expected.mime_type != detected.mime_type:
            raise InvalidUpload("A extensão do arquivo não corresponde ao conteúdo real.")

    normalized_mime = (reported_mime or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized_mime not in _GENERIC_MIME:
        if normalized_mime not in _ALLOWED_MIME:
            raise InvalidUpload("Tipo MIME não permitido. Use PDF, JPG, PNG ou WEBP.")
        if normalized_mime != detected.mime_type:
            raise InvalidUpload("O tipo MIME informado não corresponde ao conteúdo real.")

    return detected
