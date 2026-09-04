"""Dry-run/apply merge for duplicate active laboratory technicians.

Duplicates are matched case-insensitively after whitespace normalization.
The lowest id is kept. Work orders assigned to duplicate ids are moved to the
keeper before duplicates are deactivated. No technician row is deleted.
"""
import argparse
import asyncio

from sqlalchemy import select

from app.core.db import session_factory
from app.laboratory.models import LaboratoryTechnician, LaboratoryWorkOrder


def normalize(name: str) -> str:
    return " ".join(name.casefold().split())


async def run(apply: bool) -> int:
    async with session_factory() as db:
        rows = list((await db.scalars(select(LaboratoryTechnician).order_by(LaboratoryTechnician.id))).all())
        groups: dict[str, list[LaboratoryTechnician]] = {}
        for row in rows:
            if not row.is_active:
                continue
            groups.setdefault(normalize(row.name), []).append(row)

        duplicate_groups = [group for group in groups.values() if len(group) > 1]
        if not duplicate_groups:
            print("Nenhum tecnico ativo duplicado encontrado.")
            return 0

        for group in duplicate_groups:
            keeper = min(group, key=lambda item: item.id)
            duplicates = [item for item in group if item.id != keeper.id]
            print(f"KEEP #{keeper.id} {keeper.name!r}")
            for duplicate in duplicates:
                assigned = list((await db.scalars(
                    select(LaboratoryWorkOrder).where(
                        LaboratoryWorkOrder.assigned_technician_id == duplicate.id
                    )
                )).all())
                print(f"  DUP #{duplicate.id} {duplicate.name!r} -> {len(assigned)} OS")
                if apply:
                    for order in assigned:
                        order.assigned_technician_id = keeper.id
                    duplicate.is_active = False

        if apply:
            await db.commit()
            print("Aplicado: OS reassociadas e duplicados inativados; nenhum registro foi apagado.")
        else:
            await db.rollback()
            print("DRY-RUN: nenhuma alteracao foi gravada. Use --apply apos revisar.")
        return len(duplicate_groups)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.apply)))
