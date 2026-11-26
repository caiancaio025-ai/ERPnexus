"""Billing a common invoice while keeping each OS's receivables independent."""
from __future__ import annotations

import hashlib
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance.idempotency import fingerprint_mapping

CENT = Decimal("0.01")
EXIT_INVOICE_FIELDS = ("exit_invoice", "exit_invoice_2", "exit_invoice_3")


def outgoing_invoice_number(payload) -> str | None:
    """An explicit selection wins; two different invoice numbers need a choice."""
    selected = (getattr(payload, "exit_invoice", None) or "").strip()
    if selected:
        return selected
    candidates = {
        value.strip()
        for value in (payload.nfse_number, payload.nfe_number)
        if value and value.strip()
    }
    if len(candidates) > 1:
        raise HTTPException(
            status_code=422,
            detail="Informe a NF de saída das OS quando a NF-e e a NFS-e têm números diferentes.",
        )
    return next(iter(candidates), None)


def outgoing_invoice_slot(work_order, number: str | None) -> str | None:
    """Find a free slot without silently replacing an already recorded invoice."""
    if not number:
        return None
    existing = {field: (getattr(work_order, field, None) or "").strip() for field in EXIT_INVOICE_FIELDS}
    if number in existing.values():
        return None
    for field, value in existing.items():
        if not value:
            return field
    raise HTTPException(
        status_code=409,
        detail=(
            f"A OS {work_order.number} já possui três NFs de saída diferentes. "
            "Revise os documentos no Laboratório antes de faturar."
        ),
    )


def assert_work_order_version(work_order, version: int | None) -> None:
    if version is not None and work_order.version != version:
        raise HTTPException(
            status_code=409,
            detail=f"A OS {work_order.number} foi alterada. Atualize a seleção antes de faturar.",
        )


def batch_identity(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def obligation_batch_key(batch_id: str, work_order_id: int) -> str:
    return f"billing-batch:{batch_id}:{work_order_id}"


async def lock_billing_batch(db: AsyncSession, batch_id: str) -> None:
    # A transaction-scoped lock lets a concurrent retry see the committed result
    # before stale OS versions or balance checks are evaluated.
    if db.get_bind().dialect.name == "postgresql":
        lock_id = int.from_bytes(bytes.fromhex(batch_id[:16]), byteorder="big", signed=True)
        await db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})


def billing_batch_fingerprint(payload) -> str:
    data = payload.model_dump(mode="json")
    data["work_orders"] = sorted(data["work_orders"], key=lambda row: row["work_order_id"])
    data["installments"] = sorted(data["installments"], key=lambda row: row["installment_number"])
    data["total_amount"] = str(payload.total_amount.quantize(CENT))
    for row in data["work_orders"] + data["installments"]:
        row["amount"] = str(Decimal(row["amount"]).quantize(CENT))
    return fingerprint_mapping(data)


def allocate_installments(
    work_order_amounts: list[Decimal], installment_amounts: list[Decimal],
) -> list[list[Decimal]]:
    """Allocate exact cents, preserving every OS total and every due-date total.

    One cent is reserved for each cell so all generated receivables are positive.
    The residual of each column is apportioned by remaining OS balances, using
    largest remainders with stable input-order ties. No floating point is used.
    """
    row_totals = [int(amount * 100) for amount in work_order_amounts]
    column_totals = [int(amount * 100) for amount in installment_amounts]
    row_count, column_count = len(row_totals), len(column_totals)
    if not row_count or not column_count or sum(row_totals) != sum(column_totals):
        raise ValueError("A soma dos valores por OS deve ser igual à soma das parcelas.")
    if any(value < column_count for value in row_totals):
        raise ValueError("Cada OS precisa de pelo menos R$ 0,01 por parcela. Reduza as parcelas ou ajuste os valores.")
    if any(value < row_count for value in column_totals):
        raise ValueError("Cada parcela precisa de pelo menos R$ 0,01 por OS. Reduza as parcelas ou ajuste os valores.")
    balances = [value - column_count for value in row_totals]
    columns = [value - row_count for value in column_totals]
    result = [[1 for _ in columns] for _ in balances]
    for column, required in enumerate(columns):
        total_available = sum(balances)
        if not required:
            continue
        quotients = [divmod(balance * required, total_available) for balance in balances]
        allocated = [quotient for quotient, _ in quotients]
        remainder = required - sum(allocated)
        order = sorted(range(row_count), key=lambda row: (-quotients[row][1], row))
        for row in order[:remainder]:
            allocated[row] += 1
        for row, amount in enumerate(allocated):
            result[row][column] += amount
            balances[row] -= amount
    return [[(Decimal(amount) / 100).quantize(CENT) for amount in row] for row in result]
