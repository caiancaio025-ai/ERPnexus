from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.laboratory.quote_pdf import quote_pdf
from app.laboratory.schemas import WorkOrderInput


ROOT = Path(__file__).parents[1]
WEB = ROOT.parent / "web"


def base_work_order_payload(**changes):
    data = dict(
        company_code="universo_eletronica",
        customer_name="Cliente",
        reported_defect="Falha",
        entry_invoice="123",
        exit_invoice=None,
    )
    data.update(changes)
    return data


def test_invoice_access_keys_are_optional_but_require_44_digits() -> None:
    assert WorkOrderInput(**base_work_order_payload()).entry_invoice_access_key is None
    key = "1" * 44
    payload = WorkOrderInput(**base_work_order_payload(entry_invoice_access_key=key))
    assert payload.entry_invoice_access_key == key
    with pytest.raises(ValidationError):
        WorkOrderInput(**base_work_order_payload(entry_invoice_access_key="123"))


@pytest.mark.parametrize("value", ["A1", "LAB", "MEC", " NOVO "])
def test_storage_location_schema_normalizes_configured_codes(value: str) -> None:
    payload = WorkOrderInput(**base_work_order_payload(storage_location=value))
    assert payload.storage_location == value.strip().upper()


def test_storage_location_schema_rejects_codes_longer_than_database_contract() -> None:
    with pytest.raises(ValidationError):
        WorkOrderInput(**base_work_order_payload(storage_location="LOCAL_12345"))


def test_migration_adds_location_history_and_quote_photo_snapshot() -> None:
    source = (ROOT / "migrations" / "versions" / "20261008_02_laboratory_workflow_locations_quote_photos.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20261008_01"' in source
    assert '"laboratory_location_history"' in source
    assert '"laboratory_quote_photos"' in source
    assert '"entry_invoice_access_key"' in source
    assert '"exit_invoice_access_key"' in source


def test_frontend_exposes_invoice_keys_location_and_report_photos() -> None:
    dash = (WEB / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx").read_text(encoding="utf-8")
    quote = (WEB / "src" / "features" / "laboratory" / "components" / "QuoteEditor.tsx").read_text(encoding="utf-8")
    assert "Chave NF entrada (44 dígitos)" in dash
    assert "SelectLocation" in dash
    assert '"/laboratory/locations/next"' in dash
    assert "Registro fotográfico do laudo" in quote
    assert "Anexar fotos ao laudo" in quote
    assert "/revisions" in quote


def test_pdf_places_photo_section_after_legal_clauses() -> None:
    source = (ROOT / "app" / "laboratory" / "quote_pdf.py").read_text(encoding="utf-8")
    assert source.index("Natureza prévia e estimativa do orçamento") < source.index("REGISTRO FOTOGRÁFICO")


def test_main_report_surfaces_physical_location() -> None:
    dash = (WEB / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx").read_text(encoding="utf-8")
    assert "<th>Localização</th>" in dash
    assert "lab-location-badge" in dash
    assert "Sem posição" in dash
    assert "Liberar posição" in dash


def test_status_flow_is_operationally_free() -> None:
    dash = (WEB / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx").read_text(encoding="utf-8")
    assert "Status livre para a operação" in dash
    assert "Override de Gestão" not in dash
