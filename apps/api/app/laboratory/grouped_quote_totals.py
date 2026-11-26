"""Cálculo exato e rateio determinístico de desconto em centavos por OS."""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from fastapi import HTTPException

from app.laboratory.grouped_quote_schemas import GroupedQuoteItemInput, GroupedQuoteTerms, MAX_MONEY

CENT = Decimal("0.01")


def line_total(quantity: Decimal, unit_value: Decimal) -> Decimal:
    """O total visível de cada linha é a unidade monetária somada no orçamento."""
    return (quantity * unit_value).quantize(CENT, rounding=ROUND_HALF_UP)


def grouped_totals(ids: list[int], items: list[GroupedQuoteItemInput], terms: GroupedQuoteTerms):
    # Cada OS tem um subtotal independente e auditável; o total geral é sua soma.
    raw = {work_order_id: Decimal("0") for work_order_id in ids}
    for item in items:
        if item.work_order_id not in raw:
            raise HTTPException(422, "Um item pertence a uma OS não incluída no orçamento.")
        raw[item.work_order_id] += line_total(item.quantity, item.unit_value)
    subtotals = {key: value.quantize(CENT, rounding=ROUND_HALF_UP) for key, value in raw.items()}
    subtotal = sum(subtotals.values(), Decimal("0.00"))
    if subtotal > MAX_MONEY:
        raise HTTPException(422, "O valor do orçamento excede o limite permitido.")
    discount = (subtotal * terms.discount_value / 100 if terms.discount_type == "percent"
                else terms.discount_value if terms.discount_type == "amount" else Decimal("0"))
    discount = discount.quantize(CENT, rounding=ROUND_HALF_UP)
    if discount > subtotal:
        raise HTTPException(422, "O desconto não pode exceder o subtotal do orçamento.")
    shares = {key: Decimal("0.00") for key in ids}
    if subtotal and discount:
        exact = {key: discount * value / subtotal for key, value in subtotals.items()}
        shares = {key: value.quantize(CENT, rounding=ROUND_DOWN) for key, value in exact.items()}
        remaining = int((discount - sum(shares.values())) / CENT)
        # Empates usam ID crescente, portanto reordenar a tela não muda os centavos.
        remainder_order = sorted(ids, key=lambda key: (-(exact[key] - shares[key]), key))
        for key in remainder_order[:remaining]:
            shares[key] += CENT
    per_order = {key: {"subtotal": subtotals[key], "discount_amount": shares[key], "total": subtotals[key] - shares[key]} for key in ids}
    return subtotal, discount, subtotal - discount, per_order
