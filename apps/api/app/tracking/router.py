from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.laboratory.models import (
    LaboratoryStatusHistory,
    LaboratoryTechnician,
    LaboratoryWorkOrder,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]

_STATUS_LABELS = {
    "received": "Recebido",
    "awaiting_analysis": "Aguardando análise",
    "in_analysis": "Em análise",
    "awaiting_quote": "Aguardando orçamento",
    "quote_sent": "Orçamento enviado",
    "awaiting_approval": "Aguardando aprovação",
    "approved": "Aprovado",
    "rejected": "Reprovado",
    "awaiting_parts": "Aguardando peças",
    "in_repair": "Em reparo",
    "in_testing": "Em testes",
    "completed": "Concluído",
    "awaiting_pickup": "Aguardando retirada",
    "delivered": "Entregue",
    "cancelled": "Cancelado",
    "no_repair": "Sem reparo",
}


def _page(title: str, body: str, *, status_code: int = 200) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>{escape(title)} · NEXUS</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, Arial, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #06101e; color: #eaf3fb; }}
    main {{ width: min(760px, calc(100% - 32px)); margin: 0 auto; padding: 40px 0; }}
    .brand {{ color: #65b8ff; font-size: 12px; font-weight: 800; letter-spacing: .16em; }}
    .card {{ margin-top: 16px; background: #0d1c2e; border: 1px solid #1d3854;
      border-radius: 18px; padding: 24px; box-shadow: 0 24px 70px rgba(0,0,0,.28); }}
    h1 {{ margin: 4px 0 8px; font-size: clamp(24px, 5vw, 34px); }}
    .muted {{ color: #91a9c1; }}
    .status {{ display: inline-flex; margin: 14px 0 22px; padding: 7px 12px;
      border: 1px solid #315173; border-radius: 999px; color: #dcecff; font-weight: 700; }}
    dl {{ display: grid; grid-template-columns: 180px 1fr; gap: 0; margin: 0; }}
    dt, dd {{ margin: 0; padding: 13px 0; border-bottom: 1px solid #172d45; }}
    dt {{ color: #8fa6bd; }}
    dd {{ font-weight: 650; overflow-wrap: anywhere; }}
    footer {{ margin-top: 18px; color: #6f879f; font-size: 12px; }}
    @media (max-width: 560px) {{
      dl {{ grid-template-columns: 1fr; }}
      dt {{ padding-bottom: 2px; border: 0; }}
      dd {{ padding-top: 2px; }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="brand">NEXUS · RASTREABILIDADE</div>
    {body}
    <footer>Consulta pública protegida por token. Nenhum dado técnico interno é exibido.</footer>
  </main>
</body>
</html>"""
    return HTMLResponse(html, status_code=status_code, headers={"Cache-Control": "no-store"})


@router.get("/e/{tracking_token}", response_class=HTMLResponse, include_in_schema=False)
async def public_work_order_tracking(
    tracking_token: str,
    db: DbSession,
) -> HTMLResponse:
    if len(tracking_token) not in {16, 32}:
        return _page(
            "Rastreamento não encontrado",
            '<section class="card"><h1>Consulta não encontrada</h1>'
            '<p class="muted">Confira o QR Code ou solicite uma nova etiqueta.</p></section>',
            status_code=404,
        )

    work_order = await db.scalar(
        select(LaboratoryWorkOrder).where(
            LaboratoryWorkOrder.tracking_token == tracking_token
        )
    )
    if not work_order:
        return _page(
            "Rastreamento não encontrado",
            '<section class="card"><h1>Consulta não encontrada</h1>'
            '<p class="muted">Confira o QR Code ou solicite uma nova etiqueta.</p></section>',
            status_code=404,
        )

    last_technician = await db.scalar(
        select(LaboratoryTechnician.name)
        .join(
            LaboratoryStatusHistory,
            LaboratoryStatusHistory.user_id == LaboratoryTechnician.user_id,
        )
        .where(LaboratoryStatusHistory.work_order_id == work_order.id)
        .order_by(LaboratoryStatusHistory.created_at.desc())
        .limit(1)
    )
    if not last_technician and work_order.technician:
        last_technician = work_order.technician.name

    equipment = work_order.equipment
    status_label = _STATUS_LABELS.get(work_order.status, work_order.status)
    opened_at = work_order.opened_at.strftime("%d/%m/%Y")
    equipment_name = " / ".join(
        value
        for value in (
            equipment.equipment_type if equipment else None,
            equipment.manufacturer if equipment else None,
            equipment.model if equipment else None,
        )
        if value
    ) or "Não informado"

    body = f"""
<section class="card">
  <p class="muted">Ordem de Serviço</p>
  <h1>{escape(work_order.number)}</h1>
  <span class="status">{escape(status_label)}</span>
  <dl>
    <dt>Cliente</dt><dd>{escape(work_order.customer_name)}</dd>
    <dt>Data de entrada</dt><dd>{escape(opened_at)}</dd>
    <dt>Equipamento</dt><dd>{escape(equipment_name)}</dd>
    <dt>Número de série</dt><dd>{escape(work_order.equipment_serial or "Não informado")}</dd>
    <dt>Último técnico</dt><dd>{escape(last_technician or "Ainda não atribuído")}</dd>
    <dt>Status atual</dt><dd>{escape(status_label)}</dd>
  </dl>
</section>"""
    return _page(f"OS {work_order.number}", body)
