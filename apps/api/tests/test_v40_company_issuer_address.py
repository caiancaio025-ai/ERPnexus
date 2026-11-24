"""Regressões V40: endereço por empresa emitente nos orçamentos do Lab."""
from pathlib import Path

from app.commercial.schemas import CompanyProfileInput
from app.laboratory.quote_pdf import _company_display_address


def test_company_form_schema_already_accepts_address_city_and_state():
    profile = CompanyProfileInput(
        company_code="emitente_a",
        legal_name="Emitente A",
        address="Rua Teste, 150 - Bairro Industrial",
        city="Recife",
        state="PE",
    )
    assert profile.address == "Rua Teste, 150 - Bairro Industrial"
    assert profile.city == "Recife"
    assert profile.state == "PE"


def test_company_address_is_formatted_without_empty_separators():
    assert _company_display_address({"address": "Rua da Oficina, 100", "city": "Recife", "state": "PE"}) == "Rua da Oficina, 100 - Recife/PE"
    assert _company_display_address({"address": "Rua X", "city": None, "state": None}) == "Rua X"
    assert _company_display_address({"address": None, "city": "Olinda", "state": "PE"}) == "Olinda/PE"
    assert _company_display_address({"address": None, "city": None, "state": None}) == "Não informado"


def test_issuer_snapshot_retains_its_own_address_fields():
    source = (Path(__file__).resolve().parents[1] / "app/laboratory/router.py").read_text(encoding="utf-8")
    section = source.split("def _company_snapshot_payload(", 1)[1].split("async def _ensure_rack_layout_available", 1)[0]
    for field in ("company_code", "address", "city", "state"):
        assert f'"{field}": company.{field}' in section
    assert "quote.company_snapshot = json.dumps" in source
    assert "json.loads(quote.company_snapshot)" in source
