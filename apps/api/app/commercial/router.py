import asyncio
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_create_quote, user_can_view_sensitive_values
from app.auth.dependencies import require_general_admin, require_module
from app.auth.models import User
from app.auth.router import current_user
from app.commercial.label_pdf import commercial_label_pdf
from app.commercial.models import (
    CommercialAssetArea,
    CommercialAssetLocation,
    CommercialAssetLocationHistory,
    CommercialAssetRack,
    CommercialCompanyProfile,
    CommercialEquipment,
    CommercialPreventiveOrder,
    CommercialQuote,
    CommercialQuoteItem,
)
from app.commercial.quote_pdf import commercial_quote_pdf
from app.commercial.schemas import (
    CommercialAssetAreaOutput,
    CommercialAssetHistoryOutput,
    CommercialAssetLocationConfig,
    CommercialAssetLocationOutput,
    CommercialAssetMapOccupant,
    CommercialAssetMapOutput,
    CommercialAssetMapSlot,
    CommercialAssetMoveInput,
    CommercialAssetRackOutput,
    CompanyProfileInput,
    CompanyProfileOutput,
    CommercialEquipmentInput,
    CommercialEquipmentOutput,
    CommercialQuoteInput,
    CommercialQuoteOutput,
    PreventiveOrderInput,
    PreventiveOrderOutput,
    PreventiveOrderUpdate,
    QuoteItemOutput,
    QuoteStatusInput,
)
from app.core.db import get_db
from app.laboratory.models import LaboratoryCustomer
from app.notifications.service import notify_modules

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


def _quote_allowed(user: User) -> bool:
    return user_can_create_quote(user.role, user.modules)


def _require_money(user: User) -> None:
    if not _money_allowed(user):
        raise HTTPException(status_code=403, detail="Somente Gestão pode visualizar ou alterar valores monetários.")


def _require_quote(user: User) -> None:
    if not _quote_allowed(user):
        raise HTTPException(
            status_code=403,
            detail="Seu perfil não possui permissão para criar, alterar ou emitir orçamentos.",
        )


async def _equipment_or_404(db: AsyncSession, equipment_id: int) -> CommercialEquipment:
    item = await db.get(CommercialEquipment, equipment_id)
    if not item or not item.is_active:
        raise HTTPException(status_code=404, detail="Equipamento comercial não encontrado.")
    return item


