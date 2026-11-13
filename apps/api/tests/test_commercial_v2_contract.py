from datetime import date, datetime, timezone
from types import SimpleNamespace
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.commercial.quote_pdf import commercial_quote_pdf
from app.commercial.schemas import CommercialEquipmentInput, CommercialQuoteInput


def test_equipment_accepts_single_inventory_unit_and_prices():
    item = CommercialEquipmentInput(
        equipment_type="Inversor CFW11",
        quantity=1,
        sale_price=12000,
        rental_monthly_price=2500,
        condition="Revisado",
        stock_status="available",
    )
    assert item.quantity == 1
    assert item.sale_price == 12000


@pytest.mark.parametrize("quantity", [0, 2, 3, 100])
def test_equipment_rejects_quantity_other_than_one(quantity):
    with pytest.raises(ValidationError):
        CommercialEquipmentInput(
            equipment_type="Inversor CFW11",
            quantity=quantity,
            stock_status="available",
        )


def test_quote_accepts_multiple_items_and_rental_period():
    quote = CommercialQuoteInput(
        quote_type="rental",
        company_code="universo_eletronica",
        customer_id=10,
        payment_terms="30 dias",
        rental_terms="LocaÃ§Ã£o mensal com manutenÃ§Ã£o conforme proposta.",
        items=[
            {"description": "Inversor CFW11", "quantity": 2, "unit_price": 1000, "rental_period_count": 3, "rental_period_unit": "month"},
            {"description": "Painel", "quantity": 1, "unit_price": 500},
        ],
    )
    assert len(quote.items) == 2
    assert quote.items[0].quantity == 2


def test_commercial_pdf_renders_sale_reference_layout():
    now = datetime.now(timezone.utc)
    quote = SimpleNamespace(
        quote_number="COM-001066", quote_type="sale", company_code="universo_eletronica",
        intro_text="Proposta comercial para fornecimento.", preventive_scope=None, rental_terms=None,
        delivery_terms="Entrega em atÃ© 7 dias.", payment_terms="Pix, boleto ou transferÃªncia.",
        warranty_terms="Garantia de 12 meses.", exclusions=None, notes="ObservaÃ§Ãµes comerciais.", total=1200,
    )
    company = SimpleNamespace(legal_name="EMPRESA DEMONSTRACAO INDUSTRIAL LTDA", document="00.000.000/0000-00", email="contato@example.com", phone="(00) 00000-0000", address="Av. Exemplo, 100", city="Recife", state="PE")
    customer = SimpleNamespace(legal_name="Cliente Demonstração", document="00.000.000/0000-00", email=None, phone=None, address="Rua de Teste", address_number="100", city="TimbaÃºba", state="PE")
    items = [SimpleNamespace(description="CAPACITOR WEG", manufacturer="WEG", model="L132015365", power=None, voltage=None, serial_number=None, quantity=20, unit="UN", unit_price=60, line_total=1200)]
    pdf = commercial_quote_pdf(quote=quote, company=company, customer=customer, items=items, show_values=True)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500


def test_main_registers_commercial_router():
    source = (Path(__file__).parents[1] / "app/main.py").read_text(encoding="utf-8")
    assert "commercial_router" in source
    assert "app.include_router(commercial_router" in source


def test_migration_is_additive_and_chained():
    source = (Path(__file__).parents[1] / "migrations/versions/20260904_02_commercial_workflow.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20260904_01"' in source
    assert '"commercial_quotes"' in source
    assert '"commercial_preventive_orders"' in source


def test_commercial_pdf_escapes_user_text_symbols():
    quote = SimpleNamespace(
        quote_number="COM-000001", revision=1, quote_type="sale", company_code="universo_eletronica",
        intro_text="Fornecedor A&B <industrial>", preventive_scope=None, rental_terms=None, delivery_terms="Entrega A&B",
        payment_terms="PIX & boleto", warranty_terms="12 < 24 meses", exclusions=None, notes="Motor <teste>", total=100,
    )
    company = SimpleNamespace(legal_name="Universo & Cia", document=None, email=None, phone=None, address=None, city=None, state=None)
    customer = SimpleNamespace(legal_name="Cliente A&B", document=None, email=None, phone=None, address=None, address_number=None, city=None, state=None)
    items = [SimpleNamespace(description="Inversor <CFW11> & painel", manufacturer="WEG", model=None, power=None, voltage=None, serial_number=None, quantity=1, unit="UN", unit_price=100, line_total=100)]
    pdf = commercial_quote_pdf(quote=quote, company=company, customer=customer, items=items, show_values=True)
    assert pdf.startswith(b"%PDF")


def test_commercial_router_has_status_machine_and_batch_listing():
    source = (Path(__file__).parents[1] / "app/commercial/router.py").read_text(encoding="utf-8")
    assert "QUOTE_STATUS_TRANSITIONS" in source
    assert "items_by_quote" in source
    assert "customer_map" in source
    normalized_source = " ".join(source.split())
    assert 'if quote.status!="approved": raise HTTPException(409' in normalized_source
    assert "O.S. preventiva" in source
