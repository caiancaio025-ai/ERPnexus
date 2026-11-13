from pathlib import Path

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


def test_financial_entry_validates_account_company() -> None:
    router_path = Path(__file__).parents[1] / "app" / "finance" / "router.py"

    source = router_path.read_text(encoding="utf-8")
    normalized = " ".join(source.split())

    assert "FinancialAccount" in normalized, (
        "O router financeiro ainda não consulta a conta financeira."
    )
    assert "account.company_code != payload.company_code" in normalized, (
        "Ainda não existe validação impedindo lançamento em conta "
        "de outra empresa."
    )
    assert normalized.count("await _validate_entry_account_company(db, payload)") == 2, (
        "A validação da conta precisa ocorrer tanto na criação quanto na edição."
    )
