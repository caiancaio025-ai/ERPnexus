from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select

from app.auth.models import User
from app.core.db import session_factory
from app.finance.models import FinancialEntry
from app.laboratory.models import (
    LaboratoryCustomer,
    LaboratoryEquipment,
    LaboratoryQuote,
    LaboratoryQuoteItem,
    LaboratoryStatusHistory,
    LaboratoryTechnician,
    LaboratoryWorkOrder,
)
from app.purchasing.models import PurchaseOrder, Supplier

LAB_DB = "banco_laboratorio.db"
FINANCE_DBS = {
    "banco_empresa.db": "universo_eletronica",
    "banco_automacao.db": "universo_automacao",
    "banco_solucoes.db": "solucoes_eletronica",
}
PURCHASE_DB = "banco_compras.db"
IGNORED_DBS = {"banco_equipamentos.db", "banco_estoque.db"}

COMPANY_BY_LABEL = {
    "universo eletrônica industrial": "universo_eletronica",
    "universo eletronica industrial": "universo_eletronica",
    "universo automação industrial": "universo_automacao",
    "universo automacao industrial": "universo_automacao",
    "soluções eletrônicas": "solucoes_eletronica",
    "solucoes eletronicas": "solucoes_eletronica",
}

STATUS_MAP = {
    "entrada": "received",
    "ag. aprovação": "awaiting_approval",
    "ag aprovacao": "awaiting_approval",
    "ag. aprovacao": "awaiting_approval",
    "aguardando aprovação": "awaiting_approval",
    "aguardando aprovacao": "awaiting_approval",
    "analisado": "in_analysis",
    "aprovado": "approved",
    "sem conserto": "no_repair",
    "pronto": "completed",
    "liberado": "awaiting_pickup",
    "garantia": "warranty",
    "faturado": "invoiced",
    "em reparo": "in_repair",
    "cancelado": "cancelled",
}

FIN_STATUS_MAP = {
    "PAGO": ("received", "paid"),
    "EM ABERTO": ("pending", "pending"),
    "ATRASADO": ("pending", "pending"),
}

PURCHASE_STATUS_MAP = {
    "entregue": "delivered",
    "a caminho": "in_transit",
    "comprado": "purchased",
    "aguardando pagamento": "awaiting_payment",
}

INVALID_TEXT = {"", "-", "--", "---", "s/n", "sn", "snf", "n/a", "none", "null"}


@dataclass
class Report:
    counters: Counter = field(default_factory=Counter)
    issues: list[dict[str, Any]] = field(default_factory=list)

    def inc(self, key: str, n: int = 1) -> None:
        self.counters[key] += n

    def issue(self, source: str, row_id: Any, field_name: str, value: Any, reason: str) -> None:
        self.issues.append(
            {
                "source": source,
                "row_id": row_id,
                "field": field_name,
                "value": "" if value is None else str(value),
                "reason": reason,
            }
        )

    def write(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["metrica", "quantidade"])
            for key, value in sorted(self.counters.items()):
                w.writerow([key, value])
        with (output_dir / "issues.csv").open("w", newline="", encoding="utf-8-sig") as fh:
            fields = ["source", "row_id", "field", "value", "reason"]
            w = csv.DictWriter(fh, fieldnames=fields, delimiter=";")
            w.writeheader()
            w.writerows(self.issues)


