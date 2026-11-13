"""Regressões para saldos financeiros de uma OS com pagamento parcelado."""
from decimal import Decimal
from types import SimpleNamespace

from app.finance.receivables import summarize_receivables


def payment(amount: str, status: str):
    return SimpleNamespace(amount=Decimal(amount), status=status)


def test_partially_received_order_is_not_confused_with_unissued_value():
    rows = [payment("333.34", "received"), payment("333.33", "pending"), payment("333.33", "pending")]
    totals = summarize_receivables(rows, Decimal("1000.00"))
    assert totals == {
        "total_registered": Decimal("1000.00"),
        "total_received": Decimal("333.34"),
        "total_pending": Decimal("666.66"),
        "remaining_to_issue": Decimal("0.00"),
    }


def test_partial_invoicing_cancelled_and_overage():
    rows = [payment("400.00", "received"), payment("150.00", "pending"), payment("900.00", "cancelled")]
    assert summarize_receivables(rows, Decimal("800.00"))["remaining_to_issue"] == Decimal("250.00")
    assert summarize_receivables(rows, Decimal("500.00"))["remaining_to_issue"] == Decimal("-50.00")
    assert summarize_receivables(rows, None)["remaining_to_issue"] is None
