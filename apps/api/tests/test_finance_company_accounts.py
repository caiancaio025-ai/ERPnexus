from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.finance.models import FinancialAccount
from app.finance.service import build_finance_summary


def test_financial_account_is_scoped_by_company() -> None:
    assert hasattr(
        FinancialAccount,
        "company_code",
    ), "FinancialAccount ainda não possui company_code."


def test_finance_summary_filters_opening_balance_by_company() -> None:
    source = Path(build_finance_summary.__code__.co_filename).read_text(
        encoding="utf-8"
    )

    normalized = " ".join(source.split())

    assert "FinancialAccount.company_code" in normalized, (
        "O saldo inicial ainda não é filtrado pela empresa selecionada."
    )


def test_financial_account_name_is_not_globally_unique() -> None:
    name_column = FinancialAccount.__table__.c.name

    assert not name_column.unique, (
        "O nome da conta continua globalmente UNIQUE; "
        "isso impede contas com o mesmo nome em empresas diferentes."
    )


@pytest.mark.asyncio
async def test_financial_entry_validates_account_company() -> None:
    from app.finance.router import _validate_entry_account_company

    db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(company_code="universo_automacao")))
    payload = SimpleNamespace(account_id=7, company_code="universo_eletronica")
    with pytest.raises(HTTPException) as error:
        await _validate_entry_account_company(db, payload)
    assert error.value.status_code == 422 and "outra empresa" in error.value.detail
    db.get.return_value.company_code = payload.company_code
    await _validate_entry_account_company(db, payload)