def txt(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s.casefold() in INVALID_TEXT:
        return None
    return s


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", (txt(value) or "").strip()).casefold()


def digits(value: Any) -> str | None:
    s = re.sub(r"\D", "", str(value or ""))
    return s or None


def money(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.replace("R$", "").replace(" ", "")
            if "," in value and "." in value:
                value = value.replace(".", "").replace(",", ".")
            elif "," in value:
                value = value.replace(",", ".")
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    s = txt(value)
    if not s:
        return None
    candidates = (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%Y/%m/%d",
    )
    for fmt in candidates:
        try:
            d = datetime.strptime(s, fmt).date()
            if 2000 <= d.year <= 2100:
                return d
            return None
        except ValueError:
            pass
    return None


def parse_datetime(value: Any) -> datetime | None:
    s = txt(value)
    if not s:
        return None
    for fmt in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    d = parse_date(s)
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc) if d else None


def source_conn(path: Path) -> sqlite3.Connection:
    # Os bancos legados sao montados no container como somente leitura.
    # Abrir explicitamente em mode=ro evita tentativas do SQLite de criar
    # journal/WAL ao lado do arquivo em bind mounts read-only (Docker/Windows).
    resolved = path.resolve()
    uri = f"file:{resolved.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def company_code(label: Any) -> str:
    n = norm(label)
    if n in COMPANY_BY_LABEL:
        return COMPANY_BY_LABEL[n]
    if "autom" in n:
        return "universo_automacao"
    if "solu" in n:
        return "solucoes_eletronica"
    return "universo_eletronica"


def map_lab_status(value: Any) -> str:
    return STATUS_MAP.get(norm(value), "received")


def quote_status(value: Any) -> str:
    n = norm(value)
    return "emitted" if n and n not in {"rascunho", "draft"} else "draft"


def marker(source: str, table: str, row_id: Any) -> str:
    return f"[LEGACY {source}.{table}#{row_id}]"


def combine_notes(*parts: Any) -> str | None:
    values = [txt(x) for x in parts]
    values = [x for x in values if x]
    return "\n\n".join(values) if values else None


async def get_actor_id(session) -> int:
    result = await session.execute(
        select(User).where(User.is_active.is_(True)).order_by(
            (User.role == "super_admin").desc(),
            (User.role == "admin").desc(),
            User.id.asc(),
        )
    )
    user = result.scalars().first()
    if not user:
        raise RuntimeError("Nenhum usuário ativo encontrado. Crie o usuário administrador antes da importação.")
    return user.id


async def find_or_create_customer(
    session,
    report: Report,
    actor_id: int,
    company: str,
    name: str,
    document: str | None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
) -> LaboratoryCustomer:
    clauses = []
    if document:
        clauses.append(LaboratoryCustomer.document == document)
    clauses.append(func.lower(LaboratoryCustomer.legal_name) == name.casefold())
    result = await session.execute(
        select(LaboratoryCustomer).where(
            LaboratoryCustomer.company_code == company,
            or_(*clauses),
        )
    )
    customer = result.scalars().first()
    if customer:
        changed = False
        for attr, value in (("email", email), ("phone", phone), ("address", address), ("document", document)):
            if value and not getattr(customer, attr):
                setattr(customer, attr, value)
                changed = True
        report.inc("customers_updated" if changed else "customers_existing")
        return customer
    customer = LaboratoryCustomer(
        company_code=company,
        document=document,
        legal_name=name[:180],
        trade_name=name[:180],
        email=email,
        phone=phone,
        address=address,
        created_by=actor_id,
    )
    session.add(customer)
    await session.flush()
    report.inc("customers_created")
    return customer


async def import_laboratory(session, source_dir: Path, report: Report, actor_id: int, apply: bool) -> None:
    path = source_dir / LAB_DB
    if not path.exists():
        report.issue(LAB_DB, "-", "file", path, "arquivo não encontrado")
        return
    conn = source_conn(path)

    client_rows = {digits(r["CNPJ"]): r for r in conn.execute("SELECT * FROM clientes_lab") if digits(r["CNPJ"])}
    wo_rows = list(conn.execute("SELECT * FROM equipamentos_os ORDER BY ID"))
    companies_by_client: dict[tuple[str, str], str] = {}
    for r in wo_rows:
        key = (digits(r["CNPJ_CLIENTE"]) or "", norm(r["CLIENTE"]))
        companies_by_client[key] = company_code(r["EMPRESA_EMITE"])

    # Clientes cadastrados, inclusive os que ainda não têm OS.
    for r in conn.execute("SELECT * FROM clientes_lab ORDER BY ID"):
        name = txt(r["NOME"])
        if not name:
            report.issue(LAB_DB, r["ID"], "NOME", r["NOME"], "cliente sem nome")
            continue
        doc = digits(r["CNPJ"])
        company = companies_by_client.get((doc or "", norm(name)), "universo_eletronica")
        if apply:
            await find_or_create_customer(
                session, report, actor_id, company, name, doc, txt(r["EMAIL"]), txt(r["TELEFONE"]), txt(r["ENDERECO"])
            )
        else:
            report.inc("customers_candidate")

    technician_cache: dict[tuple[str, str], int] = {}
    work_order_cache: dict[str, int] = {}

    for r in wo_rows:
        source_id = r["ID"]
        number = txt(r["OS_NUM"])
        customer_name = txt(r["CLIENTE"]) or "CLIENTE NÃO INFORMADO"
        if not number:
            report.issue(LAB_DB, source_id, "OS_NUM", r["OS_NUM"], "OS sem número; ignorada")
            continue
        opened = parse_date(r["DATA_ENTRADA"])
        if not opened:
            report.issue(LAB_DB, source_id, "DATA_ENTRADA", r["DATA_ENTRADA"], "data inválida; OS ignorada")
            report.inc("work_orders_skipped_invalid_date")
            continue
        company = company_code(r["EMPRESA_EMITE"])
        doc = digits(r["CNPJ_CLIENTE"])
        client_extra = client_rows.get(doc)

        if not apply:
            report.inc("work_orders_candidate")
            continue

        existing = (await session.execute(select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.number == number))).scalars().first()
        if existing:
            work_order_cache[number] = existing.id
            report.inc("work_orders_existing")
            continue

        customer = await find_or_create_customer(
            session,
            report,
            actor_id,
            company,
            customer_name,
            doc,
            txt(client_extra["EMAIL"]) if client_extra else None,
            txt(client_extra["TELEFONE"]) if client_extra else None,
            txt(client_extra["ENDERECO"]) if client_extra else None,
        )

        eq_marker = f"LEGACY-LAB-{source_id}"
        equipment = (
            await session.execute(
                select(LaboratoryEquipment).where(
                    LaboratoryEquipment.company_code == company,
                    LaboratoryEquipment.serial_normalized == eq_marker,
                )
            )
        ).scalars().first()
        if not equipment:
            equipment = LaboratoryEquipment(
                company_code=company,
                customer_id=customer.id,
                customer_name=customer_name[:180],
                serial_number=None,
                serial_normalized=eq_marker,
                manufacturer=None,
                model=txt(r["MODELO"]),
                equipment_type=txt(r["EQUIPAMENTO"]),
                power=txt(r["POTENCIA"]),
                voltage=txt(r["TENSAO"]),
                notes=combine_notes(
                    marker(LAB_DB, "equipamentos_os", source_id),
                    f"Corrente legada: {txt(r['CORRENTE'])}" if txt(r["CORRENTE"]) else None,
                ),
                created_by=actor_id,
            )
            session.add(equipment)
            await session.flush()
            report.inc("equipment_created_from_work_orders")

        technician_id = None
        tech_name = txt(r["TECNICO"])
        if tech_name and norm(tech_name) not in {"n/a", "na"}:
            tkey = (company, norm(tech_name))
            technician_id = technician_cache.get(tkey)
            if not technician_id:
                technician = (
                    await session.execute(
                        select(LaboratoryTechnician).where(
                            LaboratoryTechnician.company_code == company,
                            func.lower(LaboratoryTechnician.name) == tech_name.casefold(),
                        )
                    )
                ).scalars().first()
                if not technician:
                    technician = LaboratoryTechnician(company_code=company, name=tech_name[:160], created_by=actor_id)
                    session.add(technician)
                    await session.flush()
                    report.inc("technicians_created")
                technician_id = technician.id
                technician_cache[tkey] = technician_id

        status = map_lab_status(r["STATUS"])
        exit_date = parse_date(r["DATA_SAIDA"])
        end_dt = datetime.combine(exit_date, datetime.min.time(), tzinfo=timezone.utc) if exit_date else None
        wo = LaboratoryWorkOrder(
            number=number[:30],
            company_code=company,
            equipment_id=equipment.id,
            customer_id=customer.id,
            customer_name=customer_name[:180],
            equipment_serial=None,
            status=status,
            priority="normal",
            reported_defect="Não informado no cadastro legado.",
            assigned_technician_id=technician_id,
            opened_at=opened,
            completed_at=end_dt if status in {"completed", "awaiting_pickup", "delivered", "invoiced", "no_repair"} else None,
            delivered_at=end_dt if status in {"delivered", "invoiced"} else None,
            invoiced_at=end_dt if status == "invoiced" else None,
            internal_notes=combine_notes(
                marker(LAB_DB, "equipamentos_os", source_id),
                f"Compras: {txt(r['OBS_COMPRAS'])}" if txt(r["OBS_COMPRAS"]) else None,
                f"Saída: {txt(r['OBS_SAIDA'])}" if txt(r["OBS_SAIDA"]) else None,
                f"Garantia: {txt(r['OBS_GARANTIA'])}" if txt(r["OBS_GARANTIA"]) else None,
            ),
            entry_invoice=txt(r["NF_ENTRADA"]),
            exit_invoice=txt(r["NF_SAIDA"]),
            parts_cost=money(r["VALOR_PECAS"]),
            quoted_value=money(r["VALOR_ORCAMENTO"]),
            approved_value=money(r["VALOR_ORCAMENTO"]) if status in {"approved", "awaiting_parts", "in_repair", "completed", "awaiting_pickup", "delivered", "invoiced"} else None,
            is_cancelled=status == "cancelled",
            created_by=actor_id,
        )
        session.add(wo)
        await session.flush()
        work_order_cache[number] = wo.id
        report.inc("work_orders_created")

    # Histórico de status legado.
    for r in conn.execute("SELECT * FROM historico_status ORDER BY ID"):
        number = txt(r["OS_NUM"])
        if not number or not apply:
            if number:
                report.inc("status_history_candidate")
            continue
        wo_id = work_order_cache.get(number)
        if not wo_id:
            wo = (await session.execute(select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.number == number))).scalars().first()
            wo_id = wo.id if wo else None
        if not wo_id:
            report.issue(LAB_DB, r["ID"], "OS_NUM", number, "histórico sem OS correspondente")
            continue
        note_marker = marker(LAB_DB, "historico_status", r["ID"])
        exists = (
            await session.execute(
                select(LaboratoryStatusHistory.id).where(
                    LaboratoryStatusHistory.work_order_id == wo_id,
                    LaboratoryStatusHistory.note == note_marker,
                )
            )
        ).scalar_one_or_none()
        if exists:
            report.inc("status_history_existing")
            continue
        ev = LaboratoryStatusHistory(
            work_order_id=wo_id,
            previous_status=map_lab_status(r["STATUS_ANT"]) if txt(r["STATUS_ANT"]) else None,
            new_status=map_lab_status(r["STATUS_NOVO"]),
            note=note_marker,
            user_id=actor_id,
        )
        dt = parse_datetime(r["DATA_HORA"])
        if dt:
            ev.created_at = dt
        session.add(ev)
        report.inc("status_history_created")

    # Orçamentos e itens.
    revision_by_wo: dict[int, int] = defaultdict(int)
    for r in conn.execute("SELECT * FROM orcamentos ORDER BY OS_NUM, ID"):
        number = txt(r["OS_NUM"])
        if not number:
            continue
        if not apply:
            report.inc("quotes_candidate")
            continue
        wo_id = work_order_cache.get(number)
        if not wo_id:
            wo = (await session.execute(select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.number == number))).scalars().first()
            wo_id = wo.id if wo else None
        if not wo_id:
            report.issue(LAB_DB, r["ID"], "OS_NUM", number, "orçamento sem OS correspondente")
            continue
        q_marker = marker(LAB_DB, "orcamentos", r["ID"])
        exists = (
            await session.execute(
                select(LaboratoryQuote.id).where(
                    LaboratoryQuote.work_order_id == wo_id,
                    LaboratoryQuote.services_description.ilike(f"%{q_marker}%"),
                )
            )
        ).scalar_one_or_none()
        if exists:
            report.inc("quotes_existing")
            continue
        if not revision_by_wo[wo_id]:
            max_rev = (
                await session.execute(select(func.max(LaboratoryQuote.revision)).where(LaboratoryQuote.work_order_id == wo_id))
            ).scalar_one_or_none()
            revision_by_wo[wo_id] = int(max_rev or 0)
        revision_by_wo[wo_id] += 1
        total = money(r["VALOR_NEGOCIADO"]) or money(r["VALOR"]) or Decimal("0.00")
        legacy_conditions = txt(r["OBS_SAIDA"]) or ""
        payment_terms = "Não informado no sistema legado."
        return_condition = "Não informada no sistema legado."
        for raw_line in legacy_conditions.splitlines():
            line = raw_line.strip().lstrip("●•- ").strip()
            upper = line.upper()
            if upper.startswith("PAGAMENTO:"):
                payment_terms = line.split(":", 1)[1].strip() or payment_terms
            elif upper.startswith("ORÇAMENTO NÃO APROVADO") or upper.startswith("ORCAMENTO NAO APROVADO"):
                return_condition = line

        quote = LaboratoryQuote(
            work_order_id=wo_id,
            revision=revision_by_wo[wo_id],
            status=quote_status(r["STATUS_OS"]),
            technical_report=txt(r["LAUDO"]) or "Sem laudo técnico no registro legado.",
            services_description=combine_notes(q_marker, txt(r["RESUMO_TECNICO"]), legacy_conditions),
            payment_terms=payment_terms[:500],
            return_condition=return_condition[:500],
            consumer_clause="Condição não informada no sistema legado.",
            supply_clause="Condição não informada no sistema legado.",
            estimate_clause="Condição não informada no sistema legado.",
            subtotal=money(r["VALOR"]) or total,
            total=total,
            emitted_at=parse_datetime(r["DATA_EMISSAO"]),
            created_by=actor_id,
        )
        session.add(quote)
        await session.flush()
        raw_items = txt(r["ITENS_JSON"])
        items: list[dict[str, Any]] = []
        if raw_items:
            try:
                data = json.loads(raw_items)
                if isinstance(data, list):
                    items = [x for x in data if isinstance(x, dict)]
            except json.JSONDecodeError:
                report.issue(LAB_DB, r["ID"], "ITENS_JSON", raw_items[:120], "JSON inválido")
        if not items:
            items = [{"desc": "Serviço de manutenção", "qtd": 1, "vunit": total}]
        for pos, item in enumerate(items, start=1):
            desc = txt(item.get("desc")) or "Item importado"
            qty = money(item.get("qtd")) or Decimal("1.00")
            unit = money(item.get("vunit")) or Decimal("0.00")
            session.add(
                LaboratoryQuoteItem(
                    quote_id=quote.id,
                    position=pos,
                    description=desc[:500],
                    quantity=qty,
                    unit_value=unit,
                )
            )
        report.inc("quotes_created")
        report.inc("quote_items_created", len(items))
    conn.close()


