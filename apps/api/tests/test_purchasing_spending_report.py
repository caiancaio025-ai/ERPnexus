from pathlib import Path


ROOT = Path(__file__).parents[1]
REPORT = ROOT / "app" / "purchasing" / "spending_report.py"
ROUTER = ROOT / "app" / "purchasing" / "router.py"


def test_spending_report_combines_both_canonical_purchase_flows() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "select(PurchaseOrder)" in source
    assert "select(MaterialRequest)" in source
    assert "MaterialRequest.status.in_(MATERIAL_COST_STATUSES)" in source
    assert 'source="purchase_order"' in source
    assert 'source="material_request"' in source


def test_material_request_spending_uses_purchase_timestamp_and_real_cost_statuses() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "MaterialRequest.purchased_at.is_not(None)" in source
    assert "MaterialRequest.unit_cost.is_not(None)" in source
    assert "_money(material.unit_cost) * Decimal(material.quantity or 0)" in source


def test_purchase_order_spending_excludes_deleted_and_cancelled() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "PurchaseOrder.is_deleted.is_(False)" in source
    assert 'PurchaseOrder.status != "cancelled"' in source


def test_report_does_not_attempt_heuristic_cross_flow_deduplication() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "não existe deduplicação heurística" in source
    assert "purchase_reference == " not in source
    assert "invoice_number == " not in source


def test_spending_endpoint_requires_sensitive_value_permission() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/reports/spending", response_model=PurchaseSpendingReport)' in source
    endpoint = source.split('@router.get("/reports/spending"', 1)[1].split('@router.get("/suppliers"', 1)[0]
    assert "_require_sensitive_values(user)" in endpoint
