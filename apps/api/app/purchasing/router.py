from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload, validate_upload
from app.notifications.service import notify_modules
from app.purchasing.models import PurchaseAuditEvent, PurchaseOrder, Supplier
from app.purchasing.schemas import (
    CompanyCode,
    PurchaseAuditOutput,
    PurchaseInput,
    PurchaseOutput,
    PurchaseStatus,
    PurchaseSummary,
    PurchaseUpdate,
    SupplierInput,
    SupplierOutput,
)
from app.purchasing.service import build_purchase_summary, next_purchase_code

router = APIRouter(prefix="/purchasing", dependencies=[Depends(require_module("compras"))])
UPLOAD_ROOT = Path(settings.storage_root) / "purchasing"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
CompanyFilter = Annotated[CompanyCode | None, Query()]
StatusFilter = Annotated[PurchaseStatus | None, Query(alias="status")]
OverdueFilter = Annotated[bool, Query()]
DueSoonFilter = Annotated[bool, Query()]
YearFilter = Annotated[int | None, Query(ge=2024, le=2100)]
MonthFilter = Annotated[int | None, Query(ge=1, le=12)]
SearchFilter = Annotated[str | None, Query(max_length=120)]
AttachmentFile = Annotated[UploadFile, File()]


async def _purchase_or_404(db: AsyncSession, purchase_id: int) -> PurchaseOrder:
    purchase = await db.get(PurchaseOrder, purchase_id)
    if not purchase or purchase.is_deleted:
        raise HTTPException(status_code=404, detail="Compra não encontrada.")
    return purchase


def _audit(
    purchase: PurchaseOrder,
    action: str,
    description: str,
    user_id: int,
) -> PurchaseAuditEvent:
    return PurchaseAuditEvent(
        purchase_id=purchase.id,
        action=action,
        description=description,
        user_id=user_id,
    )


@router.get("/summary", response_model=PurchaseSummary)
async def summary(
    _: CurrentUser,
    db: DbSession,
    company_code: CompanyFilter = None,
):
    return await build_purchase_summary(db, company_code)


@router.get("/suppliers", response_model=list[SupplierOutput])
async def list_suppliers(_: CurrentUser, db: DbSession):
    query = select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.name)
    return list((await db.scalars(query)).all())


@router.post("/suppliers", response_model=SupplierOutput, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierInput,
    _: CurrentUser,
    db: DbSession,
):
    # O nome é a chave funcional do fornecedor. A comparação é case-insensitive
    # e com espaços normalizados, para impedir duplicidades visuais e permitir
    # reativar cadastros antigos sem criar um segundo registro.
    normalized_name = " ".join(payload.name.split()).strip()
    if len(normalized_name) < 2:
        raise HTTPException(status_code=422, detail="Informe um fornecedor válido.")

    existing = await db.scalar(
        select(Supplier).where(func.lower(Supplier.name) == normalized_name.lower())
    )
    if existing:
        if existing.is_active:
            # Para a operação de compra, tratar fornecedor já existente como
            # sucesso é mais útil do que devolver 409. O frontend passa a
            # selecionar o cadastro existente automaticamente.
            return existing
        existing.is_active = True
        existing.name = normalized_name
        existing.origin = payload.origin
        existing.website = payload.website or None
        existing.contact_name = payload.contact_name or None
        existing.contact_phone = payload.contact_phone or None
        await db.commit()
        await db.refresh(existing)
        return existing

    supplier_data = payload.model_dump()
    supplier_data.update(
        name=normalized_name,
        website=payload.website or None,
        contact_name=payload.contact_name or None,
        contact_phone=payload.contact_phone or None,
    )
    supplier = Supplier(**supplier_data)
    db.add(supplier)
    try:
        await db.commit()
    except IntegrityError:
        # Protege contra concorrência: se outro request cadastrou o mesmo nome
        # entre o SELECT e o COMMIT, recuperamos o registro já persistido.
        await db.rollback()
        existing = await db.scalar(
            select(Supplier).where(func.lower(Supplier.name) == normalized_name.lower())
        )
        if not existing:
            raise HTTPException(status_code=409, detail="Não foi possível concluir o cadastro do fornecedor.")
        if not existing.is_active:
            existing.is_active = True
            await db.commit()
            await db.refresh(existing)
        return existing

    await db.refresh(supplier)
    return supplier