async def import_finance(session, source_dir: Path, report: Report, actor_id: int, apply: bool) -> None:
    for filename, company in FINANCE_DBS.items():
        path = source_dir / filename
        if not path.exists():
            report.issue(filename, "-", "file", path, "arquivo não encontrado")
            continue
        conn = source_conn(path)
        for table, entry_type in (("faturamento_bradesco", "income"), ("saidas_operacionais", "expense")):
            rows = list(conn.execute(f'SELECT rowid AS __rowid__, * FROM "{table}"'))
            for r in rows:
                legacy_id = r["ID"] if "ID" in r.keys() else r["__rowid__"]
                tag = marker(filename, table, legacy_id)
                if not apply:
                    report.inc(f"finance_{entry_type}_candidate")
                    continue
                existing = (
                    await session.execute(select(FinancialEntry.id).where(FinancialEntry.notes.ilike(f"%{tag}%")))
                ).scalar_one_or_none()
                if existing:
                    report.inc(f"finance_{entry_type}_existing")
                    continue
                if entry_type == "income":
                    issue = parse_date(r["DATA_FAT"])
                    due = parse_date(r["DATA_VENC"])
                    amount = money(r["VALOR"])
                    if not issue or not due or not amount or amount <= 0:
                        report.issue(filename, legacy_id, "finance", f"{r['DATA_FAT']}|{r['DATA_VENC']}|{r['VALOR']}", "data/valor inválido; lançamento não importado")
                        report.inc("finance_rows_skipped")
                        continue
                    raw_status = (txt(r["STATUS"]) or "EM ABERTO").upper()
                    status = FIN_STATUS_MAP.get(raw_status, ("pending", "pending"))[0]
                    nfse = txt(r["NFS"])
                    nfe = txt(r["NFD"])
                    entry = FinancialEntry(
                        entry_type="income",
                        company_code=company,
                        invoice_type="nfse" if nfse and not nfe else ("nfe" if nfe and not nfse else None),
                        nfse_number=nfse,
                        nfe_number=nfe,
                        counterparty_name=(txt(r["CLIENTE"]) or "CLIENTE NÃO INFORMADO")[:180],
                        description=(f"Faturamento legado - orçamento {txt(r['ORCAMENTO'])}" if txt(r["ORCAMENTO"]) else "Faturamento legado")[:180],
                        amount=amount,
                        issue_date=issue,
                        posting_date=issue,
                        due_date=due,
                        settlement_date=None,
                        status=status,
                        bank_name=(txt(r["BANCO"]) or "Bradesco")[:80],
                        notes=combine_notes(tag, txt(r["OBSERVACAO"]), f"Orçamento legado: {txt(r['ORCAMENTO'])}" if txt(r["ORCAMENTO"]) else None, f"Emails legados: {', '.join(x for x in [txt(r['EMAIL1']), txt(r['EMAIL2']), txt(r['EMAIL3'])] if x)}" if any(txt(r[k]) for k in ["EMAIL1","EMAIL2","EMAIL3"]) else None),
                        created_by=actor_id,
                    )
                else:
                    posting = parse_date(r["DATA_SAIDA"])
                    issue = parse_date(r["DATA_EMISSAO"]) or posting
                    amount = money(r["VALOR"])
                    if not posting or not issue or not amount or amount <= 0:
                        report.issue(filename, legacy_id, "expense", f"{r['DATA_SAIDA']}|{r['DATA_EMISSAO']}|{r['VALOR']}", "data/valor inválido; lançamento não importado")
                        report.inc("finance_rows_skipped")
                        continue
                    raw_status = (txt(r["STATUS"]) or "EM ABERTO").upper()
                    status = FIN_STATUS_MAP.get(raw_status, ("pending", "pending"))[1]
                    entry = FinancialEntry(
                        entry_type="expense",
                        company_code=company,
                        counterparty_name=(txt(r["FORNECEDOR"]) or "FORNECEDOR NÃO INFORMADO")[:180],
                        description=(txt(r["SERVICO"]) or txt(r["CATEGORIA"]) or "Saída operacional legada")[:180],
                        amount=amount,
                        issue_date=issue,
                        posting_date=posting,
                        due_date=posting,
                        settlement_date=None,
                        status=status,
                        bank_name=(txt(r["BANCO"]) or "Bradesco")[:80],
                        expense_kind="supplier" if txt(r["FORNECEDOR"]) else "variable",
                        payment_code=txt(r["LINHA_DIGITAVEL"]),
                        notes=combine_notes(tag, txt(r["OBSERVACAO"]), f"Categoria legada: {txt(r['CATEGORIA'])}" if txt(r["CATEGORIA"]) else None, f"Anexo legado: {txt(r['ANEXO'])}" if txt(r["ANEXO"]) else None),
                        created_by=actor_id,
                    )
                session.add(entry)
                report.inc(f"finance_{entry_type}_created")
        conn.close()


