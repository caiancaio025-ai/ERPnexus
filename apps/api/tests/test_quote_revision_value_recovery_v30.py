"""V30 — reproduz a revisão 25.000 -> 22.000, preservando fotos e PDF."""
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import User  # noqa: F401 (registro FK)
from app.core.models import Base
from app.laboratory.models import LaboratoryDocument, LaboratoryQuote, LaboratoryQuoteItem, LaboratoryQuotePhoto
from app.laboratory.quote_items import sync_quote_items
from app.laboratory.quote_photos import _sync_quote_photos
from app.laboratory.quote_pdf import quote_pdf
from app.laboratory.schemas import QuoteInput, QuotePhotoInput


def _input(valor: int) -> QuoteInput:
    return QuoteInput(
        technical_report="Análise técnica concluída", services_description="Revisão do reparo",
        payment_terms="PIX", return_condition="Devolução conforme orçamento",
        consumer_clause="Garantia legal", supply_clause="Prazo conforme disponibilidade",
        estimate_clause="Orçamento revisado",
        items=[{"description": "Serviço de manutenção", "quantity": "1", "unit_value": str(valor)}],
        photos=[QuotePhotoInput(document_id=1, caption="Registro do equipamento")],
    )


def test_emitted_25000_can_be_revised_saved_22000_and_printed_without_removing_drafts():
    fitz = pytest.importorskip("fitz")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        LaboratoryQuote.__table__, LaboratoryQuoteItem.__table__,
        LaboratoryQuotePhoto.__table__, LaboratoryDocument.__table__,
    ])
    with Session(engine, expire_on_commit=False) as db:
        source = LaboratoryQuote(
            work_order_id=39405, revision=1, status="emitted", emitted_at=datetime.now(timezone.utc),
            created_by=1, technical_report="Laudo original", payment_terms="PIX",
            return_condition="Devolução", consumer_clause="Garantia", supply_clause="Prazo",
            estimate_clause="Estimativa", subtotal=Decimal("25000.00"), total=Decimal("25000.00"),
        )
        source.items = [LaboratoryQuoteItem(
            position=1, description="Serviço de manutenção", quantity=Decimal("1"),
            unit_value=Decimal("25000.00"),
        )]
        source.photos = [LaboratoryQuotePhoto(position=1, document_id=1, caption="Registro original")]
        db.add(source)
        db.commit()
        source_id = source.id
        source_item_id = source.items[0].id

        # Nova revisão é cópia da emitida, porém deve ser editável e independente.
        draft = LaboratoryQuote(
            work_order_id=39405, revision=2, status="draft", created_by=1,
            technical_report=source.technical_report, payment_terms="PIX",
            return_condition="Devolução", consumer_clause="Garantia", supply_clause="Prazo",
            estimate_clause="Estimativa", subtotal=Decimal("25000.00"), total=Decimal("25000.00"),
        )
        draft.items = [LaboratoryQuoteItem(
            position=1, description=item.description, quantity=item.quantity, unit_value=item.unit_value,
        ) for item in source.items]
        draft.photos = [LaboratoryQuotePhoto(
            position=1, document_id=1, caption="Registro original",
        )]
        db.add(draft)
        db.commit()
        draft_id = draft.id
        draft_item_id = draft.items[0].id

        new_payload = _input(22000)
        sync_quote_items(draft, new_payload.items)
        _sync_quote_photos(draft, new_payload.photos)
        draft.subtotal = Decimal("22000.00")
        draft.total = Decimal("22000.00")
        draft.technical_report = new_payload.technical_report
        db.commit()
        db.expire_all()

        persisted = db.get(LaboratoryQuote, draft_id)
        emitted = db.get(LaboratoryQuote, source_id)
        assert persisted.status == "draft" and persisted.emitted_at is None
        assert persisted.total == Decimal("22000.00")
        assert persisted.subtotal == Decimal("22000.00")
        assert persisted.items[0].unit_value == Decimal("22000.00")
        assert persisted.items[0].id == draft_item_id
        assert persisted.photos[0].document_id == 1
        assert persisted.photos[0].caption == "Registro do equipamento"
        assert emitted.total == Decimal("25000.00")
        assert emitted.items[0].id == source_item_id
        assert emitted.items[0].unit_value == Decimal("25000.00")

        # Regravações subsequentes devem manter a nova quantia e vínculos.
        sync_quote_items(persisted, _input(22000).items)
        _sync_quote_photos(persisted, _input(22000).photos)
        db.commit()
        db.expire_all()
        persisted = db.get(LaboratoryQuote, draft_id)
        assert persisted.total == Decimal("22000.00")
        assert persisted.items[0].id == draft_item_id

        order = SimpleNamespace(
            number="39405", company_code="universo_eletronica", customer_name="CAPRICHE",
            opened_at=date(2026, 11, 23), reported_defect="Defeito informado",
            entry_invoice="4455",
        )
        equipment = SimpleNamespace(
            equipment_type="Inversor", manufacturer="WEG", model="CFW11",
            power="75 kW", current=None, voltage="380 V",
        )
        pdf = quote_pdf(order, equipment, persisted, None)
        document = fitz.open(stream=pdf, filetype="pdf")
        content = "\n".join(page.get_text() for page in document)
        assert "22.000,00" in content
        assert "25.000,00" not in content