@router.get("/orders", response_model=list[PurchaseOutput])
async def list_orders(
    _: CurrentUser,
    db: DbSession,
    company_code: CompanyFilter = None,
    purchase_status: StatusFilter = None,
    overdue: OverdueFilter = False,
    due_soon: DueSoonFilter = False,
    year: YearFilter = None,
    month: MonthFilter = None,
    search: SearchFilter = None,
):
    query = select(PurchaseOrder).where(PurchaseOrder.is_deleted.is_(False))
    if company_code:
        query = query.where(PurchaseOrder.company_code == company_code)
    if purchase_status:
        query = query.where(PurchaseOrder.status == purchase_status)
    if overdue:
        query = query.where(
            PurchaseOrder.status.notin_(("delivered", "cancelled")),
            PurchaseOrder.estimated_delivery_date < date.today(),
        )
    if due_soon:
        query = query.where(
            PurchaseOrder.status.notin_(("delivered", "cancelled")),
            PurchaseOrder.estimated_delivery_date >= date.today(),
            PurchaseOrder.estimated_delivery_date <= date.today() + timedelta(days=7),
        )
    if year:
        start = date(year, month or 1, 1)
        end = (
            date(year + 1, 1, 1)
            if not month or month == 12
            else date(year, month + 1, 1)
        )
        query = query.where(
            PurchaseOrder.purchase_date >= start,
            PurchaseOrder.purchase_date < end,
        )
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                PurchaseOrder.code.ilike(term),
                PurchaseOrder.supplier_name.ilike(term),
                PurchaseOrder.product_name.ilike(term),
                PurchaseOrder.equipment_serial.ilike(term),
                PurchaseOrder.invoice_number.ilike(term),
                PurchaseOrder.client_destination.ilike(term),
                PurchaseOrder.tracking_code.ilike(term),
            )
        )
    query = (
        query.order_by(
            PurchaseOrder.estimated_delivery_date,
            PurchaseOrder.id.desc(),
        )
        .limit(500)
    )
    return list((await db.scalars(query)).all())


@router.get("/orders/{purchase_id}", response_model=PurchaseOutput)
async def get_order(
    purchase_id: int,
    _: CurrentUser,
    db: DbSession,
):
    return await _purchase_or_404(db, purchase_id)