async def import_purchases(session, source_dir: Path, report: Report, actor_id: int, apply: bool) -> None:
    path = source_dir / PURCHASE_DB
    if not path.exists():
        report.issue(PURCHASE_DB, "-", "file", path, "arquivo não encontrado")
        return
    conn = source_conn(path)
    supplier_cache: dict[str, int] = {}
    for r in conn.execute("SELECT rowid AS __rowid__, * FROM pedidos_compra"):
        rowid = r["__rowid__"]
        purchase_date = parse_date(r["DATA_COMPRA"])
        estimate = parse_date(r["PRAZO_ENTREGA"]) or purchase_date
        total_amount = money(r["VALOR"])

        # O NEXUS exige valor total estritamente positivo em purchase_orders.
        # O sistema legado possui compras históricas com VALOR = 0,00.
        # Não inventamos custo (por exemplo R$ 0,01), pois isso contaminaria
        # margem, custo por OS e indicadores financeiros. O registro é
        # preservado no relatório de inconsistências para saneamento manual.
        if total_amount is None or total_amount <= Decimal("0.00"):
            report.inc("purchases_skipped_nonpositive_amount")
            report.issue(
                PURCHASE_DB,
                rowid,
                "VALOR",
                r["VALOR"],
                "valor ausente/zero; compra não importada porque o NEXUS exige valor positivo",
            )
            continue

        if not purchase_date or not estimate:
            report.inc("purchases_skipped_invalid_date")
            report.issue(PURCHASE_DB, rowid, "DATA_COMPRA", r["DATA_COMPRA"], "data inválida; compra ignorada")
            continue

        if not apply:
            report.inc("purchases_candidate")
            continue
        tag = marker(PURCHASE_DB, "pedidos_compra", rowid)
        existing = (
            await session.execute(select(PurchaseOrder.id).where(PurchaseOrder.notes.ilike(f"%{tag}%")))
        ).scalar_one_or_none()
        if existing:
            report.inc("purchases_existing")
            continue
        supplier_name = txt(r["LOJA"]) or "Fornecedor legado"
        sid = supplier_cache.get(norm(supplier_name))
        if not sid:
            supplier = (
                await session.execute(select(Supplier).where(func.lower(Supplier.name) == supplier_name.casefold()))
            ).scalars().first()
            if not supplier:
                supplier = Supplier(name=supplier_name[:180], origin="international" if norm(r["ORIGEM"]) == "internacional" else "national")
                session.add(supplier)
                await session.flush()
                report.inc("suppliers_created")
            sid = supplier.id
            supplier_cache[norm(supplier_name)] = sid
        serial = txt(r["SERIE"])
        wo_id = None
        eq_id = None
        if serial:
            candidates = [serial, f"OS-{serial}"]
            wo = (
                await session.execute(select(LaboratoryWorkOrder).where(LaboratoryWorkOrder.number.in_(candidates)).limit(1))
            ).scalars().first()
            if wo:
                wo_id = wo.id
                eq_id = wo.equipment_id
        code = f"LEG-{purchase_date.strftime('%Y%m%d')}-{rowid:04d}"
        status = PURCHASE_STATUS_MAP.get(norm(r["STATUS"]), "awaiting_payment")
        delivered = estimate if status == "delivered" else None
        order = PurchaseOrder(
            code=code,
            company_code="universo_eletronica",
            supplier_id=sid,
            supplier_name=supplier_name[:180],
            laboratory_equipment_id=eq_id,
            laboratory_work_order_id=wo_id,
            equipment_serial=serial,
            client_destination=txt(r["CLIENTE"]),
            product_name=(txt(r["PRODUTO"]) or "Produto legado")[:250],
            quantity=max(int(r["QTD"] or 1), 1),
            total_amount=total_amount,
            origin="international" if norm(r["ORIGEM"]) == "internacional" else "national",
            tracking_code=txt(r["RASTREIO"]),
            purchase_date=purchase_date,
            estimated_delivery_date=estimate,
            delivered_at=delivered,
            status=status,
            notes=combine_notes(tag, txt(r["OBSERVACAO"])),
            created_by=actor_id,
        )
        session.add(order)
        report.inc("purchases_created")
    conn.close()