async def _asset_location_or_404(db: AsyncSession, location_id: int) -> CommercialAssetLocation:
    row = await db.get(CommercialAssetLocation, location_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Localização patrimonial não encontrada.")
    return row


async def _set_asset_location(
    db: AsyncSession,
    equipment: CommercialEquipment,
    location: CommercialAssetLocation | None,
    *,
    user_id: int,
) -> None:
    current = await db.scalar(
        select(CommercialAssetLocationHistory)
        .where(
            CommercialAssetLocationHistory.equipment_id == equipment.id,
            CommercialAssetLocationHistory.released_at.is_(None),
        )
        .order_by(
            CommercialAssetLocationHistory.assigned_at.desc(),
            CommercialAssetLocationHistory.id.desc(),
        )
    )
    next_code = location.code if location else None
    if equipment.location == next_code and equipment.asset_location_id == (location.id if location else None):
        return
    if current is not None:
        current.released_at = func.now()
    equipment.asset_location_id = location.id if location else None
    equipment.location = next_code
    if location is not None:
        db.add(
            CommercialAssetLocationHistory(
                equipment_id=equipment.id,
                location_code=location.code,
                changed_by=user_id,
            )
        )


async def _commercial_equipment_output(
    row: CommercialEquipment,
    user: User,
) -> CommercialEquipmentOutput:
    data = CommercialEquipmentOutput.model_validate(row).model_dump()
    if not _money_allowed(user):
        data.update(
            unit_cost=None,
            sale_price=None,
            rental_daily_price=None,
            rental_monthly_price=None,
        )
    return CommercialEquipmentOutput(**data)


async def _asset_location_config(db: AsyncSession) -> CommercialAssetLocationConfig:
    areas = list((await db.scalars(
        select(CommercialAssetArea).order_by(CommercialAssetArea.sort_order, CommercialAssetArea.id)
    )).all())
    racks = list((await db.scalars(
        select(CommercialAssetRack).order_by(CommercialAssetRack.sort_order, CommercialAssetRack.id)
    )).all())
    locations = list((await db.scalars(
        select(CommercialAssetLocation).order_by(CommercialAssetLocation.sort_order, CommercialAssetLocation.id)
    )).all())
    area_map = {item.id: item for item in areas}
    rack_map = {item.id: item for item in racks}
    return CommercialAssetLocationConfig(
        areas=[
            CommercialAssetAreaOutput(
                id=item.id,
                code=item.code,
                name=item.name,
                sort_order=item.sort_order,
                is_active=item.is_active,
            )
            for item in areas
        ],
        racks=[
            CommercialAssetRackOutput(
                id=item.id,
                area_id=item.area_id,
                area_code=area_map[item.area_id].code,
                area_name=area_map[item.area_id].name,
                code=item.code,
                name=item.name,
                position_prefix=item.position_prefix,
                rows=item.rows,
                columns=item.columns,
                layout_row=item.layout_row,
                layout_column=item.layout_column,
                layout_span=item.layout_span,
                sort_order=item.sort_order,
                is_active=item.is_active,
            )
            for item in racks
        ],
        locations=[
            CommercialAssetLocationOutput(
                id=item.id,
                area_id=item.area_id,
                rack_id=item.rack_id,
                area_code=area_map[item.area_id].code,
                area_name=area_map[item.area_id].name,
                rack_code=rack_map[item.rack_id].code if item.rack_id else None,
                rack_name=rack_map[item.rack_id].name if item.rack_id else None,
                code=item.code,
                name=item.name,
                sort_order=item.sort_order,
                is_active=item.is_active,
            )
            for item in locations
        ],
    )


async def _quote_or_404(db: AsyncSession, quote_id: int) -> CommercialQuote:
    quote = await db.get(CommercialQuote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Orçamento comercial não encontrado.")
    return quote


async def _quote_output(db: AsyncSession, quote: CommercialQuote, user: User) -> CommercialQuoteOutput:
    customer = await db.get(LaboratoryCustomer, quote.customer_id)
    items = list((await db.scalars(select(CommercialQuoteItem).where(CommercialQuoteItem.quote_id == quote.id).order_by(CommercialQuoteItem.sort_order, CommercialQuoteItem.id))).all())
    show_values = _quote_allowed(user)
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
        query = query.where(or_(
            CommercialEquipment.serial_code.ilike(term),
            CommercialEquipment.patrimony_code.ilike(term),
            CommercialEquipment.manufacturer_serial.ilike(term),
            CommercialEquipment.equipment_type.ilike(term),
            CommercialEquipment.manufacturer.ilike(term),
            CommercialEquipment.model.ilike(term),
        ))
    rows = list((await db.scalars(query.order_by(CommercialEquipment.id.desc()).limit(500))).all())
    return [await _commercial_equipment_output(row, user) for row in rows]


async def _validate_rental_customer(db: AsyncSession, *, customer_id: int | None, status: str, company_code: str) -> None:
    if status != "rented":
        if customer_id is not None:
            raise HTTPException(422, "Cliente da locação só pode ser informado com status Locado.")
        return
    if customer_id is None:
        raise HTTPException(422, "Selecione o cliente antes de marcar o patrimônio como Locado.")
    customer = await db.get(LaboratoryCustomer, customer_id)
    if customer is None or not customer.is_active or customer.company_code != company_code:
        raise HTTPException(422, "Cliente não encontrado, inativo ou vinculado a outra empresa.")


@router.post("/equipment", response_model=CommercialEquipmentOutput, status_code=201)
async def create_equipment(payload: CommercialEquipmentInput, user: CurrentUser, db: DbSession):
    if any(v is not None for v in [payload.unit_cost,payload.sale_price,payload.rental_daily_price,payload.rental_monthly_price]):
        _require_money(user)
    if payload.quantity != 1:
        raise HTTPException(status_code=422, detail="Cada patrimônio deve representar exatamente uma unidade.")
    await _validate_rental_customer(db, customer_id=payload.rental_customer_id, status=payload.stock_status, company_code=payload.company_code)
    data = payload.model_dump()
    location_id = data.pop("asset_location_id", None)
    data["quantity"] = 1
    data["location"] = None
    equipment_id = await db.scalar(
        select(func.nextval(func.pg_get_serial_sequence(CommercialEquipment.__tablename__, "id")))
    )
    row = CommercialEquipment(
        **data,
        id=equipment_id,
        serial_code=f"{equipment_id:03d}",
        patrimony_code=f"PAT-{equipment_id:06d}",
        created_by=user.id,
    )
    db.add(row)
    await db.flush()
    if location_id is not None:
        location = await _asset_location_or_404(db, location_id)
        await _set_asset_location(db, row, location, user_id=user.id)
    await db.commit()
    await db.refresh(row)
    return await _commercial_equipment_output(row, user)


@router.put("/equipment/{equipment_id}", response_model=CommercialEquipmentOutput)
async def update_equipment(equipment_id:int,payload:CommercialEquipmentInput,user:CurrentUser,db:DbSession):
    money_fields = {"unit_cost", "sale_price", "rental_daily_price", "rental_monthly_price"}
    if any(getattr(payload, field) is not None for field in money_fields):
        _require_money(user)
    row=await _equipment_or_404(db,equipment_id)
    await _validate_rental_customer(db, customer_id=payload.rental_customer_id, status=payload.stock_status, company_code=payload.company_code)
    if payload.quantity != 1:
        raise HTTPException(status_code=422, detail="Cada patrimônio deve representar exatamente uma unidade.")
    data = payload.model_dump()
    location_id = data.pop("asset_location_id", None)
    data["quantity"] = 1
    data.pop("location", None)
    if not _money_allowed(user):
        # Valores mascarados chegam como null ao frontend operacional. Não permitir que um save
        # operacional apague preços previamente cadastrados pela Gestão.
        for field in money_fields:
            data.pop(field, None)
    for k,v in data.items():
        setattr(row,k,v)
    location = await _asset_location_or_404(db, location_id) if location_id is not None else None
    await _set_asset_location(db, row, location, user_id=user.id)
    await db.commit()
    await db.refresh(row)
    return await _commercial_equipment_output(row, user)


@router.get("/asset-locations", response_model=CommercialAssetLocationConfig)
async def asset_locations(_: CurrentUser, db: DbSession):
    return await _asset_location_config(db)


@router.get("/asset-map", response_model=CommercialAssetMapOutput)
async def asset_map(_: CurrentUser, db: DbSession):
    config = await _asset_location_config(db)
    active_areas = {item.id: item for item in config.areas if item.is_active}
    active_racks = {
        item.id: item for item in config.racks
        if item.is_active and item.area_id in active_areas
    }
    active_locations = [
        item for item in config.locations
        if item.is_active
        and item.area_id in active_areas
        and (item.rack_id is None or item.rack_id in active_racks)
    ]
    location_ids = [item.id for item in active_locations]
    rows = list((await db.scalars(
        select(CommercialEquipment)
        .where(
            CommercialEquipment.is_active.is_(True),
            CommercialEquipment.asset_location_id.in_(location_ids),
        )
        .order_by(CommercialEquipment.patrimony_code)
    )).all()) if location_ids else []
    grouped: dict[int, list[CommercialEquipment]] = {}
    for equipment in rows:
        if equipment.asset_location_id is not None:
            grouped.setdefault(equipment.asset_location_id, []).append(equipment)

    slots: list[CommercialAssetMapSlot] = []
    for location in active_locations:
        rack = active_racks.get(location.rack_id) if location.rack_id else None
        area = active_areas[location.area_id]
        occupants = [
            CommercialAssetMapOccupant(
                equipment_id=item.id,
                patrimony_code=item.patrimony_code or f"PAT-{item.id:06d}",
                equipment_type=item.equipment_type,
                manufacturer=item.manufacturer,
                model=item.model,
                manufacturer_serial=item.manufacturer_serial,
                stock_status=item.stock_status,
            )
            for item in grouped.get(location.id, [])
        ]
        slots.append(
            CommercialAssetMapSlot(
                location_id=location.id,
                location=location.code,
                area_code=area.code,
                area_name=area.name,
                rack_code=rack.code if rack else None,
                rack_name=rack.name if rack else None,
                rack_rows=rack.rows if rack else 1,
                rack_columns=rack.columns if rack else 1,
                rack_layout_row=rack.layout_row if rack else 1,
                rack_layout_column=rack.layout_column if rack else 1,
                rack_layout_span=rack.layout_span if rack else 1,
                slot_number=location.sort_order,
                occupants=occupants,
                occupancy_count=len(occupants),
            )
        )
    occupied = sum(1 for item in slots if item.occupancy_count > 0)
    without_location = int(await db.scalar(
        select(func.count()).select_from(CommercialEquipment).where(
            CommercialEquipment.is_active.is_(True),
            CommercialEquipment.asset_location_id.is_(None),
        )
    ) or 0)
    return CommercialAssetMapOutput(
        total_positions=len(slots),
        occupied_positions=occupied,
        free_positions=len(slots) - occupied,
        located_assets=sum(item.occupancy_count for item in slots),
        assets_without_location=without_location,
        slots=slots,
    )


@router.get(
    "/equipment/{equipment_id}/location-history",
    response_model=list[CommercialAssetHistoryOutput],
)
async def asset_location_history(equipment_id: int, _: CurrentUser, db: DbSession):
    await _equipment_or_404(db, equipment_id)
    rows = list((await db.scalars(
        select(CommercialAssetLocationHistory)
        .where(CommercialAssetLocationHistory.equipment_id == equipment_id)
        .order_by(
            CommercialAssetLocationHistory.assigned_at.desc(),
            CommercialAssetLocationHistory.id.desc(),
        )
    )).all())
    return rows


@router.put("/equipment/{equipment_id}/location", response_model=CommercialEquipmentOutput)
async def move_asset(
    equipment_id: int,
    payload: CommercialAssetMoveInput,
    user: CurrentUser,
    db: DbSession,
):
    row = await _equipment_or_404(db, equipment_id)
    location = await _asset_location_or_404(db, payload.location_id)
    await _set_asset_location(db, row, location, user_id=user.id)
    await db.commit()
    await db.refresh(row)
    return await _commercial_equipment_output(row, user)


@router.delete("/equipment/{equipment_id}", status_code=204)
async def deactivate_equipment(equipment_id:int,_:CurrentUser,db:DbSession, __: User = Depends(require_general_admin)):
    row=await _equipment_or_404(db,equipment_id); row.is_active=False; await db.commit(); return Response(status_code=204)


@router.get("/equipment/{equipment_id}/label.pdf")
async def equipment_label(equipment_id:int,_:CurrentUser,db:DbSession):
    row = await _equipment_or_404(db, equipment_id)
    rental_customer_name = None
    if row.stock_status == "rented" and row.rental_customer_id is not None:
        customer = await db.get(LaboratoryCustomer, row.rental_customer_id)
        if customer is not None:
            rental_customer_name = customer.trade_name or customer.legal_name
    pdf = await asyncio.to_thread(commercial_label_pdf, row, rental_customer_name)
    return Response(content=pdf,media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="patrimonio-{row.patrimony_code or row.serial_code}.pdf"'})


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

    show_values=_quote_allowed(user)
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
    _require_quote(user)
    customer=await db.get(LaboratoryCustomer,payload.customer_id)
    if not customer or not customer.is_active: raise HTTPException(404,"Cliente não encontrado.")
    data=payload.model_dump(exclude={"items"}); quote=CommercialQuote(**data,created_by=user.id,status="draft",revision=0,total=0); db.add(quote); await db.flush(); quote.quote_number=f"COM-{quote.id:06d}"; await _replace_items(db,quote,payload); await db.commit(); await db.refresh(quote); return await _quote_output(db,quote,user)


@router.put("/quotes/{quote_id}", response_model=CommercialQuoteOutput)
async def update_quote(quote_id:int,payload:CommercialQuoteInput,user:CurrentUser,db:DbSession):
    _require_quote(user); quote=await _quote_or_404(db,quote_id)
    if quote.status!="draft": raise HTTPException(409,"Somente rascunhos podem ser editados. Crie uma revisão formal para alterar um orçamento emitido.")
    for k,v in payload.model_dump(exclude={"items"}).items(): setattr(quote,k,v)
    await _replace_items(db,quote,payload); await db.commit(); await db.refresh(quote); return await _quote_output(db,quote,user)


@router.post("/quotes/{quote_id}/issue", response_model=CommercialQuoteOutput)
async def issue_quote(quote_id:int,user:CurrentUser,db:DbSession):
    _require_quote(user); quote=await _quote_or_404(db,quote_id)
    if quote.status!="draft": raise HTTPException(409,"Apenas rascunhos podem ser emitidos.")
    from datetime import datetime, timezone
    quote.status="issued"; quote.revision=max(1,quote.revision or 0); quote.issued_at=datetime.now(timezone.utc); await db.commit(); await db.refresh(quote); return await _quote_output(db,quote,user)


@router.post("/quotes/{quote_id}/revision", response_model=CommercialQuoteOutput, status_code=201)
async def revise_quote(quote_id:int,user:CurrentUser,db:DbSession):
    _require_quote(user); source=await _quote_or_404(db,quote_id)
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
    previous_status = quote.status
    quote.status = payload.status
    if previous_status != "approved" and payload.status == "approved" and quote.quote_type == "sale":
        customer = await db.get(LaboratoryCustomer, quote.customer_id)
        items = list((await db.scalars(
            select(CommercialQuoteItem)
            .where(CommercialQuoteItem.quote_id == quote.id)
            .order_by(CommercialQuoteItem.sort_order, CommercialQuoteItem.id)
        )).all())
        item_names = ", ".join(item.description for item in items[:3])
        if len(items) > 3:
            item_names += f" e mais {len(items) - 3} item(ns)"
        await notify_modules(
            db,
            modules={"compras"},
            category="commercial_sale_approved",
            severity="warning",
            title=f"Venda aprovada · {quote.quote_number}",
            message=f"{customer.legal_name if customer else 'Cliente'} aprovou a venda. Itens: {item_names or 'não informados'}.",
            target=f"/comercial?tab=orcamento&quote={quote.id}",
            entity_type="commercial_quote",
            entity_id=quote.id,
            amount=quote.total,
        )
    await db.commit()
    await db.refresh(quote)
    return await _quote_output(db,quote,user)


@router.get("/quotes/{quote_id}/pdf")
async def quote_pdf(quote_id:int,user:CurrentUser,db:DbSession):
    quote=await _quote_or_404(db,quote_id); customer=await db.get(LaboratoryCustomer,quote.customer_id); company=await db.scalar(select(CommercialCompanyProfile).where(CommercialCompanyProfile.company_code==quote.company_code,CommercialCompanyProfile.is_active.is_(True)))
    items=list((await db.scalars(select(CommercialQuoteItem).where(CommercialQuoteItem.quote_id==quote.id).order_by(CommercialQuoteItem.sort_order))).all())
    pdf=await asyncio.to_thread(commercial_quote_pdf,quote=quote,company=company,customer=customer,items=items,show_values=_quote_allowed(user))
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
