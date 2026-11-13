"""Codigo curto de etiqueta EST, independente do numero de serie do fabricante.

As etiquetas antigas continuam pesquisaveis pelo numero do item.
"""
import re

_STOCK_QUERY = re.compile(r"^EST\s*-\s*0*(\d+)\s*$", re.IGNORECASE)


def format_stock_code(item_id: int) -> str:
    """EST-01 a EST-09, EST-10 em diante (sem limite artificial de digitos)."""
    if type(item_id) is not int or item_id <= 0:
        raise ValueError("ID de estoque deve ser inteiro positivo")
    return f"EST-{item_id:02d}"


def stock_id_from_query(value: str) -> int | None:
    """Ler EST-01, EST-00000001, 'EST - 01' sem interferir na serie OEM."""
    match = _STOCK_QUERY.fullmatch(value.strip())
    if match is None:
        return None
    number = int(match.group(1))
    return number if number > 0 else None
