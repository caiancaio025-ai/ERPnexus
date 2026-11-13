from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path


BASE = Path(__file__).resolve().parents[1] / "scripts" / "finance_reconcile_data"


def rows(name: str):
    with (BASE / name).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_manifest_expected_counts():
    assert len(rows("recover_income.csv")) == 30
    assert len(rows("recover_expense.csv")) == 27
    assert len(rows("income_duplicates_remove.csv")) == 10
    assert len(rows("lab_mark_invoiced.csv")) == 354
    assert len(rows("income_safe_all.csv")) == 1218
    assert len(rows("expense_safe_all.csv")) == 2985


def test_recovered_rows_have_corrected_dates():
    assert all(r["issue_corrected"] and r["due_corrected"] for r in rows("recover_income.csv"))
    assert all(r["posting_corrected"] and r["issue_corrected"] for r in rows("recover_expense.csv"))


def test_lab_candidates_are_chronologically_valid():
    for row in rows("lab_mark_invoiced.csv"):
        if row["entry"]:
            assert date.fromisoformat(row["issue"]) >= date.fromisoformat(row["entry"])


def test_same_invoice_different_due_is_preserved():
    safe = rows("income_safe_all.csv")
    installments = [
        r for r in safe
        if r["db"] == "banco_automacao.db" and r["nfs"] == "55" and r["legacy_id"] in {"1028", "1029"}
    ]
    assert len(installments) == 2
    assert {r["due_corrected"] for r in installments} == {"2026-09-18", "2026-10-19"}
    duplicate_ids = {(r["db"], r["legacy_id"]) for r in rows("income_duplicates_remove.csv")}
    assert ("banco_automacao.db", "1028") not in duplicate_ids
    assert ("banco_automacao.db", "1029") not in duplicate_ids


def test_late_august_rows_are_in_safe_source_manifest():
    safe = rows("income_safe_all.csv")
    by_db_id = {(r["db"], int(r["legacy_id"])): r for r in safe}

    empresa_ids = [843, 845, 846, 847]
    automacao_ids = [1028, 1029, 1030, 1031, 1032, 1033]
    assert all(("banco_empresa.db", i) in by_db_id for i in empresa_ids)
    assert all(("banco_automacao.db", i) in by_db_id for i in automacao_ids)

    empresa_sum = sum(Decimal(by_db_id[("banco_empresa.db", i)]["amount"]) for i in empresa_ids)
    automacao_sum = sum(Decimal(by_db_id[("banco_automacao.db", i)]["amount"]) for i in automacao_ids)
    assert empresa_sum == Decimal("21723.65")
    assert automacao_sum == Decimal("112667.30")


def test_august_2026_expected_income_matches_latest_audited_sqlite():
    totals = defaultdict(lambda: Decimal("0.00"))
    for row in [*rows("income_safe_all.csv"), *rows("recover_income.csv")]:
        if row["issue_corrected"].startswith("2026-08"):
            totals[row["company"]] += Decimal(row["amount"])

    assert totals["universo_eletronica"] == Decimal("282463.55")
    assert totals["universo_automacao"] == Decimal("221516.14")
    assert totals["solucoes_eletronica"] == Decimal("2465.00")


def test_internal_transfers_are_kept_in_safe_manifest():
    safe = rows("income_safe_all.csv")
    transfers = [r for r in safe if r["action"] == "separate_transfer"]
    assert len(transfers) == 7
    assert sum(Decimal(r["amount"]) for r in transfers) == Decimal("250000.00")
