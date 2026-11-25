"""Numeração anual de compras e solicitações, protegida até o commit.

Um SELECT do último código seguido de INSERT permite dois usuários escolherem
o mesmo número. O lock transacional é compartilhado por todos os processos da
API e liberado automaticamente em commit/rollback, inclusive em caso de erro.
"""
import re
from datetime import date

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute


async def next_purchasing_code(
    db: AsyncSession, column: InstrumentedAttribute, kind: str,
) -> str:
    year = date.today().year
    prefix = f"{kind}-{year}-"
    if db.get_bind().dialect.name == "postgresql":
        # Dois int32 estáveis; nunca usar hash() do Python (muda por processo).
        namespace = {"PC": 1397050947, "SC": 1397052227}[kind]
        await db.execute(select(func.pg_advisory_xact_lock(namespace, year)))
        last = await db.scalar(select(func.max(
            cast(func.substr(column, len(prefix) + 1), Numeric(30, 0))
        )).where(column.op("~")(rf"^{re.escape(prefix)}[0-9]+$")))
        sequence = int(last or 0) + 1
    else:
        # O ambiente local de testes usa SQLite; os bancos implantados usam PG.
        codes = (await db.scalars(select(column).where(column.like(f"{prefix}%")))).all()
        sequence = max(
            (int(code[len(prefix):]) for code in codes
             if code.startswith(prefix) and code[len(prefix):].isascii()
             and code[len(prefix):].isdigit()),
            default=0,
        ) + 1
    return f"{prefix}{sequence:04d}"
