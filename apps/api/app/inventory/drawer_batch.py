"""Normalização dos códigos de gavetas para criação idempotente."""


def missing_drawer_numbers(existing_codes: list[str], start: int = 1, end: int = 493) -> list[int]:
    if not (1 <= start <= end <= 5000 and end - start < 500):
        raise ValueError("Faixa inválida de gavetas.")
    registered: set[int] = set()
    for value in existing_codes:
        code = value.strip().upper()
        if not code.startswith("GAVETA-"):
            continue
        suffix = code.removeprefix("GAVETA-")
        if suffix.isascii() and suffix.isdecimal():
            registered.add(int(suffix))
    return [number for number in range(start, end + 1) if number not in registered]
