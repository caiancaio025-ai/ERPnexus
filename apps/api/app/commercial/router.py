import asyncio
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_view_sensitive_values
from app.auth.dependencies import require_general_admin, require_module
from app.auth.models import User
from app.auth.router import current_user
from app.commercial.label_pdf import commercial_label_pdf
from app.commercial.models import CommercialCompanyProfile, CommercialEquipment, CommercialPreventiveOrder, CommercialQuote, CommercialQuoteItem
from app.commercial.quote_pdf import commercial_quote_pdf
from app.commercial.schemas import CompanyProfileInput, CompanyProfileOutput, CommercialEquipmentInput, CommercialEquipmentOutput, CommercialQuoteInput, CommercialQuoteOutput, PreventiveOrderInput, PreventiveOrderOutput, PreventiveOrderUpdate, QuoteItemOutput, QuoteStatusInput
from app.core.db import get_db
from app.laboratory.models import LaboratoryCustomer

router = APIRouter(prefix="/commercial", dependencies=[Depends(require_module("comercial"))])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]

QUOTE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"issued", "cancelled"},
    "issued": {"approved", "rejected", "cancelled"},
    "approved": {"cancelled"},
    "rejected": set(),
    "cancelled": set(),
}


def _money_allowed(user: User) -> bool:
    return user_can_view_sensitive_values(user.role)


def _require_money(user: User) -> None:
    if not _money_allowed(user):
        raise HTTPException(status_code=403, detail="Somente Gestão pode visualizar ou alterar valores monetários.")


async def _equipment_or_404(db: AsyncSession, equipment_id: int) -> CommercialEquipment:
    item = await db.get(CommercialEquipment, equipment_id)
    if not item or not item.is_active:
        raise HTTPException(status_code=404, detail="Equipamento comercial não encontrado.")
    return item


