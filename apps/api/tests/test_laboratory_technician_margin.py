from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).parents[1]
REPORT = ROOT / "app" / "laboratory" / "production_report.py"
SCHEMAS = ROOT / "app" / "laboratory" / "schemas.py"


def test_margin_formula_is_gross_result_over_invoiced_total() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert 'return (gross_result / invoiced_total) * Decimal("100")' in source


def test_margin_is_undefined_when_invoice_is_zero() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "invoiced_total == ZERO" in source
    assert "return None" in source


def test_margin_is_exposed_at_summary_technician_and_work_order_levels() -> None:
    schemas = SCHEMAS.read_text(encoding="utf-8")
    assert schemas.count("gross_margin_percent: Decimal | None = None") == 3


def test_summary_and_breakdown_use_the_same_margin_helper() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "gross_margin_percent = _gross_margin_percent(invoiced_total, gross_result)" in source
    assert "group_margin = _gross_margin_percent(group_invoiced, group_gross)" in source
    assert "gross_margin_percent=_gross_margin_percent(invoiced, gross)" in source
