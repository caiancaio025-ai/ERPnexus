from datetime import date
from decimal import Decimal
from pathlib import Path

from app.finance.alerts import finance_alert_fingerprint
from app.finance.models import FinancialAlertAcknowledgment, FinancialPeriodClosure


def test_finance_governance_tables_have_expected_uniques() -> None:
    closure_names = {constraint.name for constraint in FinancialPeriodClosure.__table__.constraints}
    alert_names = {constraint.name for constraint in FinancialAlertAcknowledgment.__table__.constraints}
    assert "uq_financial_period_closures_company_period" in closure_names
    assert "uq_financial_alert_acknowledgments_entry_fingerprint" in alert_names


def test_alert_fingerprint_changes_with_business_state() -> None:
    base = finance_alert_fingerprint(
        due_date=date(2026, 10, 10),
        amount=Decimal("100.00"),
        status="pending",
    )
    changed_date = finance_alert_fingerprint(
        due_date=date(2026, 10, 11),
        amount=Decimal("100.00"),
        status="pending",
    )
    changed_amount = finance_alert_fingerprint(
        due_date=date(2026, 10, 10),
        amount=Decimal("101.00"),
        status="pending",
    )
    assert base != changed_date
    assert base != changed_amount


def test_router_contains_period_guards_for_mutations() -> None:
    source = (Path(__file__).parents[1] / "app" / "finance" / "router.py").read_text(
        encoding="utf-8"
    )
    assert "await _assert_period_open(db, payload.company_code, payload.posting_date)" in source
    assert "await _assert_period_open(db, entry.company_code, entry.posting_date)" in source
    assert '@router.post("/closures/close"' in source
    assert '@router.post("/closures/reopen"' in source


def test_cost_center_feature_was_removed() -> None:
    root = Path(__file__).parents[1]
    files = [
        root / "app" / "finance" / "models.py",
        root / "app" / "finance" / "schemas.py",
        root / "app" / "finance" / "router.py",
        root / "app" / "finance" / "reporting.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "FinancialCostCenter" not in combined
    assert "cost_center_id" not in combined
    assert "/cost-centers" not in combined
