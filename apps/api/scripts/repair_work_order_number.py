"""Repara uma OS criada com numeração baixa por sequence dessincronizada.

Uso seguro (somente leitura):
    python scripts/repair_work_order_number.py OS-0005

Aplicação explícita:
    python scripts/repair_work_order_number.py OS-0005 --apply
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.core.db import session_factory


async def repair(target_number: str, apply: bool) -> None:
    async with session_factory() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('laboratory_work_order_number_seq'))"))
        target = (await db.execute(
            text("SELECT id, number, customer_name, opened_at FROM laboratory_work_orders WHERE number = :number"),
            {"number": target_number},
        )).mappings().first()
        if not target:
            raise SystemExit(f"OS {target_number} não encontrada.")

        max_existing = int(await db.scalar(text(
            """
            SELECT COALESCE(MAX(CAST(SUBSTRING(number FROM 4) AS BIGINT)), 0)
            FROM laboratory_work_orders
            WHERE number ~ '^OS-[0-9]+$' AND number <> :target
            """
        ), {"target": target_number}) or 0)
        new_number = f"OS-{max_existing + 1:04d}"
        collision = await db.scalar(
            text("SELECT 1 FROM laboratory_work_orders WHERE number = :number"),
            {"number": new_number},
        )
        if collision:
            raise SystemExit(f"Número calculado {new_number} já existe; operação abortada.")

        print(f"OS atual:   {target['number']}")
        print(f"Cliente:    {target['customer_name']}")
        print(f"Entrada:    {target['opened_at']}")
        print(f"Novo número:{new_number}")

        if not apply:
            await db.rollback()
            print("DRY-RUN: nenhuma alteração gravada.")
            return

        await db.execute(
            text("UPDATE laboratory_work_orders SET number = :new WHERE id = :id"),
            {"new": new_number, "id": target["id"]},
        )
        await db.execute(
            text("SELECT setval('laboratory_work_order_number_seq', :next_number, false)"),
            {"next_number": max_existing + 2},
        )
        await db.commit()
        print(f"APLICADO: {target_number} -> {new_number}. Próxima OS prevista: OS-{max_existing + 2:04d}.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_order", help="Número atual, por exemplo OS-0005")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(repair(args.work_order, args.apply))


if __name__ == "__main__":
    main()
