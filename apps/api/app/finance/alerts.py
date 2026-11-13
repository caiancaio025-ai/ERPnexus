from __future__ import annotations

from hashlib import sha256


def finance_alert_fingerprint(*, due_date: object, amount: object, status: object) -> str:
    raw = f"{due_date}|{amount}|{status}"
    return sha256(raw.encode("utf-8")).hexdigest()
