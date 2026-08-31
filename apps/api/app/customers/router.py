from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_any_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload, validate_upload
from app.customers.models import (
    CustomerBillingProfile,
    CustomerContact,
    CustomerDocument,
    CustomerNote,
)
from app.customers.storage import (
    commit_customer_document,
    delete_customer_document as delete_customer_document_storage,
    persist_customer_document,
    resolve_customer_storage_path,
)
from app.customers.schemas import (
    BillingInput,
    ContactInput,
    ContactOutput,
    CustomerCreate,
    CustomerDetail,
    CustomerDocumentPage,
    CustomerEquipmentPage,
    CustomerListItem,
    CustomerNotePage,
    CustomerPage,
    CustomerQuotePage,
    CustomerQuoteSummary,
    CustomerWorkOrderPage,
    CustomerUpdate,
    DocumentOutput,
    NoteInput,
    NoteOutput,
)
from app.customers.service import (
    customer_overview_summary,
    list_customer_documents_page,
    list_customer_equipment_page,
    list_customer_notes_page,
    list_customer_quotes_page,
    list_customer_work_orders_page,
    list_customers_page,
)
from app.laboratory.models import (
    LaboratoryCustomer,
    LaboratoryEquipment,
    LaboratoryQuote,
    LaboratoryWorkOrder,
)

router = APIRouter(
    prefix="/customers",
    dependencies=[Depends(require_any_module("laboratorio", "comercial", "financeiro"))],
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
CustomerFile = Annotated[UploadFile, File()]
DocumentCategory = Annotated[str, Form()]
ReferenceNumber = Annotated[str | None, Form()]
DocumentNotes = Annotated[str | None, Form()]
IssueDate = Annotated[date | None, Form()]
ExpirationDate = Annotated[date | None, Form()]
CompanyFilter = Annotated[str | None, Query()]
SearchFilter = Annotated[str | None, Query(max_length=160)]
PageFilter = Annotated[int, Query(ge=1)]
PageSizeFilter = Annotated[int, Query(ge=1, le=200)]

UPLOAD_ROOT = Path(settings.storage_root) / "customers"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@router.get("/page", response_model=CustomerPage)
async def list_customers_paginated(
    db: DbSession,
    _: CurrentUser,
    company_code: CompanyFilter = None,
    search: SearchFilter = None,
    page: PageFilter = 1,
    page_size: PageSizeFilter = 100,
):
    result = await list_customers_page(
        db,
        page=page,
        page_size=page_size,
        company_code=company_code,
        search=search,
    )
    return CustomerPage(
        items=result.items,
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("", response_model=list[CustomerListItem])
async def list_customers(
    db: DbSession,
    _: CurrentUser,
    company_code: CompanyFilter = None,
    search: SearchFilter = None,
):
    query = select(LaboratoryCustomer).where(LaboratoryCustomer.is_active.is_(True))
    if company_code:
        query = query.where(LaboratoryCustomer.company_code == company_code)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                LaboratoryCustomer.legal_name.ilike(term),
                LaboratoryCustomer.trade_name.ilike(term),
                LaboratoryCustomer.document.ilike(term),
                LaboratoryCustomer.email.ilike(term),
            )
        )
    query = query.order_by(LaboratoryCustomer.legal_name).limit(500)
    return list((await db.scalars(query)).all())


