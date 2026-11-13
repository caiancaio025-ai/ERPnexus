from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

MIRROR_VERSION = "13.0"
SENTINEL_DATE = date(2000, 1, 1)
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")
INVALID_DOCS = {"", "-", "--", "---", "none", "null", "n/a", "nan", "snf", "s/n", "s/nf", "sem nf"}
LEGACY_MARK_RE = re.compile(r"\[LEGACY\s+([^\]]+)\]", re.I)
SOURCE_SPECS = (
    ("universo_automacao", "banco_automacao.db"),
    ("universo_eletronica", "banco_empresa.db"),
    ("solucoes_eletronica", "banco_solucoes.db"),
)


def dec(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_legacy_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
        # Datas como 28/04/0205 existem na fonte. Elas são preservadas em notes,
        # mas não são transformadas silenciosamente em 2025. Vão para o bucket 01/2000
        # até edição manual, mantendo os meses reais idênticos ao SQLite.
        return parsed if 2000 <= parsed.year <= 2100 else None
    return None


def bank_name(company_code: str, raw: Any) -> str:
    text = str(raw or "").strip()
    folded = text.casefold()
    if company_code == "universo_automacao" and folded == "brasil":
        return "Banco do Brasil"
    if folded in {"itau", "itaú"}:
        return "Itaú"
    if folded == "bradesco":
        return "Bradesco"
    return {
        "universo_automacao": "Banco do Brasil",
        "universo_eletronica": "Itaú",
        "solucoes_eletronica": "Bradesco",
    }[company_code]


def clean_document(value: Any) -> str | None:
    text = clean(value)
    if not text or text.casefold() in INVALID_DOCS:
        return None
    return text


def add_note(existing: str | None, *parts: str | None) -> str | None:
    output: list[str] = []
    for part in (existing, *parts):
        if part and part.strip() and part.strip() not in output:
            output.append(part.strip())
    return "\n\n".join(output) if output else None


def marker(row: dict[str, Any]) -> str:
    return f"[LEGACY {row['source_db']}.{row['source_table']}#{row['source_id']}]"


def source_dir_from_args(args) -> Path:
    if args.data_dir:
        return Path(args.data_dir).resolve()
    return Path(__file__).resolve().parent / "finance_legacy_mirror_v13"


def verify_source_files(data_dir: Path) -> dict[str, Any]:
    manifest = json.loads((data_dir / "manifest_v13.json").read_text(encoding="utf-8"))
    source_dir = data_dir / "source"
    for dbname, meta in manifest["sources"].items():
        path = source_dir / dbname
        if not path.is_file():
            raise RuntimeError(f"Fonte ausente: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            raise RuntimeError(f"SHA256 divergente em {dbname}: esperado {meta['sha256']}, encontrado {digest}")
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        for table, table_meta in meta["tables"].items():
            count = int(connection.execute(f"select count(*) from {table}").fetchone()[0])
            total = sum(
                (dec(row[0]) for row in connection.execute(f"select VALOR from {table}")),
                Decimal("0.00"),
            )
            if count != int(table_meta["rows"]) or total != dec(table_meta["sum"]):
                connection.close()
                raise RuntimeError(
                    f"Fonte divergente {dbname}.{table}: "
                    f"esperado rows={table_meta['rows']} sum={table_meta['sum']}; "
                    f"encontrado rows={count} sum={total}"
                )
        connection.close()
    return manifest


def load_source_rows(data_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_dir = data_dir / "source"
    incomes: list[dict[str, Any]] = []
    expenses: list[dict[str, Any]] = []
    for company_code, dbname in SOURCE_SPECS:
        connection = sqlite3.connect(source_dir / dbname)
        connection.row_factory = sqlite3.Row
        for table, kind in (("faturamento_bradesco", "income"), ("saidas_operacionais", "expense")):
            rows = connection.execute(f"select rowid as __rowid__, * from {table} order by rowid").fetchall()
            for source in rows:
                source_id = source["ID"] if "ID" in source.keys() and source["ID"] is not None else source["__rowid__"]
                row = dict(source)
                row.update(
                    {
                        "company_code": company_code,
                        "source_db": dbname,
                        "source_table": table,
                        "source_id": str(source_id),
                    }
                )
                (incomes if kind == "income" else expenses).append(row)
        connection.close()
    return incomes, expenses


def expected_from_source(incomes, expenses):
    result: dict[tuple[str, str, str], tuple[int, Decimal]] = {}
    grouped: dict[tuple[str, str, str], list[Decimal]] = defaultdict(list)
    for rows, kind, date_field in (
        (incomes, "income", "DATA_FAT"),
        (expenses, "expense", "DATA_SAIDA"),
    ):
        for row in rows:
            posting = parse_legacy_date(row.get(date_field))
            period = posting.strftime("%Y-%m") if posting else "UNDATED"
            grouped[(row["company_code"], kind, period)].append(dec(row.get("VALOR")))
    for key, amounts in grouped.items():
        result[key] = (len(amounts), sum(amounts, Decimal("0.00")))
    return result


def source_ranges(incomes, expenses):
    grouped: dict[tuple[str, str], list[date]] = defaultdict(list)
    for rows, kind, date_field in (
        (incomes, "income", "DATA_FAT"),
        (expenses, "expense", "DATA_SAIDA"),
    ):
        for row in rows:
            posting = parse_legacy_date(row.get(date_field))
            if posting:
                grouped[(row["company_code"], kind)].append(posting)
    return {key: (min(values), max(values)) for key, values in grouped.items()}


def income_desired(row: dict[str, Any]) -> dict[str, Any]:
    posting = parse_legacy_date(row.get("DATA_FAT")) or SENTINEL_DATE
    due = parse_legacy_date(row.get("DATA_VENC")) or posting
    nfse = clean_document(row.get("NFS"))
    nfe = clean_document(row.get("NFD"))
    paid = str(row.get("STATUS") or "").strip().upper() == "PAGO"
    return {
        "entry_type": "income",
        "company_code": row["company_code"],
        "invoice_type": "nfse" if nfse and not nfe else ("nfe" if nfe and not nfse else None),
        "series": None,
        "nfse_number": nfse,
        "nfe_number": nfe,
        "counterparty_name": (clean(row.get("CLIENTE")) or "CLIENTE NÃO INFORMADO")[:180],
        "description": (
            f"Faturamento legado - orçamento {clean(row.get('ORCAMENTO'))}"
            if clean(row.get("ORCAMENTO"))
            else "Faturamento legado"
        )[:180],
        "amount": dec(row.get("VALOR")),
        "issue_date": posting,
        "posting_date": posting,
        "due_date": due,
        "settlement_date": due if paid and due != SENTINEL_DATE else None,
        "status": "received" if paid else "pending",
        "bank_name": bank_name(row["company_code"], row.get("BANCO")),
        "expense_kind": None,
        "document_number": None,
        "payment_code": None,
    }


def expense_desired(row: dict[str, Any]) -> dict[str, Any]:
    posting = parse_legacy_date(row.get("DATA_SAIDA")) or SENTINEL_DATE
    issue = parse_legacy_date(row.get("DATA_EMISSAO")) or posting
    paid = str(row.get("STATUS") or "").strip().upper() == "PAGO"
    return {
        "entry_type": "expense",
        "company_code": row["company_code"],
        "invoice_type": None,
        "series": None,
        "nfse_number": None,
        "nfe_number": None,
        "counterparty_name": (clean(row.get("FORNECEDOR")) or "FORNECEDOR NÃO INFORMADO")[:180],
        "description": (clean(row.get("SERVICO")) or clean(row.get("CATEGORIA")) or "Saída operacional legada")[:180],
        "amount": dec(row.get("VALOR")),
        "issue_date": issue,
        "posting_date": posting,
        "due_date": posting,
        "settlement_date": posting if paid and posting != SENTINEL_DATE else None,
        "status": "paid" if paid else "pending",
        "bank_name": bank_name(row["company_code"], row.get("BANCO")),
        "expense_kind": "supplier",
        "document_number": None,
        "payment_code": clean(row.get("LINHA_DIGITAVEL")),
    }


def source_note(row: dict[str, Any], kind: str, tag: str) -> str | None:
    if kind == "income":
        posting_valid = parse_legacy_date(row.get("DATA_FAT")) is not None
        emails = ", ".join(filter(None, [clean(row.get("EMAIL1")), clean(row.get("EMAIL2")), clean(row.get("EMAIL3"))]))
        return add_note(
            tag,
            f"[LEGACY MIRROR V{MIRROR_VERSION}: SQLite bruto]",
            "[LEGACY DATA SEM COMPETÊNCIA: bucket 01/2000 até edição manual]" if not posting_valid else None,
            clean(row.get("OBSERVACAO")),
            f"DATA_FAT original: {row.get('DATA_FAT') or ''}",
            f"DATA_VENC original: {row.get('DATA_VENC') or ''}",
            f"ORÇAMENTO original: {row.get('ORCAMENTO') or ''}",
            f"NFS original: {row.get('NFS') or ''}",
            f"NFD original: {row.get('NFD') or ''}",
            f"E-mails legados: {emails}" if emails else None,
        )
    posting_valid = parse_legacy_date(row.get("DATA_SAIDA")) is not None
    return add_note(
        tag,
        f"[LEGACY MIRROR V{MIRROR_VERSION}: SQLite bruto]",
        "[LEGACY DATA SEM COMPETÊNCIA: bucket 01/2000 até edição manual]" if not posting_valid else None,
        clean(row.get("OBSERVACAO")),
        f"DATA_SAIDA original: {row.get('DATA_SAIDA') or ''}",
        f"DATA_EMISSAO original: {row.get('DATA_EMISSAO') or ''}",
        f"Categoria legada: {row.get('CATEGORIA') or ''}" if clean(row.get("CATEGORIA")) else None,
        f"Anexo legado: {row.get('ANEXO') or ''}" if clean(row.get("ANEXO")) else None,
    )


def print_source_summary(expected, from_period: str) -> None:
    print("Cobertura direta do SQLite bruto:")
    for (company, kind, period), (count, amount) in sorted(expected.items()):
        if period != "UNDATED" and period < from_period:
            continue
        print(f"{company:22} {kind:7} {period:7} {amount:>12.2f} ({count:>4})")


async def run_database(args, data_dir: Path, incomes, expenses, expected) -> int:
    # Importações são intencionalmente tardias para permitir --source-check-only
    # em qualquer ambiente Python, sem exigir o driver PostgreSQL.
    from sqlalchemy import select
    from app.auth.models import User
    from app.core.db import session_factory
    from app.finance.models import FinancialEntry
    from app.laboratory import models as _laboratory_models  # noqa: F401

    async def actor_id(session) -> int:
        query = await session.execute(
            select(User)
            .where(User.is_active.is_(True))
            .order_by(
                (User.role == "super_admin").desc(),
                (User.role.in_(["management", "gestao", "gestor"])).desc(),
                (User.role == "admin").desc(),
                User.id.asc(),
            )
        )
        user = query.scalars().first()
        if not user:
            raise RuntimeError("Nenhum usuário ativo para registrar a conciliação.")
        return user.id

    async def entries_by_marker(session, tag: str):
        query = await session.execute(
            select(FinancialEntry)
            .where(FinancialEntry.notes.ilike(f"%{tag}%"))
            .order_by(FinancialEntry.id.asc())
        )
        return list(query.scalars().all())

    def different_fields(entry, desired):
        return [field for field, value in desired.items() if getattr(entry, field) != value]

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    counters = Counter()
    details: list[dict[str, str]] = []
    source_tags: set[str] = set()
    ranges = source_ranges(incomes, expenses)

    async with session_factory() as session:
        actor = await actor_id(session)
        for rows, kind in ((incomes, "income"), (expenses, "expense")):
            for row in rows:
                tag = marker(row)
                source_tags.add(tag)
                desired = income_desired(row) if kind == "income" else expense_desired(row)
                matches = await entries_by_marker(session, tag)
                entry = matches[0] if matches else None
                # Duplicatas internas com o mesmo marcador nunca podem permanecer ativas.
                for duplicate in matches[1:]:
                    if not duplicate.is_deleted:
                        duplicate.is_deleted = True
                        duplicate.deleted_at = datetime.now(timezone.utc)
                        duplicate.notes = add_note(duplicate.notes, f"[LEGACY MIRROR V{MIRROR_VERSION}: duplicata de marcador desativada]")
                        counters["duplicate_marker_soft_deleted"] += 1
                if entry is None:
                    entry = FinancialEntry(**desired, created_by=actor, notes=source_note(row, kind, tag))
                    session.add(entry)
                    counters[f"{kind}_created"] += 1
                    details.append({"action": f"{kind}_create", "marker": tag, "fields": "all"})
                    continue
                fields = different_fields(entry, desired)
                restored = bool(entry.is_deleted)
                if restored:
                    entry.is_deleted = False
                    entry.deleted_at = None
                for field in fields:
                    setattr(entry, field, desired[field])
                entry.notes = add_note(entry.notes, source_note(row, kind, tag))
                if fields or restored:
                    counters[f"{kind}_updated"] += 1
                    details.append({"action": f"{kind}_update", "marker": tag, "fields": ";".join(fields), "restored": str(restored)})
                else:
                    counters[f"{kind}_unchanged"] += 1

        await session.flush()
        # Para cumprir a decisão do usuário de espelhar o legado, qualquer lançamento ativo
        # dentro do período histórico coberto e que não exista na fonte é desativado logicamente.
        active_query = await session.execute(
            select(FinancialEntry)
            .where(FinancialEntry.is_deleted.is_(False))
            .order_by(FinancialEntry.id.asc())
        )
        now = datetime.now(timezone.utc)
        for entry in active_query.scalars().all():
            key = (entry.company_code, entry.entry_type)
            if key not in ranges:
                continue
            start, end = ranges[key]
            in_scope = start <= entry.posting_date <= end or entry.posting_date == SENTINEL_DATE
            if not in_scope:
                continue
            found = LEGACY_MARK_RE.search(entry.notes or "")
            current_tag = f"[LEGACY {found.group(1)}]" if found else None
            if current_tag in source_tags:
                continue
            entry.is_deleted = True
            entry.deleted_at = now
            entry.notes = add_note(entry.notes, f"[LEGACY MIRROR V{MIRROR_VERSION}: desativado por não existir no SQLite de referência]")
            counters["non_source_soft_deleted"] += 1
            details.append({
                "action": "non_source_soft_delete",
                "marker": f"financial_entries#{entry.id}",
                "fields": f"company={entry.company_code};type={entry.entry_type};posting={entry.posting_date};amount={entry.amount}",
            })

        await session.flush()
        # Verificação forte: considera TODOS os registros ativos no escopo, não apenas os marcados.
        actual: dict[tuple[str, str, str], list[Decimal]] = defaultdict(list)
        actual_rows = await session.execute(select(FinancialEntry).where(FinancialEntry.is_deleted.is_(False)))
        for entry in actual_rows.scalars().all():
            key2 = (entry.company_code, entry.entry_type)
            if key2 not in ranges:
                continue
            start, end = ranges[key2]
            if not (start <= entry.posting_date <= end or entry.posting_date == SENTINEL_DATE):
                continue
            period = "UNDATED" if entry.posting_date == SENTINEL_DATE else entry.posting_date.strftime("%Y-%m")
            actual[(entry.company_code, entry.entry_type, period)].append(dec(entry.amount))

        problems: list[str] = []
        checks: list[dict[str, str]] = []
        for key in sorted(set(expected) | set(actual)):
            expected_count, expected_amount = expected.get(key, (0, Decimal("0.00")))
            values = actual.get(key, [])
            actual_count = len(values)
            actual_amount = sum(values, Decimal("0.00"))
            ok = expected_count == actual_count and expected_amount == actual_amount
            if not ok:
                problems.append(
                    f"{key}: esperado count={expected_count}, amount={expected_amount}; "
                    f"atual count={actual_count}, amount={actual_amount}"
                )
            checks.append({
                "company_code": key[0], "entry_type": key[1], "period": key[2],
                "expected_count": str(expected_count), "actual_count": str(actual_count),
                "expected_amount": str(expected_amount), "actual_amount": str(actual_amount),
                "ok": "1" if ok else "0",
            })

        with (report_dir / "mirror_check.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(checks[0].keys()))
            writer.writeheader()
            writer.writerows(checks)
        with (report_dir / "plan_details.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["action", "marker", "fields", "restored"], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(details)
        (report_dir / "summary.json").write_text(
            json.dumps({"counters": dict(counters), "problems": problems}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"NEXUS FINANCE LEGACY MIRROR V{MIRROR_VERSION} - {'APPLY' if args.apply else 'DRY-RUN'}")
        for name, value in sorted(counters.items()):
            print(f"{name:34} {value}")
        print("\nComparação projetada com o SQLite bruto:")
        for row in checks:
            if row["period"] != "UNDATED" and row["period"] < args.from_period:
                continue
            print(
                f"{row['company_code']:22} {row['entry_type']:7} {row['period']:7} "
                f"esperado {Decimal(row['expected_amount']):>12.2f} ({int(row['expected_count']):>4}) "
                f"atual {Decimal(row['actual_amount']):>12.2f} ({int(row['actual_count']):>4}) "
                f"{'OK' if row['ok']=='1' else 'ERRO'}"
            )

        if problems:
            await session.rollback()
            print("\nBLOQUEADO: a projeção não ficou idêntica ao SQLite fornecido.")
            for problem in problems[:30]:
                print(" -", problem)
            return 3
        if args.apply:
            await session.commit()
            print("\nAPLICAÇÃO CONCLUÍDA. Financeiro histórico alinhado ao SQLite bruto.")
        else:
            await session.rollback()
            print("\nDRY-RUN CONCLUÍDO. Nenhuma alteração gravada.")
    return 0


async def run(args) -> int:
    data_dir = source_dir_from_args(args)
    verify_source_files(data_dir)
    incomes, expenses = load_source_rows(data_dir)
    expected = expected_from_source(incomes, expenses)
    print(f"Fontes verificadas: {len(incomes)} receitas + {len(expenses)} despesas = {len(incomes)+len(expenses)} registros.")
    print_source_summary(expected, args.from_period)
    if args.source_check_only:
        print("\nSOURCE CHECK OK. Nenhum banco do NEXUS foi acessado.")
        return 0
    return await run_database(args, data_dir, incomes, expenses, expected)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default=None)
    p.add_argument("--report-dir", default="/app/storage/finance_legacy_mirror_v13")
    p.add_argument("--from-period", default="2026-01")
    p.add_argument("--source-check-only", action="store_true")
    p.add_argument("--apply", action="store_true")
    return p


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parser().parse_args())))