@router.post("/orders", response_model=PurchaseOutput, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: PurchaseInput,
    user: CurrentUser,
    db: DbSession,
):
    supplier = await db.get(Supplier, payload.supplier_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(status_code=400, detail="Fornecedor inválido.")
    purchase = PurchaseOrder(
        **payload.model_dump(),
        code=await next_purchase_code(db),
        supplier_name=supplier.name,
        created_by=user.id,
    )
    db.add(purchase)
    await db.flush()
    db.add(_audit(purchase, "created", f"Compra criada: {purchase.code}", user.id))
    await db.commit()
    await db.refresh(purchase)
    return purchase


@router.put("/orders/{purchase_id}", response_model=PurchaseOutput)
async def update_order(
    purchase_id: int,
    payload: PurchaseUpdate,
    user: CurrentUser,
    db: DbSession,
):
    purchase = await _purchase_or_404(db, purchase_id)
    supplier = await db.get(Supplier, payload.supplier_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(status_code=400, detail="Fornecedor inválido.")
    for field, value in payload.model_dump().items():
        setattr(purchase, field, value)
    purchase.supplier_name = supplier.name
    if purchase.status == "delivered" and purchase.delivered_at is None:
        purchase.delivered_at = date.today()
    db.add(_audit(purchase, "updated", f"Compra editada: {purchase.code}", user.id))
    await db.commit()
    await db.refresh(purchase)
    return purchase


@router.delete("/orders/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    purchase_id: int,
    user: CurrentUser,
    db: DbSession,
):
    purchase = await _purchase_or_404(db, purchase_id)
    purchase.is_deleted = True
    db.add(_audit(purchase, "deleted", f"Compra excluída: {purchase.code}", user.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/equipment/{serial_number}/purchases", response_model=list[PurchaseOutput])
async def purchases_by_serial(
    serial_number: str,
    _: CurrentUser,
    db: DbSession,
):
    query = (
        select(PurchaseOrder)
        .where(
            PurchaseOrder.is_deleted.is_(False),
            PurchaseOrder.equipment_serial.ilike(serial_number.strip()),
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    return list((await db.scalars(query)).all())


@router.post("/orders/{purchase_id}/attachment")
async def upload_attachment(
    purchase_id: int,
    file: AttachmentFile,
    user: CurrentUser,
    db: DbSession,
):
    purchase = await _purchase_or_404(db, purchase_id)
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="O arquivo excede 10 MB.")

    try:
        detected = validate_upload(content, file.filename, file.content_type)
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    suffix = detected.extension
    directory = UPLOAD_ROOT / purchase.company_code
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{purchase.id}-{uuid4().hex}{suffix}"
    target.write_bytes(content)
    purchase.attachment_name = file.filename
    purchase.attachment_path = str(target)
    purchase.attachment_mime = detected.mime_type
    db.add(
        _audit(
            purchase,
            "attachment_added",
            f"Anexo incluído: {file.filename}",
            user.id,
        )
    )
    await db.commit()
    return {"filename": file.filename or target.name}


@router.get("/orders/{purchase_id}/attachment/preview")
async def preview_attachment(
    purchase_id: int,
    _: CurrentUser,
    db: DbSession,
):
    purchase = await _purchase_or_404(db, purchase_id)
    if not purchase.attachment_path or not Path(purchase.attachment_path).is_file():
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    safe_name = quote(purchase.attachment_name or "anexo")
    return FileResponse(
        purchase.attachment_path,
        media_type=purchase.attachment_mime or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{safe_name}"},
    )


@router.get("/audit", response_model=list[PurchaseAuditOutput])
async def list_audit(_: CurrentUser, db: DbSession):
    query = (
        select(PurchaseAuditEvent, User.name)
        .join(User, User.id == PurchaseAuditEvent.user_id)
        .order_by(PurchaseAuditEvent.created_at.desc())
        .limit(500)
    )
    rows = (await db.execute(query)).all()
    return [
        PurchaseAuditOutput(
            id=event.id,
            purchase_id=event.purchase_id,
            action=event.action,
            description=event.description,
            user_id=event.user_id,
            user_name=user_name,
            created_at=event.created_at,
        )
        for event, user_name in rows
    ]

# ------------------------------------------------------- material requests ---

from app.purchasing.material_models import MaterialRequest, MaterialRequestEvent
from app.purchasing.material_schemas import (
    MaterialRequestEventOutput,
    MaterialRequestOutput,
    MaterialRequestStatus,
    StandaloneMaterialRequestCreate,
    MaterialRequestUpdate,
)
from app.purchasing.material_service import (
    apply_status_timestamps,
    event as material_event,
    output_rows,
    validate_transition,
    next_material_request_code,
)


@router.get("/material-requests", response_model=list[MaterialRequestOutput])
async def list_material_requests(
    _: CurrentUser,
    db: DbSession,
    request_status: MaterialRequestStatus | None = Query(default=None, alias="status"),
    company_code: CompanyCode | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
):
    query = select(MaterialRequest)
    if request_status:
        query = query.where(MaterialRequest.status == request_status)
    if company_code:
        query = query.where(MaterialRequest.company_code == company_code)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                MaterialRequest.code.ilike(term),
                MaterialRequest.item_name.ilike(term),
                MaterialRequest.technical_note.ilike(term),
                MaterialRequest.supplier_name.ilike(term),
                MaterialRequest.purchase_reference.ilike(term),
            )
        )
    rows = list((await db.scalars(query.order_by(MaterialRequest.created_at.desc()).limit(500))).all())
    return await output_rows(db, rows)


@router.post("/material-requests", response_model=MaterialRequestOutput, status_code=status.HTTP_201_CREATED)
async def create_standalone_material_request(
    payload: StandaloneMaterialRequestCreate,
    user: CurrentUser,
    db: DbSession,
):
    request = MaterialRequest(
        code=await next_material_request_code(db),
        company_code=payload.company_code,
        work_order_id=None,
        equipment_id=None,
        requester_user_id=user.id,
        source_type="standalone",
        item_name=payload.item_name.strip(),
        quantity=payload.quantity,
        priority=payload.priority,
        technical_note=payload.technical_note,
        suggested_link=payload.suggested_link,
        status="awaiting_approval",
        updated_by=user.id,
    )
    db.add(request)
    await db.flush()
    db.add(material_event(
        request,
        user_id=user.id,
        event_type="created",
        previous=None,
        target="awaiting_approval",
        note="Solicitação avulsa criada no módulo de Compras.",
    ))
    await notify_modules(
        db,
        modules={"compras"},
        category="purchase_request",
        severity="info",
        title=f"Nova solicitação avulsa · {request.code}",
        message=f"{user.name} solicitou {request.quantity}x {request.item_name}.",
        target="/compras?view=requests",
        entity_type="material_request",
        entity_id=request.id,
        exclude_user_id=user.id,
    )
    await db.commit()
    await db.refresh(request)
    return (await output_rows(db, [request]))[0]


@router.patch("/material-requests/{request_id}", response_model=MaterialRequestOutput)
async def update_material_request(
    request_id: int,
    payload: MaterialRequestUpdate,
    user: CurrentUser,
    db: DbSession,
):
    request = await db.get(MaterialRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Solicitação de material não encontrada.")

    previous = request.status
    validate_transition(previous, payload.status)
    if payload.status == "purchased" and (payload.unit_cost is None or payload.unit_cost <= 0):
        raise HTTPException(
            status_code=422,
            detail="Informe o valor unitário antes de marcar a solicitação como Comprado.",
        )
    request.status = payload.status
    request.supplier_name = payload.supplier_name
    request.purchase_reference = payload.purchase_reference
    request.purchase_link = payload.purchase_link
    request.tracking_code = payload.tracking_code
    request.unit_cost = payload.unit_cost
    request.expected_delivery_date = payload.expected_delivery_date
    apply_status_timestamps(request, previous, payload.status, user.id)
    db.add(material_event(
        request,
        user_id=user.id,
        event_type="status_changed" if previous != payload.status else "updated",
        previous=previous,
        target=payload.status,
        note=payload.note,
    ))
    if previous != "purchased" and payload.status == "purchased":
        total = (request.unit_cost or Decimal("0")) * request.quantity
        value = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        await notify_modules(
            db,
            modules={"compras", "laboratorio"},
            category="purchase",
            severity="success",
            title=f"Compra realizada · {request.code}",
            message=f"{request.quantity}x {request.item_name} comprado(s) por {value}. OS vinculada pronta para acompanhamento.",
            target=(f"/laboratorio?os={request.work_order_id}&aba=materials" if request.work_order_id else "/compras?view=requests"),
            entity_type="material_request",
            entity_id=request.id,
            work_order_id=request.work_order_id,
            amount=total,
        )
    await db.commit()
    await db.refresh(request)
    return (await output_rows(db, [request]))[0]


@router.get("/material-requests/{request_id}/events", response_model=list[MaterialRequestEventOutput])
async def list_material_request_events(
    request_id: int,
    _: CurrentUser,
    db: DbSession,
):
    exists = await db.get(MaterialRequest, request_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Solicitação de material não encontrada.")
    query = (
        select(MaterialRequestEvent, User.name)
        .join(User, User.id == MaterialRequestEvent.user_id)
        .where(MaterialRequestEvent.material_request_id == request_id)
        .order_by(MaterialRequestEvent.created_at.desc())
    )
    rows = (await db.execute(query)).all()
    return [
        MaterialRequestEventOutput(
            id=item.id,
            event_type=item.event_type,
            previous_status=item.previous_status,
            new_status=item.new_status,
            note=item.note,
            user_id=item.user_id,
            user_name=user_name,
            created_at=item.created_at,
        )
        for item, user_name in rows
    ]