def test_create_and_revision_endpoints_reuse_unemitted_drafts_and_pdf_has_acknowledged_post():
    source = (Path(__file__).parents[1] / "app" / "laboratory" / "router.py").read_text()
    assert "return await update_quote(" in source.split("async def create_quote(", 1)[1].split("async def create_quote_revision(", 1)[0]
    assert "return _to_quote_output(existing_draft, include_sensitive_values=True)" in source
    assert '@router.post("/quotes/{quote_id}/emit")' in source
    assert "quote.status = \"emitted\"" in source


def test_editor_saves_pending_form_and_verifies_total_before_issuing():
    source = (Path(__file__).parents[2] / "web" / "src" / "features" / "laboratory" / "components" / "QuoteEditor.tsx").read_text()
    assert "const current = await persistDraft();" in source
    assert "verifyQuoteSaved(snapshot, savedQuote)" in source
    assert "selectQuote(savedQuote); // somente após confirmação da consulta persistida" in source
    assert "const data = await apiClient.get<Quote[]>(`/laboratory/work-orders/${workOrderId}/quotes?confirm=${Date.now()}`);" in source
    assert "const responseError = verifyQuoteSaved(snapshot, result);" in source
    assert "const persistedError = verifyQuoteSaved(snapshot, savedQuote);" in source
    assert "`${base}/laboratory/quotes/${quoteId}/emit`" in source
    assert "await response.blob()" in source

@pytest.mark.asyncio
async def test_real_quote_api_functions_revise_and_reuse_draft(monkeypatch):
    """Chama as rotinas FastAPI com SQLAlchemy real quando o driver PostgreSQL existe."""
    pytest.importorskip("psycopg", reason="Driver do ambiente Docker necessário para importar a API")
    from app.laboratory import router as endpoint

    class SessionAdapter:
        def __init__(self, sync): self.sync = sync
        async def get(self, model, key): return self.sync.get(model, key)
        async def scalar(self, query): return self.sync.scalar(query)
        async def scalars(self, query): return self.sync.scalars(query)
        async def execute(self, query): return self.sync.execute(query)
        async def flush(self): self.sync.flush()
        async def commit(self): self.sync.commit()
        async def refresh(self, value): self.sync.refresh(value)
        def add(self, value): self.sync.add(value)
        async def delete(self, value): self.sync.delete(value)

    async def fake_work_order(db, work_order_id, **kwargs):
        return SimpleNamespace(id=work_order_id, number=f"OS-{work_order_id}")

    async def fake_activity(*args, **kwargs):
        return None

    monkeypatch.setattr(endpoint, "_work_order_or_404", fake_work_order)
    monkeypatch.setattr(endpoint, "work_order_activity", fake_activity)
    user = SimpleNamespace(id=1, name="Gestor", role="gestao", modules=None)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        LaboratoryQuote.__table__, LaboratoryQuoteItem.__table__,
        LaboratoryQuotePhoto.__table__, LaboratoryDocument.__table__,
    ])
    with Session(engine, expire_on_commit=False) as sess:
        document = LaboratoryDocument(
            work_order_id=39405, category="analise", original_name="foto.jpg",
            storage_path="fake/foto.jpg", mime_type="image/jpeg", size_bytes=123,
            checksum_sha256="a" * 64, uploaded_by=1,
        )
        sess.add(document)
        sess.flush()
        photo_id = document.id
        source = LaboratoryQuote(
            work_order_id=39405, revision=1, status="emitted", emitted_at=datetime.now(timezone.utc),
            created_by=1, technical_report="Laudo emitido", payment_terms="PIX", return_condition="Devolução",
            consumer_clause="Garantia", supply_clause="Prazo", estimate_clause="Estimativa",
            subtotal=Decimal("25000.00"), total=Decimal("25000.00"),
        )
        source.items = [LaboratoryQuoteItem(
            position=1, description="Manutenção", quantity=Decimal("1"), unit_value=Decimal("25000.00"),
        )]
        source.photos = [LaboratoryQuotePhoto(document_id=photo_id, caption="Foto original", position=1)]
        sess.add(source)
        sess.commit()
        db = SessionAdapter(sess)
        draft = await endpoint.create_quote_revision(source.id, user=user, db=db)
        assert draft.revision == 2 and draft.status == "draft" and draft.total == Decimal("25000.00")
        assert draft.photos[0].document_id == photo_id

        update = _input(22000).model_copy(update={"photos": [QuotePhotoInput(document_id=photo_id, caption="Foto preservada")]})
        result = await endpoint.update_quote(draft.id, update, user=user, db=db)
        assert result.status == "draft" and result.total == Decimal("22000.00")
        assert result.items[0].unit_value == Decimal("22000.00")
        assert result.photos[0].caption == "Foto preservada"

        # Solicitar outra revisão não cria bloqueio ou exige apagar rascunhos.
        same = await endpoint.create_quote_revision(source.id, user=user, db=db)
        assert same.id == draft.id and same.total == Decimal("22000.00")
        # Repetir 'novo orçamento' salva sobre a revisão atual.
        again = await endpoint.create_quote(39405, _input(22000).model_copy(update={"photos": [QuotePhotoInput(document_id=photo_id)]}), user=user, db=db)
        assert again.id == draft.id and again.total == Decimal("22000.00")
        assert sess.get(LaboratoryQuote, source.id).total == Decimal("25000.00")
        assert sess.get(LaboratoryQuote, draft.id).total == Decimal("22000.00")
