from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.finance import models, schemas


def _valid_obligation_payload() -> dict:
    return {
        "entry_type": "income",
        "company_code": "universo_eletronica",
        "nfse_number": "100",
        "counterparty_name": "Cliente Teste",
        "description": "Serviço parcelado",
        "total_amount": Decimal("1000.00"),
        "issue_date": date(2026, 10, 7),
        "posting_date": date(2026, 10, 7),
        "bank_name": "Itaú",
        "installments": [
            {
                "installment_number": 1,
                "due_date": date(2026, 11, 7),
                "amount": Decimal("500.00"),
            },
            {
                "installment_number": 2,
                "due_date": date(2026, 12, 7),
                "amount": Decimal("500.00"),
            },
        ],
    }


def test_financial_obligation_model_exists() -> None:
    assert hasattr(
        models,
        "FinancialObligation",
    ), "Ainda não existe entidade pai para obrigação/documento financeiro."


def test_financial_entry_can_reference_obligation() -> None:
    assert hasattr(
        models.FinancialEntry,
        "obligation_id",
    ), "FinancialEntry ainda não possui vínculo com a obrigação financeira."

    assert hasattr(
        models.FinancialEntry,
        "installment_number",
    ), "FinancialEntry ainda não identifica o número da parcela."


def test_installment_batch_input_exists() -> None:
    assert hasattr(
        schemas,
        "FinancialObligationInput",
    ), "Ainda não existe schema para criação nativa de obrigação parcelada."

    assert hasattr(
        schemas,
        "FinancialInstallmentInput",
    ), "Ainda não existe schema para informar as parcelas."


def test_finance_router_exposes_native_installment_creation() -> None:
    router_path = (
        Path(__file__).parents[1]
        / "app"
        / "finance"
        / "router.py"
    )

    source = router_path.read_text(encoding="utf-8")
    normalized = " ".join(source.split())

    assert '"/obligations"' in normalized, (
        "Ainda não existe endpoint nativo para criação "
        "de obrigação financeira parcelada."
    )


def test_invoice_numbers_remain_non_unique() -> None:
    nfse = models.FinancialEntry.__table__.c.nfse_number
    nfe = models.FinancialEntry.__table__.c.nfe_number

    assert not nfse.unique
    assert not nfe.unique


def test_obligation_accepts_valid_installments() -> None:
    payload = schemas.FinancialObligationInput(**_valid_obligation_payload())

    assert len(payload.installments) == 2
    assert payload.total_amount == Decimal("1000.00")


def test_obligation_rejects_installment_sum_mismatch() -> None:
    data = _valid_obligation_payload()
    data["installments"][1]["amount"] = Decimal("400.00")

    with pytest.raises(ValidationError) as exc:
        schemas.FinancialObligationInput(**data)

    assert "soma das parcelas" in str(exc.value)


def test_obligation_rejects_non_sequential_installments() -> None:
    data = _valid_obligation_payload()
    data["installments"][1]["installment_number"] = 3

    with pytest.raises(ValidationError) as exc:
        schemas.FinancialObligationInput(**data)

    assert "numeradas sequencialmente" in str(exc.value)
