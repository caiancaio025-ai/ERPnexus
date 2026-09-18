from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.laboratory.models import LaboratoryQuote
from app.laboratory.quote_pdf import (
    _effective_validity_days,
    _entry_invoice_text,
    quote_pdf,
)
from app.laboratory.schemas import QuoteInput
from app.laboratory.service import list_work_orders_page


WEB_ROOT = Path(__file__).parents[2] / "web"


@pytest.mark.asyncio
async def test_work_order_search_includes_equipment_name_manufacturer_model_and_combined_text() -> None:
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=0),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
    )

    await list_work_orders_page(
        db,
        page=1,
        page_size=25,
        search="WEG CFW11",
    )

    query = db.scalars.await_args.args[0]
    sql = str(query).lower()

    assert "laboratory_equipment" in sql
    assert "equipment_type" in sql
    assert "manufacturer" in sql
    assert "model" in sql
    assert "concat_ws" in sql
    assert "exists" in sql


def test_frontend_text_search_is_global_instead_of_being_blocked_by_period_or_status() -> None:
    source = (
        WEB_ROOT / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"
    ).read_text(encoding="utf-8")

    assert "const hasSearch = normalizedSearch.length > 0" in source
    assert 'params.set("search", normalizedSearch)' in source
    assert "if (hasSearch)" in source
    assert "} else {\n      params.set(\"year\", String(yearFilter));" in source
    assert "Buscar O.S., cliente, equipamento/modelo, NF entrada ou saída" in source


def test_new_laboratory_quote_defaults_to_30_days_and_frontend_keeps_it_editable() -> None:
    payload = QuoteInput(
        technical_report="Diagnóstico técnico",
        payment_terms="PIX",
        return_condition="Devolução",
        consumer_clause="Garantia",
        supply_clause="Fornecimento",
        estimate_clause="Estimativa",
        items=[
            {
                "description": "Serviço de manutenção",
                "quantity": 1,
                "unit_value": 100,
            }
        ],
    )
    assert payload.validity_days == 30
    assert LaboratoryQuote.__table__.c.validity_days.default is not None
    assert LaboratoryQuote.__table__.c.validity_days.default.arg == 30

    source = (
        WEB_ROOT / "src" / "features" / "laboratory" / "components" / "QuoteEditor.tsx"
    ).read_text(encoding="utf-8")
    assert "validity_days: 30" in source
    assert "quote.validity_days > 0 ? quote.validity_days : 30" in source
    assert 'label="Validade (dias)" value={form.validity_days}' in source
    assert 'onChange={(v)=>setForm({...form,validity_days:v})}' in source


def test_legacy_zero_validity_is_normalized_to_30_days() -> None:
    assert _effective_validity_days(SimpleNamespace(validity_days=0)) == 30
    assert _effective_validity_days(SimpleNamespace(validity_days=None)) == 30
    assert _effective_validity_days(SimpleNamespace(validity_days=45)) == 45


def test_entry_invoice_is_taken_from_work_order() -> None:
    assert _entry_invoice_text(SimpleNamespace(entry_invoice=" NF-98765 ")) == "NF-98765"
    assert _entry_invoice_text(SimpleNamespace(entry_invoice="")) == "Não informada"


def test_quote_pdf_generates_with_entry_invoice_and_legacy_zero_validity() -> None:
    work_order = SimpleNamespace(
        number="OS-1234",
        company_code="universo_eletronica",
        customer_name="Cliente Teste",
        opened_at=date(2026, 9, 18),
        reported_defect="Falha apresentada",
        entry_invoice="NF-98765",
    )
    equipment = SimpleNamespace(
        equipment_type="Inversor de Frequência",
        manufacturer="WEG",
        model="CFW11",
        power="24A",
        current=None,
        voltage="380V",
    )
    quote = SimpleNamespace(
        revision=1,
        emitted_at=None,
        updated_at=datetime.now(timezone.utc),
        service_code="3312102 / 14.01",
        technical_report="Diagnóstico técnico",
        services_description="Reparo completo",
        delivery_days=20,
        billing_days=21,
        billing_terms="21 dias",
        warranty_months=3,
        warranty_terms="3 meses",
        payment_terms="PIX",
        validity_days=0,
        return_condition="Devolução",
        consumer_clause="Garantia",
        supply_clause="Fornecimento",
        estimate_clause="Estimativa",
        discount_type="none",
        discount_value=Decimal("0"),
        subtotal=Decimal("1000"),
        total=Decimal("1000"),
        items=[
            SimpleNamespace(
                description="Serviço de manutenção",
                quantity=Decimal("1"),
                unit_value=Decimal("1000"),
            )
        ],
    )

    pdf = quote_pdf(work_order, equipment, quote, None)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000

    source = (Path(__file__).parents[1] / "app" / "laboratory" / "quote_pdf.py").read_text(
        encoding="utf-8"
    )
    assert '("NF de Entrada", _entry_invoice_text(work_order))' in source
    assert "validity_days = _effective_validity_days(quote)" in source
    assert "rowHeights=[35 * mm]" not in source
