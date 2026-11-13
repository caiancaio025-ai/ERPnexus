from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_view_sensitive_values
from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload
from app.core.upload_stream import UploadTooLarge, persist_streamed_upload
from app.notifications.service import notify_modules
from app.purchasing.models import PurchaseAuditEvent, PurchaseOrder, Supplier
from app.inventory.stock_codes import stock_id_from_query
from app.inventory.purchase_cycle import purchase_unit_cost, receive_purchase
from app.inventory.models import InventoryComponentFormat, InventoryItem, InventoryMovement
from app.purchasing.schemas import (
    CompanyCode,
    PurchaseAuditOutput,
    PurchaseInput,
    PurchaseOutput,
    PurchaseStatus,
    PurchaseSummary,
    PurchaseSpendingReport,
    PurchaseUpdate,
    SupplierInput,
    SupplierOutput,
)
from app.purchasing.service import build_purchase_summary, next_purchase_code
from app.purchasing.stock_names import _purchase_with_canonical_inventory_name
from app.purchasing.spending_report import build_purchase_spending_report

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


def _require_sensitive_values(user: User) -> None:
    if not user_can_view_sensitive_values(user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o perfil Gestão pode registrar ou alterar valores monetários.",
        )


def _purchase_output(purchase: PurchaseOrder, *, include_sensitive_values: bool) -> PurchaseOutput:
    return PurchaseOutput(
        id=purchase.id,
        code=purchase.code,
        company_code=purchase.company_code,
        supplier_id=purchase.supplier_id,
        supplier_name=purchase.supplier_name,
        equipment_serial=purchase.equipment_serial,
        invoice_number=purchase.invoice_number,
        client_destination=purchase.client_destination,
        product_name=purchase.product_name,
        inventory_destination=purchase.inventory_destination,
        inventory_item_id=purchase.inventory_item_id,
        inventory_name=purchase.inventory_name,
        inventory_mode=purchase.inventory_mode,
        inventory_serial=purchase.inventory_serial,
        inventory_category=purchase.inventory_category,
        inventory_format_id=purchase.inventory_format_id,
        quantity=purchase.quantity,
        total_amount=purchase.total_amount if include_sensitive_values else None,
        origin=purchase.origin,
        tracking_code=purchase.tracking_code,
        purchase_date=purchase.purchase_date,
        estimated_delivery_date=purchase.estimated_delivery_date,
        delivered_at=purchase.delivered_at,
        status=purchase.status,
        product_link=purchase.product_link,
        notes=purchase.notes,
        attachment_name=purchase.attachment_name,
        attachment_mime=purchase.attachment_mime,
        created_at=purchase.created_at,
        updated_at=purchase.updated_at,
    )


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
    user: CurrentUser,
    db: DbSession,
    company_code: CompanyFilter = None,
):
    result = await build_purchase_summary(db, company_code)
    if not user_can_view_sensitive_values(user.role):
        result.total_value_open = None
    return result


@router.get("/reports/spending", response_model=PurchaseSpendingReport)
async def spending_report(
    user: CurrentUser,
    db: DbSession,
    start_date: date = Query(),
    end_date: date = Query(),
    company_code: CompanyFilter = None,
    supplier: str | None = Query(default=None, max_length=180),
):
    _require_sensitive_values(user)
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="A data final não pode ser anterior à data inicial.",
        )
    return await build_purchase_spending_report(
        db,
        start_date=start_date,
        end_date=end_date,
        company_code=company_code,
        supplier=supplier,
    )


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
    user: CurrentUser,
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
    rows = list((await db.scalars(query)).all())
    include_values = user_can_view_sensitive_values(user.role)
    return [_purchase_output(item, include_sensitive_values=include_values) for item in rows]


