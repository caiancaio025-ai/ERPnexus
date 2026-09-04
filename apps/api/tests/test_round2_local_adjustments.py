from pathlib import Path

from app.finance.schemas import ForecastPoint
from app.laboratory.schemas import QuoteInput


def test_quote_commercial_terms_accept_free_text() -> None:
    quote = QuoteInput(
        technical_report="Laudo",
        payment_terms="PIX",
        return_condition="30 dias",
        consumer_clause="CDC",
        supply_clause="Fornecimento",
        estimate_clause="Estimativa",
        billing_terms="21 dias após entrega e aceite",
        warranty_terms="90 dias após entrega técnica",
        items=[{"description": "Serviço", "quantity": 1, "unit_value": 100}],
    )
    assert quote.billing_terms == "21 dias após entrega e aceite"
    assert quote.warranty_terms == "90 dias após entrega técnica"


def test_forecast_point_represents_exact_due_date() -> None:
    point = ForecastPoint(date="2026-09-01", income=15000, expense=0, net=15000)
    assert point.date.isoformat() == "2026-09-01"
    assert point.income == 15000


def test_technician_duplicate_guards_are_present_in_router() -> None:
    source = (Path(__file__).parents[1] / "app" / "laboratory" / "router.py").read_text(encoding="utf-8")
    assert "_normalized_technician_name" in source
    assert "Já existe um técnico ativo com este nome" in source
    assert "Somente ADM ou Gestão" in source
