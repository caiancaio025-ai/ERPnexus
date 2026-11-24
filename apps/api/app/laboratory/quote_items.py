"""Atualização estável dos itens de um rascunho de orçamento."""

from app.laboratory.models import LaboratoryQuote, LaboratoryQuoteItem
from app.laboratory.schemas import QuoteItemInput


def sync_quote_items(quote: LaboratoryQuote, items: list[QuoteItemInput]) -> None:
    """Reutiliza linhas existentes e preserva a ordem ao editar valores.

    O frontend envia itens por posição (não por ID). Recriar a coleção a cada
    alteração é desnecessário e pode dificultar a inspeção de rascunhos após
    revisões ou enquanto há fotografias vinculadas. Remove apenas excedentes.
    """
    old = list(quote.items)
    result: list[LaboratoryQuoteItem] = []
    for index, item in enumerate(items):
        row = old[index] if index < len(old) else LaboratoryQuoteItem()
        row.position = index + 1
        row.description = item.description
        row.quantity = item.quantity
        row.unit_value = item.unit_value
        result.append(row)
    quote.items = result
