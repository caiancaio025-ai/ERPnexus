"""Contratos, cálculo monetário e conteúdo do PDF de orçamento conjunto."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.laboratory.grouped_quote_pdf import grouped_quote_pdf
from app.laboratory.grouped_quote_schemas import (
    GroupedQuoteCreate, GroupedQuoteItemInput, GroupedQuoteOutput, GroupedQuoteTerms,
)
from app.laboratory.grouped_quote_totals import grouped_totals


def item(key, value, *, quantity="1"):
    return GroupedQuoteItemInput(work_order_id=key, description="Reparo", quantity=quantity, unit_value=value)


@pytest.mark.parametrize("ids", [[3, 1, 2], [2, 3, 1], [1, 2, 3]])
def test_discount_remainder_goes_to_same_os_independent_of_display_order(ids):
    terms = GroupedQuoteTerms(discount_type="amount", discount_value="0.01")
    subtotal, discount, total, amounts = grouped_totals(ids, [item(key, "1") for key in ids], terms)
    assert (subtotal, discount, total) == (Decimal("3.00"), Decimal("0.01"), Decimal("2.99"))
    assert amounts[1]["discount_amount"] == Decimal("0.01")
    assert amounts[2]["discount_amount"] == amounts[3]["discount_amount"] == 0
    assert sum(row["total"] for row in amounts.values()) == total


def test_fractional_items_round_per_os_and_full_discount_never_creates_negative_balance():
    terms = GroupedQuoteTerms(discount_type="percent", discount_value="100")
    subtotal, discount, total, amounts = grouped_totals([1, 2, 3], [item(1, "0.03", quantity="0.5"), item(2, "0.05", quantity="0.5"), item(3, "0")], terms)
    assert subtotal == discount == Decimal("0.05") and total == 0
    assert amounts[1]["subtotal"] == Decimal("0.02") and amounts[2]["subtotal"] == Decimal("0.03")
    assert all(row["total"] == 0 for row in amounts.values())


def test_two_half_cent_lines_are_summed_as_their_visible_rounded_totals():
    subtotal, discount, total, amounts = grouped_totals([1, 2],
        [item(1, "0.01", quantity="0.5"), item(1, "0.01", quantity="0.5"), item(2, "1")], GroupedQuoteTerms())
    assert subtotal == total == Decimal("1.02") and discount == 0
    assert amounts[1]["subtotal"] == Decimal("0.02")


@pytest.mark.parametrize("terms,items", [
    (GroupedQuoteTerms(discount_type="amount", discount_value="4"), [item(1, "1"), item(2, "2")]),
    (GroupedQuoteTerms(), [item(1, "999999999999.99"), item(2, "0.01")]),
    (GroupedQuoteTerms(), [item(1, "1"), item(99, "1")]),
])
def test_invalid_totals_fail_before_persistence(terms, items):
    with pytest.raises(HTTPException) as error:
        grouped_totals([1, 2], items, terms)
    assert error.value.status_code == 422


@pytest.mark.parametrize("payload", [
    {"work_order_ids": [1]}, {"work_order_ids": [1, 1]}, {"work_order_ids": [0, 2]},
    {"work_order_ids": list(range(1, 52))},
    {"work_order_ids": [1, 2], "discount_type": "percent", "discount_value": "100.01"},
    {"work_order_ids": [1, 2], "discount_value": "NaN"},
    {"work_order_ids": [1, 2], "items": [{"work_order_id": 1, "description": "Reparo", "quantity": "1", "unit_value": "2"}]},
])
def test_invalid_membership_or_money_is_rejected(payload):
    with pytest.raises(ValidationError):
        GroupedQuoteCreate.model_validate(payload)


def sample_snapshot(*, long_text=False, count=4):
    terms = GroupedQuoteTerms(
        title="Reparo de inversores CFW11", technical_report=(
            "As unidades foram avaliadas individualmente. Foram constatadas falhas no estágio de potência e desgaste nos ventiladores. "
            + ("Foi realizado teste de isolamento, verificação dos módulos e inspeção dos conectores. " * 45 if long_text else "")),
        services_description="Substituição dos componentes danificados, limpeza técnica, montagem e ensaios em bancada.",
        discount_type="percent", discount_value="5",
    )
    ids = list(range(1, count + 1))
    items = [item(key, "1250.00") for key in ids]
    subtotal, discount, total, amounts = grouped_totals(ids, items, terms)
    data = GroupedQuoteOutput(**terms.model_dump(), id=1, group_id=1, code="OC-000123", revision=1,
        version=2, status="emitted", company_code="universo_eletronica", customer_id=1,
        customer_name="Cliente Industrial de Demonstração Ltda.", work_order_ids=ids,
        work_orders=[{
            "id": key, "number": f"2026-{100 + key:05d}", "equipment_id": key,
            "equipment_type": "Inversor de frequência", "manufacturer": "WEG", "model": "CFW11 7,5 kW",
            "equipment_serial": f"CFW11-TESTE-{key:04d}",
            "reported_defect": "Equipamento não aciona o motor. Apresenta falha de sobrecorrente na partida." + (
                " O cliente relata funcionamento intermitente durante o turno e paradas sem comando externo." * 12 if long_text else ""),
            "opened_at": "2026-11-26", "entry_invoice": "123456", "version": 2, **amounts[key],
        } for key in ids],
        items=[{"id": key, "position": key, "work_order_id": key, "description": "Manutenção corretiva do inversor, com substituição de componentes e testes de funcionamento.",
                "quantity": "1.000", "unit_value": "1250.00"} for key in ids],
        subtotal=subtotal, discount_amount=discount, total=total,
        emitted_at="2026-11-26T12:00:00+00:00", created_at="2026-11-26T12:00:00+00:00", updated_at="2026-11-26T12:00:00+00:00")
    return {
        "quote": data.model_dump(mode="json"), "issued_at": "2026-11-26T12:00:00+00:00",
        "company": {"legal_name": "Universo Eletrônica - Demonstração", "document": "00.000.000/0000-00",
                    "email": "contato@example.invalid", "phone": "00 00000-0000", "address": "Rua de Demonstração, 100", "city": "Recife", "state": "PE"},
        "customer": {"legal_name": "Cliente Industrial de Demonstração Ltda.", "document": "00.000.000/0000-00", "phone": "00 11111-1111"},
    }


@pytest.mark.parametrize("long_text", [False, True])
def test_pdf_contains_one_header_and_identifiable_os_with_each_total(long_text):
    fitz = pytest.importorskip("fitz")
    snapshot = sample_snapshot(long_text=long_text)
    content = grouped_quote_pdf(snapshot)
    reader = fitz.open(stream=content, filetype="pdf")
    text = "\n".join(page.get_text() for page in reader)
    assert content.startswith(b"%PDF-")
    assert text.count("ORÇAMENTO PRÉVIO") == 1
    assert text.count("TOTAL OS:") == 4
    assert "R$ 4.750,00" in text and "R$ 250,00" in text
    for order in snapshot["quote"]["work_orders"]:
        assert order["number"] in text and order["equipment_serial"] in text
    assert "Natureza prévia e estimativa do orçamento" in text
    assert "TERMOS E CONDIÇÕES DA PROPOSTA" in text
    assert len(reader) >= (3 if long_text else 2)
    if not long_text:
        assert len(reader) <= 3  # Não dedicar uma página vazia a cada OS curta.


def test_pdf_half_cent_lines_match_the_sum_printed_in_each_os():
    fitz = pytest.importorskip("fitz")
    snapshot = sample_snapshot(count=2)
    lines = [item(1, "0.01", quantity="0.5"), item(1, "0.01", quantity="0.5"), item(2, "1")]
    subtotal, discount, total, amounts = grouped_totals([1, 2], lines, GroupedQuoteTerms())
    snapshot["quote"].update(discount_type="none", discount_value="0", subtotal=str(subtotal), discount_amount=str(discount), total=str(total))
    snapshot["quote"]["items"] = [{"id": index, "position": index, **line.model_dump(mode="json")} for index, line in enumerate(lines, 1)]
    for order in snapshot["quote"]["work_orders"]:
        order.update({key: str(value) for key, value in amounts[order["id"]].items()})
    document = fitz.open(stream=grouped_quote_pdf(snapshot), filetype="pdf")
    text = "\n".join(page.get_text() for page in document)
    assert text.count("R$ 0,01") >= 2
    assert "R$ 0,02" in text and "R$ 1,02" in text
