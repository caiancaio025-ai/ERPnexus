from pathlib import Path
from uuid import uuid4


def persist_attachment(
    root: Path,
    *,
    company_code: str,
    entry_id: int,
    extension: str,
    content: bytes,
) -> Path:
    """Persiste anexo em armazenamento durável e retorna o caminho final.

    A função não mascara erros de I/O: o router converte OSError em HTTP 503,
    permitindo distinguir falha de armazenamento de arquivo inválido.
    """
    directory = root / company_code
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{entry_id}-{uuid4().hex}{extension}"
    target.write_bytes(content)
    return target