async def run(args: argparse.Namespace) -> int:
    source_dir = Path(args.source_dir).resolve()
    output_dir = Path(args.report_dir).resolve()
    report = Report()
    required = [LAB_DB, *FINANCE_DBS.keys(), PURCHASE_DB]
    missing = [name for name in required if not (source_dir / name).exists()]
    if missing:
        print("ERRO: arquivos ausentes em", source_dir)
        for name in missing:
            print(" -", name)
        return 2

    print("NEXUS - IMPORTAÇÃO DE LEGADO SQLITE")
    print("Fonte:", source_dir)
    print("Modo:", "APLICAR" if args.apply else "DRY-RUN (nenhuma gravação)")
    print("Ignorado por decisão do projeto: banco_equipamentos.db")
    print("Estoque vazio será ignorado: banco_estoque.db")

    async with session_factory() as session:
        actor_id = await get_actor_id(session)
        try:
            await import_laboratory(session, source_dir, report, actor_id, args.apply)
            await import_finance(session, source_dir, report, actor_id, args.apply)
            await import_purchases(session, source_dir, report, actor_id, args.apply)
            if args.apply:
                await session.commit()
            else:
                await session.rollback()
        except Exception:
            await session.rollback()
            raise

    report.write(output_dir)
    print("\nRESUMO")
    for key, value in sorted(report.counters.items()):
        print(f"{key:38} {value}")
    print(f"\nInconsistências registradas: {len(report.issues)}")
    print("Relatórios:", output_dir)
    if not args.apply:
        print("\nNenhuma alteração foi feita. Para importar de verdade, execute novamente com --apply.")
    else:
        print("\nImportação concluída. O processo é idempotente: uma nova execução não deve duplicar registros já marcados como legado.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Importa bancos SQLite legados para o PostgreSQL do NEXUS.")
    p.add_argument("--source-dir", default="/legacy", help="Diretório contendo os .db legados.")
    p.add_argument("--report-dir", default="/app/storage/legacy_import_report", help="Diretório para relatórios CSV.")
    p.add_argument("--apply", action="store_true", help="Efetiva a gravação. Sem esta flag o modo é apenas DRY-RUN.")
    return p


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run(build_parser().parse_args())))
    except KeyboardInterrupt:
        print("Importação cancelada.", file=sys.stderr)
        raise SystemExit(130)
