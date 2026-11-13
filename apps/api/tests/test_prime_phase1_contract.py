from pathlib import Path

from app.laboratory.schemas import QuoteInput

API_ROOT = Path(__file__).parents[1]
WEB_ROOT = API_ROOT.parent / "web"


def _minimal_quote(**changes: object) -> QuoteInput:
    payload: dict[str, object] = {
        "technical_report": "",
        "payment_terms": "PIX",
        "return_condition": "30 dias",
        "consumer_clause": "CDC",
        "supply_clause": "Fornecimento",
        "estimate_clause": "Estimativa",
        "items": [{"description": "Serviço", "quantity": 1, "unit_value": 100}],
    }
    payload.update(changes)
    return QuoteInput(**payload)


def test_quote_draft_accepts_empty_technical_report() -> None:
    quote = _minimal_quote(technical_report="")
    assert quote.technical_report == ""


def test_quote_emission_requires_technical_report_but_preview_remains_available() -> None:
    source = (API_ROOT / "app" / "laboratory" / "router.py").read_text(encoding="utf-8")

    assert 'if not preview and not (quote.technical_report or "").strip():' in source
    assert "Preencha o diagnóstico técnico / laudo antes de emitir o orçamento." in source
    assert "status.HTTP_422_UNPROCESSABLE_ENTITY" in source


def test_purchasing_background_refresh_preserves_selected_supplier() -> None:
    source = (WEB_ROOT / "src" / "features" / "purchasing" / "PurchasingDashboard.tsx").read_text(
        encoding="utf-8"
    )

    assert "setForm((current) => {" in source
    assert "if (current.supplier_id || !supplierData[0]) return current;" in source
    assert "return { ...current, supplier_id: String(supplierData[0].id) };" in source
    assert "if (!form.supplier_id && supplierData[0])" not in source
