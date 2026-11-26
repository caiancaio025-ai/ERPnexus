"""Serializa fechamento/reabertura com as escritas da mesma competência.

Escritores obtêm estas travas depois das OS e dos títulos. O fechamento usa
somente a trava exclusiva da competência, sem bloquear OS ou títulos.
"""
import hashlib

from sqlalchemy import text


async def lock_period(db, company_code, year, month, *, exclusive=False):
    if db.get_bind().dialect.name != "postgresql":
        return
    identity = f"sentico:finance-period:{company_code}:{year:04d}:{month:02d}"
    key = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "big", signed=True)
    function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
    await db.execute(text(f"SELECT {function}(:key)"), {"key": key})


async def lock_entry_periods(db, entries):
    periods = {(row.company_code, row.posting_date.year, row.posting_date.month) for row in entries}
    for company_code, year, month in sorted(periods):
        await lock_period(db, company_code, year, month)
