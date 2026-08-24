from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.auth.models import User
from app.core.db import session_factory
from app.finance.models import FinancialEntry
from app.laboratory.models import LaboratoryStatusHistory, LaboratoryWorkOrder

COMPANY_BY_DB = {
    "banco_empresa.db": "universo_eletronica",
    "banco_automacao.db": "universo_automacao",
    "banco_solucoes.db": "solucoes_eletronica",
}
STATUS_INCOME = {"PAGO": "received", "EM ABERTO": "pending", "ATRASADO": "pending"}
STATUS_EXPENSE = {"PAGO": "paid", "EM ABERTO": "pending", "ATRASADO": "pending"}
LEGACY_MARKER_RE = re.compile(r"\[LEGACY\s+([^\]]+)\]", re.IGNORECASE)


def txt(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.casefold() in {"-", "--", "---", "n/a", "none", "null"}:
        return None
    return s


def money(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    s = str(value or "0").replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return Decimal(s).quantize(Decimal("0.01"))


def parse_iso(value: Any) -> date:
    return date.fromisoformat(str(value).strip())


def marker(source: str, table: str, row_id: Any) -> str:
    return f"[LEGACY {source}.{table}#{row_id}]"


def has_legacy_marker(notes: str | None) -> bool:
    return bool(notes and LEGACY_MARKER_RE.search(notes))


def combine_notes(*parts: Any) -> str | None:
    values = [txt(x) for x in parts]
    values = [x for x in values if x]
    return "\n\n".join(values) if values else None


def normalize_name(value: Any) -> str:
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s).casefold()
    return re.sub(r"\s+", " ", s).strip()


def normalize_doc(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", str(value or "")).casefold()


def names_compatible(a: str, b: str) -> bool:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.60


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def sqlite_row(source_dir: Path, db_name: str, table: str, row_id: int) -> sqlite3.Row:
    path = source_dir / db_name
    if not path.exists():
        raise RuntimeError(f"Fonte auditada ausente: {path}")
    uri = f"file:{path.resolve().as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        if "ID" in columns:
            row = conn.execute(f'SELECT rowid AS __rowid__, * FROM "{table}" WHERE ID = ?', (row_id,)).fetchone()
        else:
            row = conn.execute(f'SELECT rowid AS __rowid__, * FROM "{table}" WHERE rowid = ?', (row_id,)).fetchone()
        if row is None:
            raise RuntimeError(f"Linha não encontrada: {db_name}.{table}#{row_id}")
        return row
    finally:
        conn.close()


async def actor_id(session) -> int:
    result = await session.execute(
        select(User).where(User.is_active.is_(True)).order_by(
            (User.role == "super_admin").desc(),
            (User.role.in_(["management", "gestao", "gestor"])).desc(),
            (User.role == "admin").desc(),
            User.id.asc(),
        )
    )
    user = result.scalars().first()
    if not user:
        raise RuntimeError("Nenhum usuário ativo disponível para registrar a conciliação.")
    return user.id


async def find_entry_by_marker(session, tag: str) -> FinancialEntry | None:
    result = await session.execute(
        select(FinancialEntry).where(FinancialEntry.notes.ilike(f"%{tag}%")).order_by(FinancialEntry.id.asc())
    )
    return result.scalars().first()


def reconciliation_note(manifest: dict[str, str]) -> str:
    if str(manifest.get("valid_original", "")).casefold() == "true":
        return "[RECONCILIADO 2026-08-24: registro legítimo auditado ausente no PostgreSQL]"
    return "[RECONCILIADO 2026-08-24: data recuperada de forma determinística]"


def make_income_entry(row: sqlite3.Row, manifest: dict[str, str], actor: int) -> FinancialEntry:
    db_name = manifest["db"]
    legacy_id = int(manifest["legacy_id"])
    issue = parse_iso(manifest["issue_corrected"])
    due = parse_iso(manifest["due_corrected"])
    nfse, nfe = txt(row["NFS"]), txt(row["NFD"])
    raw_status = (txt(row["STATUS"]) or "EM ABERTO").upper()
    return FinancialEntry(
        entry_type="income",
        company_code=COMPANY_BY_DB[db_name],
        invoice_type="nfse" if nfse and not nfe else ("nfe" if nfe and not nfse else None),
        nfse_number=nfse,
        nfe_number=nfe,
        counterparty_name=(txt(row["CLIENTE"]) or "CLIENTE NÃO INFORMADO")[:180],
        description=(f"Faturamento legado - orçamento {txt(row['ORCAMENTO'])}" if txt(row["ORCAMENTO"]) else "Faturamento legado")[:180],
        amount=money(row["VALOR"]),
        issue_date=issue,
        posting_date=issue,
        due_date=due,
        settlement_date=None,
        status=STATUS_INCOME.get(raw_status, "pending"),
        bank_name=(txt(row["BANCO"]) or "Bradesco")[:80],
        notes=combine_notes(
            marker(db_name, "faturamento_bradesco", legacy_id),
            txt(row["OBSERVACAO"]),
            f"Orçamento legado: {txt(row['ORCAMENTO'])}" if txt(row["ORCAMENTO"]) else None,
            reconciliation_note(manifest),
        ),
        created_by=actor,
    )


def make_expense_entry(row: sqlite3.Row, manifest: dict[str, str], actor: int) -> FinancialEntry:
    db_name = manifest["db"]
    legacy_id = int(manifest["legacy_id"])
    posting = parse_iso(manifest["posting_corrected"])
    issue = parse_iso(manifest["issue_corrected"])
    raw_status = (txt(row["STATUS"]) or "EM ABERTO").upper()
    return FinancialEntry(
        entry_type="expense",
        company_code=COMPANY_BY_DB[db_name],
        counterparty_name=(txt(row["FORNECEDOR"]) or "FORNECEDOR NÃO INFORMADO")[:180],
        description=(txt(row["SERVICO"]) or txt(row["CATEGORIA"]) or "Saída operacional legada")[:180],
        amount=money(row["VALOR"]),
        issue_date=issue,
        posting_date=posting,
        due_date=posting,
        settlement_date=None,
        status=STATUS_EXPENSE.get(raw_status, "pending"),
        bank_name=(txt(row["BANCO"]) or "Bradesco")[:80],
        expense_kind="supplier" if txt(row["FORNECEDOR"]) else "variable",
        payment_code=txt(row["LINHA_DIGITAVEL"]),
        notes=combine_notes(
            marker(db_name, "saidas_operacionais", legacy_id),
            txt(row["OBSERVACAO"]),
            f"Categoria legada: {txt(row['CATEGORIA'])}" if txt(row["CATEGORIA"]) else None,
            reconciliation_note(manifest),
        ),
        created_by=actor,
    )


async def monthly_totals(session) -> dict[tuple[str, str, str], Decimal]:
    q = (
        select(
            FinancialEntry.company_code,
            FinancialEntry.entry_type,
            func.to_char(FinancialEntry.posting_date, "YYYY-MM").label("period"),
            func.coalesce(func.sum(FinancialEntry.amount), 0),
        )
        .where(FinancialEntry.is_deleted.is_(False))
        .group_by(FinancialEntry.company_code, FinancialEntry.entry_type, "period")
    )
    rows = (await session.execute(q)).all()
    return {(c, t, p): Decimal(str(v)) for c, t, p, v in rows}


def expected_legacy_totals(
    income_safe: list[dict[str, str]],
    recover_income: list[dict[str, str]],
    expense_safe: list[dict[str, str]],
    recover_expense: list[dict[str, str]],
) -> dict[tuple[str, str, str], Decimal]:
    totals: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in [*income_safe, *recover_income]:
        period = row["issue_corrected"][:7]
        totals[(row["company"], "income", period)] += money(row["amount"])
    for row in [*expense_safe, *recover_expense]:
        period = row["posting_corrected"][:7]
        totals[(row["company"], "expense", period)] += money(row["amount"])
    return totals


async def active_entries_for_period(session, period: str) -> list[FinancialEntry]:
    start = date.fromisoformat(f"{period}-01")
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    result = await session.execute(
        select(FinancialEntry)
        .where(
            FinancialEntry.is_deleted.is_(False),
            FinancialEntry.posting_date >= start,
            FinancialEntry.posting_date < end,
        )
        .order_by(FinancialEntry.company_code, FinancialEntry.entry_type, FinancialEntry.posting_date, FinancialEntry.id)
    )
    return list(result.scalars().all())


def exact_business_key(entry: FinancialEntry) -> tuple[Any, ...] | None:
    invoice = normalize_doc(entry.nfse_number) or normalize_doc(entry.nfe_number)
    if not invoice:
        return None
    return (
        entry.company_code,
        entry.entry_type,
        normalize_name(entry.counterparty_name),
        invoice,
        money(entry.amount),
        entry.issue_date,
        entry.due_date,
    )


async def source_coverage_for_period(
    session,
    period: str,
    expected: dict[tuple[str, str, str], Decimal],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    entries = await active_entries_for_period(session, period)
    marked_totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    unmarked_totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    unmarked_rows: list[dict[str, Any]] = []
    marked_by_key: dict[tuple[Any, ...], list[FinancialEntry]] = defaultdict(list)

    for entry in entries:
        key2 = (entry.company_code, entry.entry_type)
        if has_legacy_marker(entry.notes):
            marked_totals[key2] += money(entry.amount)
            key = exact_business_key(entry)
            if key:
                marked_by_key[key].append(entry)
        else:
            unmarked_totals[key2] += money(entry.amount)
            unmarked_rows.append({
                "id": entry.id,
                "company": entry.company_code,
                "entry_type": entry.entry_type,
                "posting_date": str(entry.posting_date),
                "issue_date": str(entry.issue_date),
                "due_date": str(entry.due_date),
                "client_supplier": entry.counterparty_name,
                "nfse": entry.nfse_number or "",
                "nfe": entry.nfe_number or "",
                "amount": str(entry.amount),
                "status": entry.status,
                "description": entry.description,
            })

    duplicate_candidates: list[dict[str, Any]] = []
    for entry in entries:
        if has_legacy_marker(entry.notes):
            continue
        key = exact_business_key(entry)
        if not key or key not in marked_by_key:
            continue
        for marked in marked_by_key[key]:
            duplicate_candidates.append({
                "unmarked_entry_id": entry.id,
                "legacy_entry_id": marked.id,
                "company": entry.company_code,
                "entry_type": entry.entry_type,
                "client_supplier": entry.counterparty_name,
                "nfse": entry.nfse_number or "",
                "nfe": entry.nfe_number or "",
                "issue_date": str(entry.issue_date),
                "due_date": str(entry.due_date),
                "amount": str(entry.amount),
            })

    companies = sorted({c for c, _, p in expected if p == period} | {e.company_code for e in entries})
    coverage: list[dict[str, Any]] = []
    for company in companies:
        for entry_type in ("income", "expense"):
            exp = expected.get((company, entry_type, period), Decimal("0.00"))
            marked = marked_totals.get((company, entry_type), Decimal("0.00"))
            unmarked = unmarked_totals.get((company, entry_type), Decimal("0.00"))
            total = marked + unmarked
            coverage.append({
                "company": company,
                "entry_type": entry_type,
                "period": period,
                "expected_legacy": str(exp),
                "legacy_marked_after_plan": str(marked),
                "unmarked_after_plan": str(unmarked),
                "total_after_plan": str(total),
                "legacy_gap": str(exp - marked),
                "total_vs_expected": str(total - exp),
            })
    return coverage, unmarked_rows, duplicate_candidates


def write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    fields = list(rows[0].keys()) if rows else fallback_fields
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


async def run(args: argparse.Namespace) -> int:
    base = Path(__file__).resolve().parent
    data_dir = Path(args.data_dir).resolve() if args.data_dir else base / "finance_reconcile_data"
    source_dir = Path(args.source_dir).resolve()
    out_dir = Path(args.report_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    income_safe = load_csv(data_dir / "income_safe_all.csv")
    expense_safe = load_csv(data_dir / "expense_safe_all.csv")
    recover_income = load_csv(data_dir / "recover_income.csv")
    recover_expense = load_csv(data_dir / "recover_expense.csv")
    dup_remove = load_csv(data_dir / "income_duplicates_remove.csv")
    lab_rows = load_csv(data_dir / "lab_mark_invoiced.csv")
    expected = expected_legacy_totals(income_safe, recover_income, expense_safe, recover_expense)

    counters = Counter()
    details: list[dict[str, Any]] = []

    async with session_factory() as session:
        actor = await actor_id(session)
        before = await monthly_totals(session)

        # 0) Sincroniza todos os lançamentos LEGÍTIMOS e já auditados do SQLite atual.
        # Nunca sobrescreve registro que já possui o marcador legado.
        for m in income_safe:
            tag = marker(m["db"], "faturamento_bradesco", int(m["legacy_id"]))
            existing = await find_entry_by_marker(session, tag)
            if existing:
                counters["income_safe_already_present"] += 1
                continue
            row = sqlite_row(source_dir, m["db"], "faturamento_bradesco", int(m["legacy_id"]))
            session.add(make_income_entry(row, m, actor))
            counters["income_safe_missing_create"] += 1
            details.append({"action": "create_missing_safe_income", "marker": tag, "amount": str(m["amount"]), "date": m["issue_corrected"]})

        for m in expense_safe:
            tag = marker(m["db"], "saidas_operacionais", int(m["legacy_id"]))
            existing = await find_entry_by_marker(session, tag)
            if existing:
                counters["expense_safe_already_present"] += 1
                continue
            row = sqlite_row(source_dir, m["db"], "saidas_operacionais", int(m["legacy_id"]))
            session.add(make_expense_entry(row, m, actor))
            counters["expense_safe_missing_create"] += 1
            details.append({"action": "create_missing_safe_expense", "marker": tag, "amount": str(m["amount"]), "date": m["posting_corrected"]})

        # 1) Receitas com datas inválidas recuperadas deterministicamente.
        for m in recover_income:
            tag = marker(m["db"], "faturamento_bradesco", int(m["legacy_id"]))
            existing = await find_entry_by_marker(session, tag)
            if existing:
                counters["income_recover_already_present"] += 1
                continue
            row = sqlite_row(source_dir, m["db"], "faturamento_bradesco", int(m["legacy_id"]))
            session.add(make_income_entry(row, m, actor))
            counters["income_recover_create"] += 1
            details.append({"action": "create_income_recovered_date", "marker": tag, "amount": str(m["amount"]), "date": m["issue_corrected"]})

        # 2) Despesas com datas inválidas recuperadas deterministicamente.
        for m in recover_expense:
            tag = marker(m["db"], "saidas_operacionais", int(m["legacy_id"]))
            existing = await find_entry_by_marker(session, tag)
            if existing:
                counters["expense_recover_already_present"] += 1
                continue
            row = sqlite_row(source_dir, m["db"], "saidas_operacionais", int(m["legacy_id"]))
            session.add(make_expense_entry(row, m, actor))
            counters["expense_recover_create"] += 1
            details.append({"action": "create_expense_recovered_date", "marker": tag, "amount": str(m["amount"]), "date": m["posting_corrected"]})

        await session.flush()

        # 3) Duplicidades exatas auditadas. Parcelas com vencimentos diferentes não entram neste manifesto.
        for m in dup_remove:
            tag = marker(m["db"], "faturamento_bradesco", int(m["legacy_id"]))
            entry = await find_entry_by_marker(session, tag)
            if not entry:
                counters["duplicate_marker_absent"] += 1
                continue
            if entry.is_deleted:
                counters["duplicate_already_deleted"] += 1
                continue
            entry.is_deleted = True
            entry.deleted_at = datetime.now(timezone.utc)
            suffix = "[RECONCILIADO 2026-08-24: duplicidade exata desativada; mesma NF, emissão, vencimento, cliente e valor]"
            entry.notes = combine_notes(entry.notes, suffix)
            counters["duplicate_soft_delete"] += 1
            details.append({"action": "soft_delete_duplicate", "marker": tag, "entry_id": entry.id, "amount": str(entry.amount)})

        await session.flush()

        # 4) Financeiro -> Laboratório. Revalida estado atual antes de mudar a OS.
        for m in lab_rows:
            wo_number = str(m["os"]).strip()
            wo = (
                await session.execute(select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.number.in_([wo_number, f"OS-{wo_number}"])))
            ).scalars().first()
            if not wo:
                counters["lab_missing_work_order"] += 1
                continue
            if wo.status == "warranty":
                counters["lab_skip_warranty"] += 1
                continue
            if wo.status == "invoiced":
                counters["lab_already_invoiced"] += 1
                continue
            issue = parse_iso(m["issue"])
            if wo.opened_at and issue < wo.opened_at:
                counters["lab_skip_chronology"] += 1
                details.append({"action": "skip_lab_chronology", "os": wo.number, "issue": str(issue), "opened_at": str(wo.opened_at)})
                continue
            if not names_compatible(m["finance_client"], wo.customer_name):
                counters["lab_skip_customer_mismatch"] += 1
                details.append({"action": "skip_lab_customer", "os": wo.number, "finance_client": m["finance_client"], "lab_client": wo.customer_name})
                continue
            finance_tag = marker(m["finance_db"], "faturamento_bradesco", int(float(m["finance_rowid"])))
            finance_entry = await find_entry_by_marker(session, finance_tag)
            if not finance_entry or finance_entry.is_deleted:
                counters["lab_skip_finance_entry_missing"] += 1
                details.append({"action": "skip_lab_missing_finance", "os": wo.number, "marker": finance_tag})
                continue

            previous = wo.status
            wo.status = "invoiced"
            wo.invoiced_at = datetime.combine(issue, time(hour=12), tzinfo=timezone.utc)
            if str(m.get("link_count", "1")).strip() in {"1", "1.0"} and finance_entry.work_order_id is None:
                finance_entry.work_order_id = wo.id
            session.add(
                LaboratoryStatusHistory(
                    work_order_id=wo.id,
                    previous_status=previous,
                    new_status="invoiced",
                    note=f"Conciliação automática com faturamento legado {m.get('nfs') or ''} em {issue.strftime('%d/%m/%Y')}.",
                    user_id=actor,
                    created_at=datetime.combine(issue, time(hour=12), tzinfo=timezone.utc),
                )
            )
            counters["lab_mark_invoiced"] += 1
            details.append({"action": "mark_lab_invoiced", "os": wo.number, "previous": previous, "issue": str(issue), "marker": finance_tag})

        await session.flush()
        after = await monthly_totals(session)

        # 5) Diagnóstico de cobertura da fonte e lançamentos locais sem marcador legado.
        coverage, unmarked_rows, duplicate_candidates = await source_coverage_for_period(session, args.target_period, expected)
        counters["target_period_unmarked_entries"] = len(unmarked_rows)
        counters["target_period_unmarked_exact_duplicate_candidates"] = len(duplicate_candidates)

        periods = sorted({(k[0], k[2]) for k in set(before) | set(after) if k[2] >= "2023-01"})
        monthly_rows = []
        for company, period in periods:
            bi = before.get((company, "income", period), Decimal("0"))
            be = before.get((company, "expense", period), Decimal("0"))
            ai = after.get((company, "income", period), Decimal("0"))
            ae = after.get((company, "expense", period), Decimal("0"))
            if bi != ai or be != ae or period == args.target_period:
                monthly_rows.append({
                    "company": company,
                    "period": period,
                    "income_before": str(bi),
                    "income_after_plan": str(ai),
                    "expense_before": str(be),
                    "expense_after_plan": str(ae),
                    "net_after_plan": str(ai - ae),
                })

        write_csv(out_dir / "plan_details.csv", details, ["action"])
        write_csv(out_dir / "monthly_after_plan.csv", monthly_rows, ["company", "period"])
        write_csv(out_dir / "source_coverage.csv", coverage, ["company", "entry_type", "period"])
        write_csv(out_dir / "unmarked_entries.csv", unmarked_rows, ["id", "company", "entry_type"])
        write_csv(out_dir / "unmarked_exact_duplicate_candidates.csv", duplicate_candidates, ["unmarked_entry_id", "legacy_entry_id"])
        (out_dir / "summary.json").write_text(json.dumps(dict(counters), ensure_ascii=False, indent=2), encoding="utf-8")

        print("\nNEXUS - CONCILIAÇÃO FINANCEIRA 2026-08-24 / V11")
        print("Modo:", "APLICAR" if args.apply else "DRY-RUN")
        print("Regras: mesma NF + vencimento diferente = MANTER; transferências internas = MANTER.")
        print("Sincronização: somente registros auditados como legítimos e ausentes pelo marcador LEGACY.")
        for key, value in sorted(counters.items()):
            print(f"{key:48} {value}")

        print(f"\nCobertura da fonte em {args.target_period}:")
        for row in coverage:
            if row["entry_type"] == "income":
                print(
                    f"  {row['company']:24} esperado legado {row['expected_legacy']:>12}  "
                    f"marcado {row['legacy_marked_after_plan']:>12}  sem marcador {row['unmarked_after_plan']:>12}  "
                    f"gap legado {row['legacy_gap']:>12}  total {row['total_after_plan']:>12}"
                )

        print(f"\n{args.target_period} após o plano:")
        for row in monthly_rows:
            if row["period"] == args.target_period:
                print(
                    f"  {row['company']:24} receitas {row['income_after_plan']:>12}  "
                    f"despesas {row['expense_after_plan']:>12}  resultado {row['net_after_plan']:>12}"
                )

        if duplicate_candidates:
            print("\nATENÇÃO: existem lançamentos locais sem marcador que coincidem exatamente com um lançamento LEGACY.")
            print("Eles NÃO serão excluídos automaticamente. Consulte unmarked_exact_duplicate_candidates.csv.")

        print("\nRelatórios:", out_dir)

        if args.apply:
            # Segurança adicional: não permite aplicar enquanto a fonte auditada ainda tiver gap no período alvo.
            legacy_gaps = [r for r in coverage if Decimal(r["legacy_gap"]) != Decimal("0.00")]
            if legacy_gaps:
                await session.rollback()
                print("APLICAÇÃO BLOQUEADA: ainda existe gap entre a fonte auditada e os lançamentos LEGACY marcados.")
                return 3
            await session.commit()
            print("APLICAÇÃO CONCLUÍDA E COMMITADA.")
        else:
            await session.rollback()
            print("DRY-RUN CONCLUÍDO. NENHUMA ALTERAÇÃO FOI GRAVADA.")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Concilia o Financeiro legado e baixa OS faturadas com regras auditadas.")
    p.add_argument("--source-dir", default="/legacy/reconcile_20260824")
    p.add_argument("--data-dir", default=None)
    p.add_argument("--report-dir", default="/app/storage/finance_reconcile_20260824")
    p.add_argument("--target-period", default="2026-08", help="Período YYYY-MM usado no diagnóstico detalhado de cobertura.")
    p.add_argument("--apply", action="store_true")
    return p


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parser().parse_args())))
