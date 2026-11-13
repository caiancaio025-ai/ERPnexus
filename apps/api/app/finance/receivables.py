"""Saldos por OS: valores financeiros calculados a partir das parcelas persistidas."""
from decimal import Decimal
from typing import Protocol


class Receivable(Protocol):
    amount: Decimal
    status: str


def summarize_receivables(
    installments: list[Receivable],
    approved: Decimal | None,
) -> dict[str, Decimal | None]:
    """Distingue obrigação lançada, dinheiro recebido e parcelas a receber.

    Entradas canceladas não são somadas. Não arredonda os valores para float.
    """
    active = [item for item in installments if item.status in {"pending", "received"}]
    registered = sum((item.amount for item in active), Decimal("0.00"))
    received = sum((item.amount for item in active if item.status == "received"), Decimal("0.00"))
    pending = sum((item.amount for item in active if item.status == "pending"), Decimal("0.00"))
    return {
        "total_registered": registered,
        "total_received": received,
        "total_pending": pending,
        "remaining_to_issue": (approved - registered) if approved is not None else None,
    }
