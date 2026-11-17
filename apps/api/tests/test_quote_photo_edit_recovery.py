"""V17: imagens nunca podem impedir a edição nem emitir PDF incompleto."""
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import User  # registra a tabela users para resolução de chaves
from app.core.models import Base
from app.laboratory.models import (
    LaboratoryDocument,
    LaboratoryQuote,
    LaboratoryQuoteItem,
    LaboratoryQuotePhoto,
)
from app.laboratory.quote_pdf import quote_pdf
from app.laboratory.quote_photos import _sync_quote_photos
from app.laboratory.schemas import QuoteInput, QuotePhotoInput


def _payload(**changes):
    base = dict(
        technical_report="Laudo",
        payment_terms="PIX",
        return_condition="Devolução",
        consumer_clause="Garantia",
        supply_clause="Prazo",
        estimate_clause="Estimativa",
        items=[dict(description="Reparo", quantity=1, unit_value=1200)],
    )
    base.update(changes)
    return QuoteInput(**base)


def test_quote_accepts_ten_photos_and_rejects_eleven_or_duplicate_ids():
    assert len(_payload(photos=[dict(document_id=i) for i in range(1, 11)]).photos) == 10
    with pytest.raises(ValidationError):
        _payload(photos=[dict(document_id=i) for i in range(1, 12)])
    with pytest.raises(ValidationError, match="mesma foto"):
        _payload(photos=[dict(document_id=1), dict(document_id=1)])


def test_quote_valuations_and_photo_links_survive_multiple_saves_in_sqlite():
    """Replica a restrição única responsável pelo conflito de gravação."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        LaboratoryQuote.__table__,
        LaboratoryQuoteItem.__table__,
        LaboratoryQuotePhoto.__table__,
        LaboratoryDocument.__table__,
    ])
    with Session(engine, expire_on_commit=False) as db:
        quote = LaboratoryQuote(
            work_order_id=39405,
            created_by=1,
            technical_report="Laudo original",
            payment_terms="PIX",
            return_condition="Devolução",
            consumer_clause="Garantia",
            supply_clause="Fornecimento",
            estimate_clause="Estimativa",
            total=Decimal("1000.00"),
        )
        quote.photos = [LaboratoryQuotePhoto(document_id=1, caption="Defeito 01")]
        db.add(quote)
        db.commit()
        quote_id, first_photo_id = quote.id, quote.photos[0].id

        # Primeiro update: a foto já existe e o valor precisa ser salvo.
        quote.total = Decimal("1750.00")
        quote.technical_report = "Laudo alterado após anexar foto"
        _sync_quote_photos(quote, [QuotePhotoInput(document_id=1, caption="Novo texto")])
        db.commit()
        assert quote.photos[0].id == first_photo_id

        # Segundo update: acrescentar outras 9 fotos e alterar novamente o valor.
        quote.total = Decimal("2600.00")
        _sync_quote_photos(quote, [QuotePhotoInput(document_id=i) for i in range(1, 11)])
        db.commit()
        db.expire_all()
        reloaded = db.get(LaboratoryQuote, quote_id)
        assert reloaded.total == Decimal("2600.00")
        assert reloaded.technical_report == "Laudo alterado após anexar foto"
        assert len(reloaded.photos) == 10
        assert reloaded.photos[0].id == first_photo_id

        # Remover e alterar a legenda: nenhuma foto remanescente é recriada.
        kept_id = reloaded.photos[1].id
        _sync_quote_photos(reloaded, [QuotePhotoInput(document_id=2, caption="Após reparo")])
        db.commit()
        db.expire_all()
        reloaded = db.get(LaboratoryQuote, quote_id)
        assert [(photo.id, photo.document_id, photo.caption) for photo in reloaded.photos] == [
            (kept_id, 2, "Após reparo"),
        ]


def test_pdf_generates_ten_numbered_photos_without_detaching_captions(tmp_path):
    fitz = pytest.importorskip("fitz")
    Image = pytest.importorskip("PIL.Image")
    photos = []
    for index in range(1, 11):
        img = tmp_path / f"foto_{index}.jpg"
        dims = (400, 280) if index % 2 else (280, 400)
        Image.new("RGB", dims, (230, 225, 210)).save(img, quality=80)
        photos.append((str(img), f"Registro visual {index}"))

    work_order = SimpleNamespace(
        number="39405", company_code="universo_eletronica", customer_name="CAPRICHE",
        opened_at=date(2026, 11, 17), reported_defect="Curto circuito", entry_invoice="4455",
    )
    equipment = SimpleNamespace(
        equipment_type="Inversor", manufacturer="WEG", model="CFW11",
        power="75 KW", current=None, voltage="380 V",
    )
    quote = SimpleNamespace(
        revision=1, emitted_at=None, updated_at=datetime.now(timezone.utc),
        service_code="3312102 / 14.01", technical_report="Laudo com fotos",
        services_description="Substituição dos IGBTs", delivery_days=20, billing_days=21,
        billing_terms="21 dias", warranty_months=3, warranty_terms="3 meses",
        payment_terms="PIX", validity_days=30, return_condition="Devolução",
        consumer_clause="Garantia", supply_clause="Fornecimento", estimate_clause="Estimativa",
        discount_type="none", discount_value=Decimal("0"),
        subtotal=Decimal("2600"), total=Decimal("2600"),
        items=[SimpleNamespace(description="Manutenção", quantity=1, unit_value=Decimal("2600"))],
    )
    pdf = quote_pdf(work_order, equipment, quote, None, photos)
    assert pdf.startswith(b"%PDF")
    document = fitz.open(stream=pdf, filetype="pdf")
    assert document.page_count >= 3
    extracted = "\n".join(page.get_text() for page in document)
    for i in range(1, 11):
        assert extracted.count(f"Foto {i:02d}") == 1
        assert f"Registro visual {i}" in extracted


def test_pdf_emission_is_persisted_only_after_pdf_success():
    source = (Path(__file__).parents[1] / "app" / "laboratory" / "router.py").read_text()
    endpoint = source.split("async def quote_pdf_endpoint(", 1)[1].split("# ---", 1)[0]
    assert endpoint.index("pdf_bytes = await asyncio.to_thread") < endpoint.index('quote.status = "emitted"')
    assert "Nenhum rascunho foi bloqueado" in endpoint