async def _quote_or_404(db: AsyncSession, quote_id: int) -> CommercialQuote:
    quote = await db.get(CommercialQuote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento comercial não encontrado.")
    return quote


async def _quote_output(db: AsyncSession, quote: CommercialQuote, user: User) -> CommercialQuoteOutput:
    customer = await db.get(LaboratoryCustomer, quote.customer_id)
    items = list((await db.scalars(select(CommercialQuoteItem).where(CommercialQuoteItem.quote_id == quote.id).order_by(CommercialQuoteItem.sort_order, CommercialQuoteItem.id))).all())
    show_values = _money_allowed(user)
    return CommercialQuoteOutput(
        id=quote.id, quote_number=quote.quote_number or f"COM-{quote.id:06d}", quote_type=quote.quote_type,
        company_code=quote.company_code, customer_id=quote.customer_id, customer_name=customer.legal_name if customer else "Cliente removido",
        revision=quote.revision, status=quote.status, issue_date=quote.issue_date, valid_until=quote.valid_until, title=quote.title,
        intro_text=quote.intro_text, notes=quote.notes, payment_terms=quote.payment_terms, delivery_terms=quote.delivery_terms,
        warranty_terms=quote.warranty_terms, rental_terms=quote.rental_terms, preventive_scope=quote.preventive_scope, exclusions=quote.exclusions,
        total=float(quote.total) if show_values else None, issued_at=quote.issued_at, created_at=quote.created_at, updated_at=quote.updated_at,
        items=[QuoteItemOutput(id=i.id, equipment_id=i.equipment_id, description=i.description, manufacturer=i.manufacturer, model=i.model, power=i.power, voltage=i.voltage, serial_number=i.serial_number, quantity=float(i.quantity), unit=i.unit, unit_price=float(i.unit_price) if show_values else None, discount_pct=float(i.discount_pct), rental_period_count=i.rental_period_count, rental_period_unit=i.rental_period_unit, line_total=float(i.line_total) if show_values else None, sort_order=i.sort_order) for i in items],
    )


@router.get("/companies", response_model=list[CompanyProfileOutput])
async def list_companies(_: CurrentUser, db: DbSession):
    return list((await db.scalars(select(CommercialCompanyProfile).where(CommercialCompanyProfile.is_active.is_(True)).order_by(CommercialCompanyProfile.legal_name))).all())


@router.post("/companies", response_model=CompanyProfileOutput, status_code=201)
async def upsert_company(payload: CompanyProfileInput, user: CurrentUser, db: DbSession, _: User = Depends(require_general_admin)):
    row = await db.scalar(select(CommercialCompanyProfile).where(CommercialCompanyProfile.company_code == payload.company_code))
    if row:
        for key, value in payload.model_dump().items(): setattr(row, key, value)
        row.is_active = True
    else:
        row = CommercialCompanyProfile(**payload.model_dump(), created_by=user.id)
        db.add(row)
    await db.commit(); await db.refresh(row); return row


@router.get("/equipment", response_model=list[CommercialEquipmentOutput])
async def list_equipment(user: CurrentUser, db: DbSession, search: Annotated[str | None, Query(max_length=120)] = None):
    query = select(CommercialEquipment).where(CommercialEquipment.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(CommercialEquipment.serial_code.ilike(term), CommercialEquipment.equipment_type.ilike(term), CommercialEquipment.manufacturer.ilike(term), CommercialEquipment.model.ilike(term)))
    rows = list((await db.scalars(query.order_by(CommercialEquipment.id.desc()).limit(500))).all())
    if _money_allowed(user): return rows
    result=[]
    for row in rows:
        data=CommercialEquipmentOutput.model_validate(row).model_dump(); data.update(unit_cost=None,sale_price=None,rental_daily_price=None,rental_monthly_price=None); result.append(data)
    return result


@router.post("/equipment", response_model=CommercialEquipmentOutput, status_code=201)
async def create_equipment(payload: CommercialEquipmentInput, user: CurrentUser, db: DbSession):
    if any(v is not None for v in [payload.unit_cost,payload.sale_price,payload.rental_daily_price,payload.rental_monthly_price]): _require_money(user)
    row=CommercialEquipment(**payload.model_dump(), created_by=user.id); db.add(row); await db.flush(); row.serial_code=f"{row.id:03d}"; await db.commit(); await db.refresh(row); return row


@router.put("/equipment/{equipment_id}", response_model=CommercialEquipmentOutput)
async def update_equipment(equipment_id:int,payload:CommercialEquipmentInput,user:CurrentUser,db:DbSession):
    money_fields = {"unit_cost", "sale_price", "rental_daily_price", "rental_monthly_price"}
    if any(getattr(payload, field) is not None for field in money_fields):
        _require_money(user)
    row=await _equipment_or_404(db,equipment_id)
    data = payload.model_dump()
    if not _money_allowed(user):
        # Valores mascarados chegam como null ao frontend operacional. Não permitir que um save
        # operacional apague preços previamente cadastrados pela Gestão.
        for field in money_fields:
            data.pop(field, None)
    for k,v in data.items(): setattr(row,k,v)
    await db.commit(); await db.refresh(row)
    if _money_allowed(user): return row
    out=CommercialEquipmentOutput.model_validate(row).model_dump()
    out.update(unit_cost=None,sale_price=None,rental_daily_price=None,rental_monthly_price=None)
    return out


@router.delete("/equipment/{equipment_id}", status_code=204)
async def deactivate_equipment(equipment_id:int,_:CurrentUser,db:DbSession, __: User = Depends(require_general_admin)):
    row=await _equipment_or_404(db,equipment_id); row.is_active=False; await db.commit(); return Response(status_code=204)


@router.get("/equipment/{equipment_id}/label.pdf")
async def equipment_label(equipment_id:int,_:CurrentUser,db:DbSession):
    row=await _equipment_or_404(db,equipment_id); pdf=await asyncio.to_thread(commercial_label_pdf,row)
    return Response(content=pdf,media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="etiqueta-comercial-{row.serial_code}.pdf"'})


def _line_total(quantity: float, unit_price: float, discount_pct: float) -> Decimal:
    total=Decimal(str(quantity))*Decimal(str(unit_price))*(Decimal("1")-Decimal(str(discount_pct))/Decimal("100"))
    return total.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)


async def _replace_items(db:AsyncSession, quote:CommercialQuote,payload:CommercialQuoteInput):
    existing=list((await db.scalars(select(CommercialQuoteItem).where(CommercialQuoteItem.quote_id==quote.id))).all())
    for row in existing: await db.delete(row)
    total=Decimal("0")
    for index,item in enumerate(payload.items):
        line=_line_total(item.quantity,item.unit_price,item.discount_pct); total+=line
        db.add(CommercialQuoteItem(quote_id=quote.id,line_total=line,sort_order=index,**item.model_dump()))
    quote.total=total


@router.get("/quotes", response_model=list[CommercialQuoteOutput])
async def list_quotes(user:CurrentUser,db:DbSession,quote_type:str|None=Query(default=None),status_filter:str|None=Query(default=None,alias="status")):
    query=select(CommercialQuote)
    if quote_type: query=query.where(CommercialQuote.quote_type==quote_type)
    if status_filter: query=query.where(CommercialQuote.status==status_filter)
    rows=list((await db.scalars(query.order_by(CommercialQuote.id.desc()).limit(500))).all())
    if not rows: return []

    customer_ids={row.customer_id for row in rows}
    customers=list((await db.scalars(select(LaboratoryCustomer).where(LaboratoryCustomer.id.in_(customer_ids)))).all())
    customer_map={row.id: row for row in customers}
    quote_ids=[row.id for row in rows]
    item_rows=list((await db.scalars(select(CommercialQuoteItem).where(CommercialQuoteItem.quote_id.in_(quote_ids)).order_by(CommercialQuoteItem.quote_id, CommercialQuoteItem.sort_order, CommercialQuoteItem.id))).all())
    items_by_quote: dict[int, list[CommercialQuoteItem]] = {}
    for item in item_rows:
        items_by_quote.setdefault(item.quote_id, []).append(item)

    show_values=_money_allowed(user)
    result=[]
    for quote in rows:
        customer=customer_map.get(quote.customer_id)
        result.append(CommercialQuoteOutput(
            id=quote.id, quote_number=quote.quote_number or f"COM-{quote.id:06d}", quote_type=quote.quote_type, company_code=quote.company_code,
            customer_id=quote.customer_id, customer_name=customer.legal_name if customer else "Cliente removido", revision=quote.revision, status=quote.status,
            issue_date=quote.issue_date, valid_until=quote.valid_until, title=quote.title, intro_text=quote.intro_text, notes=quote.notes, payment_terms=quote.payment_terms,
            delivery_terms=quote.delivery_terms, warranty_terms=quote.warranty_terms, rental_terms=quote.rental_terms, preventive_scope=quote.preventive_scope, exclusions=quote.exclusions,
            total=float(quote.total) if show_values else None, issued_at=quote.issued_at, created_at=quote.created_at, updated_at=quote.updated_at,
            items=[QuoteItemOutput(id=i.id,equipment_id=i.equipment_id,description=i.description,manufacturer=i.manufacturer,model=i.model,power=i.power,voltage=i.voltage,serial_number=i.serial_number,quantity=float(i.quantity),unit=i.unit,unit_price=float(i.unit_price) if show_values else None,discount_pct=float(i.discount_pct),rental_period_count=i.rental_period_count,rental_period_unit=i.rental_period_unit,line_total=float(i.line_total) if show_values else None,sort_order=i.sort_order) for i in items_by_quote.get(quote.id,[])],
        ))
    return result


@router.post("/quotes", response_model=CommercialQuoteOutput, status_code=201)
async def create_quote(payload:CommercialQuoteInput,user:CurrentUser,db:DbSession):
    _require_money(user)
    customer=await db.get(LaboratoryCustomer,payload.customer_id)
    if not customer or not customer.is_active: raise HTTPException(404,"Cliente não encontrado.")
    data=payload.model_dump(exclude={"items"}); quote=CommercialQuote(**data,created_by=user.id,status="draft",revision=0,total=0); db.add(quote); await db.flush(); quote.quote_number=f"COM-{quote.id:06d}"; await _replace_items(db,quote,payload); await db.commit(); await db.refresh(quote); return await _quote_output(db,quote,user)


@router.put("/quotes/{quote_id}", response_model=CommercialQuoteOutput)
async def update_quote(quote_id:int,payload:CommercialQuoteInput,user:CurrentUser,db:DbSession):
    _require_money(user); quote=await _quote_or_404(db,quote_id)
    if quote.status!="draft": raise HTTPException(409,"Somente rascunhos podem ser editados. Crie uma revisão formal para alterar um orçamento emitido.")
    for k,v in payload.model_dump(exclude={"items"}).items(): setattr(quote,k,v)
    await _replace_items(db,quote,payload); await db.commit(); await db.refresh(quote); return await _quote_output(db,quote,user)


@router.post("/quotes/{quote_id}/issue", response_model=CommercialQuoteOutput)
async def issue_quote(quote_id:int,user:CurrentUser,db:DbSession):
    _require_money(user); quote=await _quote_or_404(db,quote_id)
    if quote.status!="draft": raise HTTPException(409,"Apenas rascunhos podem ser emitidos.")
    from datetime import datetime, timezone
    quote.status="issued"; quote.revision=max(1,quote.revision or 0); quote.issued_at=datetime.now(timezone.utc); await db.commit(); await db.refresh(quote); return await _quote_output(db,quote,user)


@router.post("/quotes/{quote_id}/revision", response_model=CommercialQuoteOutput, status_code=201)
async def revise_quote(quote_id:int,user:CurrentUser,db:DbSession):
    _require_money(user); source=await _quote_or_404(db,quote_id)
    if source.status=="draft": raise HTTPException(409,"Já existe um rascunho editável; não é necessário criar revisão.")
    source_items=list((await db.scalars(select(CommercialQuoteItem).where(CommercialQuoteItem.quote_id==source.id).order_by(CommercialQuoteItem.sort_order))).all())
    data={c.name:getattr(source,c.name) for c in CommercialQuote.__table__.columns if c.name not in {"id","quote_number","revision","status","issued_at","created_at","updated_at","created_by"}}
    copy=CommercialQuote(**data,quote_number=source.quote_number,revision=source.revision+1,status="draft",issued_at=None,created_by=user.id); db.add(copy); await db.flush()
    for item in source_items:
        vals={c.name:getattr(item,c.name) for c in CommercialQuoteItem.__table__.columns if c.name not in {"id","quote_id"}}; db.add(CommercialQuoteItem(quote_id=copy.id,**vals))
    await db.commit(); await db.refresh(copy); return await _quote_output(db,copy,user)


@router.patch("/quotes/{quote_id}/status", response_model=CommercialQuoteOutput)
async def set_quote_status(quote_id:int,payload:QuoteStatusInput,user:CurrentUser,db:DbSession):
    quote=await _quote_or_404(db,quote_id)
    if payload.status == quote.status:
        return await _quote_output(db,quote,user)
    allowed=QUOTE_STATUS_TRANSITIONS.get(quote.status,set())
    if payload.status not in allowed:
        raise HTTPException(409, f"Transição de status inválida: {quote.status} → {payload.status}.")
    if payload.status in {"approved","rejected","cancelled"}: _require_money(user)
    quote.status=payload.status; await db.commit(); await db.refresh(quote); return await _quote_output(db,quote,user)


@router.get("/quotes/{quote_id}/pdf")
async def quote_pdf(quote_id:int,user:CurrentUser,db:DbSession):
    quote=await _quote_or_404(db,quote_id); customer=await db.get(LaboratoryCustomer,quote.customer_id); company=await db.scalar(select(CommercialCompanyProfile).where(CommercialCompanyProfile.company_code==quote.company_code,CommercialCompanyProfile.is_active.is_(True)))
    items=list((await db.scalars(select(CommercialQuoteItem).where(CommercialQuoteItem.quote_id==quote.id).order_by(CommercialQuoteItem.sort_order))).all())
    pdf=await asyncio.to_thread(commercial_quote_pdf,quote=quote,company=company,customer=customer,items=items,show_values=_money_allowed(user))
    return Response(content=pdf,media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="{quote.quote_number}.pdf"'})


@router.get("/preventive-orders", response_model=list[PreventiveOrderOutput])
async def list_preventive_orders(_:CurrentUser,db:DbSession):
    rows=list((await db.scalars(select(CommercialPreventiveOrder).order_by(CommercialPreventiveOrder.id.desc()).limit(500))).all())
    if not rows: return []
    customer_ids={row.customer_id for row in rows}
    customers=list((await db.scalars(select(LaboratoryCustomer).where(LaboratoryCustomer.id.in_(customer_ids)))).all())
    customer_map={row.id: row for row in customers}
    return [PreventiveOrderOutput(id=row.id,order_number=row.order_number or f"PREV-{row.id:06d}",quote_id=row.quote_id,company_code=row.company_code,customer_id=row.customer_id,customer_name=customer_map[row.customer_id].legal_name if row.customer_id in customer_map else "Cliente removido",status=row.status,scheduled_date=row.scheduled_date,completed_date=row.completed_date,technical_notes=row.technical_notes,created_at=row.created_at,updated_at=row.updated_at) for row in rows]


@router.post("/preventive-orders", response_model=PreventiveOrderOutput, status_code=201)
async def create_preventive_order(payload:PreventiveOrderInput,user:CurrentUser,db:DbSession):
    quote=await _quote_or_404(db,payload.quote_id)
    if quote.quote_type!="preventive": raise HTTPException(409,"A O.S. preventiva só pode ser criada a partir de orçamento de preventiva.")
    if quote.status!="approved": raise HTTPException(409,"A O.S. preventiva só pode ser gerada após a aprovação do orçamento.")
    existing=await db.scalar(select(CommercialPreventiveOrder).where(CommercialPreventiveOrder.quote_id==quote.id))
    if existing: raise HTTPException(409,"Já existe O.S. preventiva vinculada a este orçamento.")
    row=CommercialPreventiveOrder(quote_id=quote.id,company_code=quote.company_code,customer_id=quote.customer_id,scheduled_date=payload.scheduled_date,technical_notes=payload.technical_notes,created_by=user.id); db.add(row); await db.flush(); row.order_number=f"PREV-{row.id:06d}"; await db.commit(); await db.refresh(row); customer=await db.get(LaboratoryCustomer,row.customer_id); return PreventiveOrderOutput(id=row.id,order_number=row.order_number,quote_id=row.quote_id,company_code=row.company_code,customer_id=row.customer_id,customer_name=customer.legal_name,status=row.status,scheduled_date=row.scheduled_date,completed_date=row.completed_date,technical_notes=row.technical_notes,created_at=row.created_at,updated_at=row.updated_at)


@router.put("/preventive-orders/{order_id}", response_model=PreventiveOrderOutput)
async def update_preventive_order(order_id:int,payload:PreventiveOrderUpdate,_:CurrentUser,db:DbSession):
    row=await db.get(CommercialPreventiveOrder,order_id)
    if not row: raise HTTPException(404,"O.S. preventiva não encontrada.")
    for k,v in payload.model_dump().items(): setattr(row,k,v)
    await db.commit(); await db.refresh(row); customer=await db.get(LaboratoryCustomer,row.customer_id); return PreventiveOrderOutput(id=row.id,order_number=row.order_number or f"PREV-{row.id:06d}",quote_id=row.quote_id,company_code=row.company_code,customer_id=row.customer_id,customer_name=customer.legal_name if customer else "Cliente removido",status=row.status,scheduled_date=row.scheduled_date,completed_date=row.completed_date,technical_notes=row.technical_notes,created_at=row.created_at,updated_at=row.updated_at)
