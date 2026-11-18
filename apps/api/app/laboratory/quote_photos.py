"""Gravação incremental das fotos dos orçamentos de laboratório."""

from app.laboratory.models import LaboratoryQuote, LaboratoryQuotePhoto
from app.laboratory.schemas import QuotePhotoInput


def _sync_quote_photos(quote: LaboratoryQuote, photos: list[QuotePhotoInput]) -> None:
    """Atualiza fotos sem recriar vínculos existentes.

    Recriar a coleção em toda gravação dispara conflito em
    uq_lab_quote_photo_document (INSERT antes do DELETE), inclusive quando o
    usuário só alterou um valor. Preserva o ID e a ordem das fotos existentes,
    permite novas fotos e remove apenas os vínculos explicitamente retirados.
    """
    existing = {row.document_id: row for row in quote.photos}
    ordered = []
    for index, photo in enumerate(photos, start=1):
        row = existing.get(photo.document_id)
        if row is None:
            row = LaboratoryQuotePhoto(document_id=photo.document_id)
        row.position = index
        row.caption = photo.caption
        ordered.append(row)
    quote.photos = ordered