@router.post("", response_model=CustomerListItem, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate, db: DbSession, user: CurrentUser
):
    if payload.document:
        exists = await db.scalar(
            select(LaboratoryCustomer.id).where(
                LaboratoryCustomer.company_code == payload.company_code,
                LaboratoryCustomer.document == payload.document,
            )
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe cliente com este documento para a empresa.",
            )
    customer = LaboratoryCustomer(**payload.model_dump(), created_by=user.id)
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def _customer_or_404(db: AsyncSession, customer_id: int) -> LaboratoryCustomer:
    customer = await db.get(LaboratoryCustomer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return customer


@router.get("/{customer_id}", response_model=CustomerDetail)
async def get_customer(customer_id: int, db: DbSession, _: CurrentUser):
    customer = await _customer_or_404(db, customer_id)
    contacts = list(
        (
            await db.scalars(
                select(CustomerContact)
                .where(
                    CustomerContact.customer_id == customer_id,
                    CustomerContact.is_active.is_(True),
                )
                .order_by(CustomerContact.is_primary.desc(), CustomerContact.name)
            )
        ).all()
    )
    billing = await db.get(CustomerBillingProfile, customer_id)
    notes = list(
        (
            await db.scalars(
                select(CustomerNote)
                .where(CustomerNote.customer_id == customer_id)
                .order_by(CustomerNote.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    documents = list(
        (
            await db.scalars(
                select(CustomerDocument)
                .where(CustomerDocument.customer_id == customer_id)
                .order_by(CustomerDocument.created_at.desc())
            )
        ).all()
    )
    overview = await customer_overview_summary(db, customer_id=customer_id)
    equipment = list(
        (
            await db.scalars(
                select(LaboratoryEquipment)
                .where(
                    LaboratoryEquipment.customer_id == customer_id,
                    LaboratoryEquipment.is_active.is_(True),
                )
                .order_by(LaboratoryEquipment.updated_at.desc())
                .limit(200)
            )
        ).all()
    )
    work_orders = list(
        (
            await db.scalars(
                select(LaboratoryWorkOrder)
                .where(LaboratoryWorkOrder.customer_id == customer_id)
                .order_by(LaboratoryWorkOrder.opened_at.desc(), LaboratoryWorkOrder.id.desc())
                .limit(200)
            )
        ).all()
    )
    quote_rows = list(
        (
            await db.execute(
                select(LaboratoryQuote, LaboratoryWorkOrder.number)
                .join(
                    LaboratoryWorkOrder,
                    LaboratoryQuote.work_order_id == LaboratoryWorkOrder.id,
                )
                .where(LaboratoryWorkOrder.customer_id == customer_id)
                .order_by(LaboratoryQuote.created_at.desc())
                .limit(200)
            )
        ).all()
    )
    quote_summaries = [
        CustomerQuoteSummary(
            id=quote.id,
            work_order_id=quote.work_order_id,
            work_order_number=work_order_number,
            revision=quote.revision,
            status=quote.status,
            total=float(quote.total or 0),
            emitted_at=quote.emitted_at,
            created_at=quote.created_at,
        )
        for quote, work_order_number in quote_rows
    ]
    values = {
        column.name: getattr(customer, column.name)
        for column in customer.__table__.columns
        if column.name not in {"created_by", "created_at", "updated_at"}
    }
    return CustomerDetail(
        **values,
        equipment_count=overview.equipment_count,
        work_orders_count=overview.work_orders_count,
        quotes_count=overview.quotes_count,
        quotes_total=overview.quotes_total,
        recent_work_orders=overview.recent_work_orders,
        contacts=contacts,
        billing=billing,
        notes_history=notes,
        documents=documents,
        equipment=equipment,
        work_orders=work_orders,
        quotes=quote_summaries,
    )


@router.get("/{customer_id}/equipment/page", response_model=CustomerEquipmentPage)
async def get_customer_equipment_page(
    customer_id: int,
    db: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    await _customer_or_404(db, customer_id)
    result = await list_customer_equipment_page(
        db, customer_id=customer_id, page=page, page_size=page_size
    )
    return CustomerEquipmentPage(items=result.items, page=result.page, page_size=result.page_size, total=result.total, pages=result.pages)


@router.get("/{customer_id}/work-orders/page", response_model=CustomerWorkOrderPage)
async def get_customer_work_orders_page(
    customer_id: int,
    db: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    await _customer_or_404(db, customer_id)
    result = await list_customer_work_orders_page(
        db, customer_id=customer_id, page=page, page_size=page_size
    )
    return CustomerWorkOrderPage(items=result.items, page=result.page, page_size=result.page_size, total=result.total, pages=result.pages)


@router.get("/{customer_id}/quotes/page", response_model=CustomerQuotePage)
async def get_customer_quotes_page(
    customer_id: int,
    db: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    await _customer_or_404(db, customer_id)
    result = await list_customer_quotes_page(
        db, customer_id=customer_id, page=page, page_size=page_size
    )
    return CustomerQuotePage(items=result.items, page=result.page, page_size=result.page_size, total=result.total, pages=result.pages)


@router.get("/{customer_id}/notes/page", response_model=CustomerNotePage)
async def get_customer_notes_page(
    customer_id: int,
    db: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    await _customer_or_404(db, customer_id)
    result = await list_customer_notes_page(
        db, customer_id=customer_id, page=page, page_size=page_size
    )
    return CustomerNotePage(items=result.items, page=result.page, page_size=result.page_size, total=result.total, pages=result.pages)


@router.get("/{customer_id}/documents/page", response_model=CustomerDocumentPage)
async def get_customer_documents_page(
    customer_id: int,
    db: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    await _customer_or_404(db, customer_id)
    result = await list_customer_documents_page(
        db, customer_id=customer_id, page=page, page_size=page_size
    )
    return CustomerDocumentPage(items=result.items, page=result.page, page_size=result.page_size, total=result.total, pages=result.pages)


@router.put("/{customer_id}", response_model=CustomerDetail)
async def update_customer(
    customer_id: int, payload: CustomerUpdate, db: DbSession, user: CurrentUser
):
    customer = await _customer_or_404(db, customer_id)
    for field, value in payload.model_dump().items():
        setattr(customer, field, value)
    await db.commit()
    return await get_customer(customer_id, db, user)


@router.post("/{customer_id}/contacts", response_model=ContactOutput, status_code=201)
async def create_contact(
    customer_id: int, payload: ContactInput, db: DbSession, user: CurrentUser
):
    await _customer_or_404(db, customer_id)
    if payload.is_primary:
        rows = await db.scalars(
            select(CustomerContact).where(CustomerContact.customer_id == customer_id)
        )
        for item in rows:
            item.is_primary = False
    contact = CustomerContact(
        customer_id=customer_id, created_by=user.id, **payload.model_dump()
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.put("/{customer_id}/contacts/{contact_id}", response_model=ContactOutput)
async def update_contact(
    customer_id: int,
    contact_id: int,
    payload: ContactInput,
    db: DbSession,
    _: CurrentUser,
):
    contact = await db.get(CustomerContact, contact_id)
    if not contact or contact.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    if payload.is_primary:
        rows = await db.scalars(
            select(CustomerContact).where(
                CustomerContact.customer_id == customer_id,
                CustomerContact.id != contact_id,
            )
        )
        for item in rows:
            item.is_primary = False
    for field, value in payload.model_dump().items():
        setattr(contact, field, value)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.delete(
    "/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def deactivate_contact(
    customer_id: int, contact_id: int, db: DbSession, _: CurrentUser
):
    contact = await db.get(CustomerContact, contact_id)
    if not contact or contact.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    contact.is_active = False
    contact.is_primary = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{customer_id}/billing")
async def save_billing(
    customer_id: int, payload: BillingInput, db: DbSession, user: CurrentUser
):
    await _customer_or_404(db, customer_id)
    billing = await db.get(CustomerBillingProfile, customer_id)
    if billing is None:
        billing = CustomerBillingProfile(customer_id=customer_id, updated_by=user.id)
        db.add(billing)
    for field, value in payload.model_dump().items():
        setattr(billing, field, value)
    billing.updated_by = user.id
    await db.commit()
    await db.refresh(billing)
    return billing


@router.post("/{customer_id}/notes", response_model=NoteOutput, status_code=201)
async def create_note(
    customer_id: int, payload: NoteInput, db: DbSession, user: CurrentUser
):
    await _customer_or_404(db, customer_id)
    note = CustomerNote(
        customer_id=customer_id, created_by=user.id, **payload.model_dump()
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.post("/{customer_id}/documents", response_model=DocumentOutput, status_code=201)
async def upload_document(
    customer_id: int,
    file: CustomerFile,
    category: DocumentCategory,
    db: DbSession,
    user: CurrentUser,
    reference_number: ReferenceNumber = None,
    issue_date: IssueDate = None,
    expiration_date: ExpirationDate = None,
    notes: DocumentNotes = None,
):
    await _customer_or_404(db, customer_id)
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 10 MB.")
    try:
        detected = validate_upload(content, file.filename, file.content_type)
    except InvalidUpload as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    checksum = sha256(content).hexdigest()
    try:
        path = persist_customer_document(
            UPLOAD_ROOT,
            customer_id=customer_id,
            extension=detected.extension,
            content=content,
        )
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="Armazenamento de documentos indisponível. Verifique o volume /app/storage da API.",
        ) from exc
    document = CustomerDocument(
        customer_id=customer_id,
        category=category,
        reference_number=reference_number,
        issue_date=issue_date,
        expiration_date=expiration_date,
        original_name=file.filename or path.name,
        storage_path=str(path),
        mime_type=detected.mime_type,
        size_bytes=len(content),
        checksum_sha256=checksum,
        notes=notes,
        uploaded_by=user.id,
    )
    await commit_customer_document(
        db,
        document,
        root=UPLOAD_ROOT,
        stored_path=path,
    )
    return document


@router.get("/{customer_id}/documents/{document_id}")
async def preview_document(
    customer_id: int, document_id: int, db: DbSession, _: CurrentUser
):
    document = await db.get(CustomerDocument, document_id)
    if not document or document.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    try:
        path = resolve_customer_storage_path(UPLOAD_ROOT, document.storage_path)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Caminho de armazenamento inválido.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no storage.")
    return FileResponse(path, media_type=document.mime_type, filename=document.original_name)


@router.delete(
    "/{customer_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_document(
    customer_id: int, document_id: int, db: DbSession, _: CurrentUser
):
    document = await db.get(CustomerDocument, document_id)
    if not document or document.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    try:
        await delete_customer_document_storage(db, document, root=UPLOAD_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Caminho de armazenamento inválido.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