@router.get("/orders/{purchase_id}", response_model=PurchaseOutput)
async def get_order(
    purchase_id: int,
    user: CurrentUser,
    db: DbSession,
):
    purchase = await _purchase_or_404(db, purchase_id)
    return _purchase_output(
        purchase,
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.get("/stock-options")
async def purchase_stock_options(
    user: CurrentUser, db: DbSession,
    company_code: CompanyCode,
    search: str = Query(default="", max_length=120),
    selected_id: int | None = Query(default=None, gt=0),
):
    """Consulta de saldo disponível, sem custo, para evitar compras desnecessárias.

    Disponível aos usuários de Compras mesmo sem permissão do módulo Estoque.
    """
    query = select(InventoryItem).where(
        InventoryItem.is_active.is_(True),
        InventoryItem.company_code == company_code,
    )
    if search.strip():
        term = f"%{search.strip()}%"
        matched_id = stock_id_from_query(search)
        clauses = [InventoryItem.name.ilike(term), InventoryItem.stock_code.ilike(term), InventoryItem.manufacturer_serial.ilike(term)]
        if matched_id is not None:
            clauses.append(InventoryItem.id == matched_id)
        query = query.where(or_(*clauses))
    query = query.order_by(InventoryItem.name, InventoryItem.id).limit(60)
    rows = list((await db.scalars(query)).all())
    # Item já associado à compra deve continuar identificado mesmo fora da busca/limite.
    if selected_id is not None and all(item.id != selected_id for item in rows):
        selected = await db.get(InventoryItem, selected_id)
        if selected is not None and selected.is_active and selected.company_code == company_code:
            rows.append(selected)
    formats = (await db.scalars(select(InventoryComponentFormat).where(
        InventoryComponentFormat.is_active.is_(True),
    ).order_by(InventoryComponentFormat.category, InventoryComponentFormat.name))).all()
    return {
        "items": [
            {"id": item.id, "stock_code": item.stock_code, "name": item.name,
             "quantity": item.quantity, "mode": item.mode,
             "category": item.category, "manufacturer_serial": item.manufacturer_serial}
            for item in rows
        ],
        "formats": [
            {"id": fmt.id, "category": fmt.category, "name": fmt.name, "code": fmt.code}
            for fmt in formats
        ],
    }


@router.post("/orders", response_model=PurchaseOutput, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: PurchaseInput,
    user: CurrentUser,
    db: DbSession,
):
    _require_sensitive_values(user)
    supplier = await db.get(Supplier, payload.supplier_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(status_code=400, detail="Fornecedor inválido.")
    payload = await _purchase_with_canonical_inventory_name(db, payload)
    purchase = PurchaseOrder(
        **payload.model_dump(),
        code=await next_purchase_code(db),
        supplier_name=supplier.name,
        created_by=user.id,
    )
    db.add(purchase)
    await db.flush()
    if purchase.status == "delivered" and purchase.delivered_at is None:
        purchase.delivered_at = date.today()
    if purchase.status == "delivered":
        linked_requests = (await db.scalars(select(MaterialRequest).where(
            MaterialRequest.purchase_reference == purchase.code,
            MaterialRequest.company_code == purchase.company_code,
            MaterialRequest.status.in_(("received", "delivered_to_lab")),
        ).limit(2))).all()
        if len(linked_requests) > 1:
            raise HTTPException(409, "Múltiplas solicitações apontam para este pedido; concilie antes de receber.")
        await receive_purchase(db, source="order", source_id=purchase.id,
            company_code=purchase.company_code, name=purchase.product_name,
            quantity=purchase.quantity, unit_cost=purchase_unit_cost(purchase.total_amount, purchase.quantity),
            user_id=user.id, source_code=purchase.code,
            linked_source_id=linked_requests[0].id if linked_requests else None,
            destination=purchase.inventory_destination,
            target_item_id=purchase.inventory_item_id,
            stock_name=purchase.inventory_name,
            stock_mode=purchase.inventory_mode,
            stock_serial=purchase.inventory_serial,
            stock_category=purchase.inventory_category,
            stock_format_id=purchase.inventory_format_id)
    db.add(_audit(purchase, "created", f"Compra criada: {purchase.code}", user.id))
    await db.commit()
    await db.refresh(purchase)
    return _purchase_output(purchase, include_sensitive_values=True)


@router.put("/orders/{purchase_id}", response_model=PurchaseOutput)
async def update_order(
    purchase_id: int,
    payload: PurchaseUpdate,
    user: CurrentUser,
    db: DbSession,
):
    _require_sensitive_values(user)
    purchase = await db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == purchase_id, PurchaseOrder.is_deleted.is_(False),
    ).with_for_update())
    if purchase is None:
        raise HTTPException(404, "Compra não encontrada.")
    prior_receipt = await db.scalar(select(InventoryMovement).where(InventoryMovement.purchase_order_id == purchase_id))
    if prior_receipt is not None and (
        payload.status != "delivered" or payload.quantity != purchase.quantity
        or payload.product_name != purchase.product_name
        or payload.company_code != purchase.company_code
        or payload.total_amount != purchase.total_amount
        or payload.inventory_destination != purchase.inventory_destination
        or payload.inventory_item_id != purchase.inventory_item_id
        or payload.inventory_name != purchase.inventory_name
        or payload.inventory_mode != purchase.inventory_mode
        or payload.inventory_serial != purchase.inventory_serial
        or payload.inventory_category != purchase.inventory_category
        or payload.inventory_format_id != purchase.inventory_format_id
    ):
        raise HTTPException(409, "Compra já recebida no estoque. Estorne mediante fluxo auditado antes de alterar dados físicos ou valores.")
    supplier = await db.get(Supplier, payload.supplier_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(status_code=400, detail="Fornecedor inválido.")
    # Recebimentos antigos são imutáveis sem estorno; só sincronizar o nome antes da entrada.
    if prior_receipt is None:
        payload = await _purchase_with_canonical_inventory_name(db, payload)
    for field, value in payload.model_dump().items():
        setattr(purchase, field, value)
    purchase.supplier_name = supplier.name
    if purchase.status == "delivered" and purchase.delivered_at is None:
        purchase.delivered_at = date.today()
    if purchase.status == "delivered":
        linked_requests = (await db.scalars(select(MaterialRequest).where(
            MaterialRequest.purchase_reference == purchase.code,
            MaterialRequest.company_code == purchase.company_code,
            MaterialRequest.status.in_(("received", "delivered_to_lab")),
        ).limit(2))).all()
        if len(linked_requests) > 1:
            raise HTTPException(409, "Múltiplas solicitações apontam para este pedido; concilie antes de receber.")
        await receive_purchase(db, source="order", source_id=purchase.id,
            company_code=purchase.company_code, name=purchase.product_name,
            quantity=purchase.quantity, unit_cost=purchase_unit_cost(purchase.total_amount, purchase.quantity),
            user_id=user.id, source_code=purchase.code,
            linked_source_id=linked_requests[0].id if linked_requests else None,
            destination=purchase.inventory_destination,
            target_item_id=purchase.inventory_item_id,
            stock_name=purchase.inventory_name,
            stock_mode=purchase.inventory_mode,
            stock_serial=purchase.inventory_serial,
            stock_category=purchase.inventory_category,
            stock_format_id=purchase.inventory_format_id)
    db.add(_audit(purchase, "updated", f"Compra editada: {purchase.code}", user.id))
    await db.commit()
    await db.refresh(purchase)
    return _purchase_output(purchase, include_sensitive_values=True)


@router.delete("/orders/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    purchase_id: int,
    user: CurrentUser,
    db: DbSession,
):
    _require_sensitive_values(user)
    purchase = await _purchase_or_404(db, purchase_id)
    if await db.scalar(select(InventoryMovement.id).where(InventoryMovement.purchase_order_id == purchase.id)):
        raise HTTPException(409, "Compra já recebida em estoque; não é possível excluí-la sem estorno auditado.")
    purchase.is_deleted = True
    db.add(_audit(purchase, "deleted", f"Compra excluída: {purchase.code}", user.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/equipment/{serial_number}/purchases", response_model=list[PurchaseOutput])
async def purchases_by_serial(
    serial_number: str,
    user: CurrentUser,
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
    rows = list((await db.scalars(query)).all())
    include_values = user_can_view_sensitive_values(user.role)
    return [_purchase_output(item, include_sensitive_values=include_values) for item in rows]


@router.post("/orders/{purchase_id}/attachment")
async def upload_attachment(
    purchase_id: int,
    file: AttachmentFile,
    user: CurrentUser,
    db: DbSession,
):
    purchase = await _purchase_or_404(db, purchase_id)
    previous_path = Path(purchase.attachment_path) if purchase.attachment_path else None
    try:
        streamed = await persist_streamed_upload(
            file,
            directory=UPLOAD_ROOT / purchase.company_code,
            filename_prefix=f"{purchase.id}-",
            max_size=MAX_UPLOAD_SIZE,
        )
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail="O arquivo excede 10 MB.") from exc
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="Armazenamento de anexos indisponível. Verifique o volume /app/storage da API.",
        ) from exc

    target = streamed.path
    purchase.attachment_name = file.filename
    purchase.attachment_path = str(target)
    purchase.attachment_mime = streamed.mime_type
    db.add(
        _audit(
            purchase,
            "attachment_added",
            f"Anexo incluído: {file.filename}",
            user.id,
        )
    )
    try:
        await db.commit()
    except Exception:
        target.unlink(missing_ok=True)
        raise

    if previous_path and previous_path != target:
        try:
            previous_path.unlink(missing_ok=True)
        except OSError:
            pass
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
    next_material_request_code,
    output_rows,
    recalculate_work_order_parts_cost,
    validate_transition,
)


@router.get("/material-requests", response_model=list[MaterialRequestOutput])
async def list_material_requests(
    user: CurrentUser,
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
    return await output_rows(
        db,
        rows,
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


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
        **payload.model_dump(include={
            "inventory_destination", "inventory_item_id", "inventory_name", "inventory_mode",
            "inventory_serial", "inventory_category", "inventory_format_id",
        }),
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
    return (await output_rows(
        db,
        [request],
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    ))[0]


@router.patch("/material-requests/{request_id}", response_model=MaterialRequestOutput)
async def update_material_request(
    request_id: int,
    payload: MaterialRequestUpdate,
    user: CurrentUser,
    db: DbSession,
):
    request = await db.scalar(select(MaterialRequest).where(MaterialRequest.id == request_id).with_for_update())
    if not request:
        raise HTTPException(status_code=404, detail="Solicitação de material não encontrada.")

    previous = request.status
    previous_receipt = await db.scalar(select(InventoryMovement).where(InventoryMovement.material_request_id == request.id))
    if previous_receipt is not None and payload.status not in {"received", "delivered_to_lab"}:
        raise HTTPException(409, "Material já recebido em estoque; alteração de status requer estorno controlado.")
    if previous_receipt is not None and payload.unit_cost is not None and payload.unit_cost != request.unit_cost:
        raise HTTPException(409, "Material recebido não permite modificar o custo histórico de entrada.")
    stock_fields = (
        "inventory_destination", "inventory_item_id", "inventory_name", "inventory_mode",
        "inventory_serial", "inventory_category", "inventory_format_id",
    )
    if previous_receipt is not None and any(
        field in payload.model_fields_set and getattr(payload, field) != getattr(request, field)
        for field in stock_fields
    ):
        raise HTTPException(409, "O recebimento já foi registrado; dados de estoque não podem mais mudar.")
    if previous_receipt is None:
        for field in stock_fields:
            if field in payload.model_fields_set:
                setattr(request, field, getattr(payload, field))
    validate_transition(previous, payload.status)
    can_view_values = user_can_view_sensitive_values(user.role)
    if payload.unit_cost is not None and not can_view_values:
        _require_sensitive_values(user)
    if payload.status == "purchased" and not can_view_values:
        _require_sensitive_values(user)
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
    if can_view_values:
        request.unit_cost = payload.unit_cost
    request.expected_delivery_date = payload.expected_delivery_date
    apply_status_timestamps(request, previous, payload.status, user.id)
    if payload.status == "received" and previous_receipt is None:
        if previous == "received":
            raise HTTPException(409, "Recebimento antigo sem movimentação no Estoque. Exige conciliação manual, sem lançar novamente.")
        if request.inventory_destination not in {"new", "existing"}:
            raise HTTPException(422, "Antes de confirmar a entrega, escolha um item existente ou novo no Estoque.")
        linked_orders = (await db.scalars(select(PurchaseOrder).where(
            PurchaseOrder.code == (request.purchase_reference or ""),
            PurchaseOrder.company_code == request.company_code,
            PurchaseOrder.status == "delivered",
            PurchaseOrder.is_deleted.is_(False),
        ).limit(2))).all()
        if len(linked_orders) > 1:
            raise HTTPException(409, "Referência ambígua: vários pedidos entregues com mesmo código.")
        await receive_purchase(db, source="request", source_id=request.id,
            company_code=request.company_code, name=request.item_name,
            quantity=request.quantity, unit_cost=Decimal(request.unit_cost or 0),
            user_id=user.id, source_code=request.code,
            linked_source_id=linked_orders[0].id if linked_orders else None,
            destination=request.inventory_destination,
            target_item_id=request.inventory_item_id,
            stock_name=request.inventory_name,
            stock_mode=request.inventory_mode,
            stock_serial=request.inventory_serial,
            stock_category=request.inventory_category,
            stock_format_id=request.inventory_format_id)
    db.add(material_event(
        request,
        user_id=user.id,
        event_type="status_changed" if previous != payload.status else "updated",
        previous=previous,
        target=payload.status,
        note=payload.note,
    ))
    if previous != "approved" and payload.status == "approved" and request.work_order_id is not None:
        await notify_modules(
            db,
            modules={"laboratorio"},
            category="material_request_approved",
            severity="success",
            title=f"Material aprovado · {request.code}",
            message=f"Compras aprovou {request.quantity}x {request.item_name}. Acompanhe o andamento na O.S.",
            target=f"/laboratorio?os={request.work_order_id}&aba=materials",
            entity_type="material_request",
            entity_id=request.id,
            work_order_id=request.work_order_id,
            exclude_user_id=user.id,
        )
    if previous != "purchased" and payload.status == "purchased":
        await notify_modules(
            db,
            modules={"compras", "laboratorio"},
            category="purchase",
            severity="success",
            title=f"Compra realizada · {request.code}",
            message=f"{request.quantity}x {request.item_name} comprado(s). OS vinculada pronta para acompanhamento.",
            target=(f"/laboratorio?os={request.work_order_id}&aba=materials" if request.work_order_id else "/compras?view=requests"),
            entity_type="material_request",
            entity_id=request.id,
            work_order_id=request.work_order_id,
        )
    await recalculate_work_order_parts_cost(db, request.work_order_id)
    await db.commit()
    await db.refresh(request)
    return (await output_rows(
        db,
        [request],
        include_sensitive_values=can_view_values,
    ))[0]


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
