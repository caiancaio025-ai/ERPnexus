from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import normalize_modules
from app.auth.dependencies import require_admin, require_any_module
from app.auth.models import User, UserSession
from app.auth.router import current_user
from app.auth.security import hash_password
from app.core.db import get_db
from app.employees.models import Employee, EmployeeAuditEvent
from app.employees.schemas import (
    CollaboratorAccessCreate,
    CollaboratorAccessResponse,
    CollaboratorAccessUpdate,
    EmployeeCreate,
    EmployeeDetailResponse,
    EmployeeListResponse,
    EmployeeTerminateRequest,
    EmployeeUpdate,
    PaginatedEmployeeResponse,
)
from app.employees.service import EmployeeService

router = APIRouter(
    prefix="/employees",
    dependencies=[Depends(require_any_module("colaboradores", "configuracoes"))],
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
ManagerUser = Annotated[User, Depends(require_admin)]

OFFICIAL_ACCESS_ROLES = {"lab", "gestao", "admin"}
MANAGER_EQUIVALENT_ROLES = {"gestao", "super_admin"}


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(maxsplit=1)
    return parts[0] if parts else "", parts[1] if len(parts) > 1 else ""


def _internal_email(username: str) -> str:
    return f"{username}@nexus.local"


def _response(user: User, employee: Employee | None) -> CollaboratorAccessResponse:
    first_name, last_name = _split_name(user.name)
    return CollaboratorAccessResponse(
        employee_id=employee.id if employee else None,
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        full_name=user.name,
        phone=employee.phone if employee else None,
        role="gestao" if user.role == "super_admin" else ("lab" if user.role == "tecnico" else user.role),
        username=user.username,
        is_active=user.is_active,
    )


async def _ensure_access_unique(
    db: AsyncSession,
    username: str,
    *,
    exclude_user_id: int | None = None,
) -> None:
    query = select(User.id).where(
        or_(User.username == username, User.email == _internal_email(username))
    )
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    if await db.scalar(query):
        raise HTTPException(status_code=409, detail="ID de acesso já cadastrado.")


async def _ensure_not_last_manager(
    db: AsyncSession,
    target: User,
    *,
    next_role: str,
    next_active: bool,
) -> None:
    if target.role not in MANAGER_EQUIVALENT_ROLES:
        return
    remains_manager = next_active and next_role in MANAGER_EQUIVALENT_ROLES
    if remains_manager:
        return
    active_managers = int(
        await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.is_active.is_(True), User.role.in_(MANAGER_EQUIVALENT_ROLES))
        )
        or 0
    )
    if active_managers <= 1:
        raise HTTPException(
            status_code=400,
            detail="Não é possível remover ou desativar o último Gestor ativo do sistema.",
        )


@router.get("/access", response_model=list[CollaboratorAccessResponse])
async def list_collaborator_access(db: DbSession, _: CurrentUser) -> list[CollaboratorAccessResponse]:
    rows = (
        await db.execute(
            select(User, Employee)
            .outerjoin(Employee, Employee.user_id == User.id)
            .where(User.role.in_(("super_admin", "admin", "gestao", "lab", "tecnico")))
            .order_by(User.is_active.desc(), User.name.asc(), User.id.asc())
        )
    ).all()
    return [_response(user, employee) for user, employee in rows]


@router.post("/access", response_model=CollaboratorAccessResponse, status_code=status.HTTP_201_CREATED)
async def create_collaborator_access(
    payload: CollaboratorAccessCreate,
    db: DbSession,
    actor: ManagerUser,
) -> CollaboratorAccessResponse:
    role = payload.role.strip().lower()
    if role not in OFFICIAL_ACCESS_ROLES:
        raise HTTPException(status_code=422, detail="Perfil deve ser LAB, GESTÃO ou ADM.")

    username = payload.username.strip().lower()
    await _ensure_access_unique(db, username)

    full_name = f"{payload.first_name.strip()} {payload.last_name.strip()}".strip()
    user = User(
        name=full_name,
        email=_internal_email(username),
        username=username,
        password_hash=hash_password(payload.password),
        role=role,
        modules=normalize_modules(role, None),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    employee = Employee(
        company_code="universo_eletronica",
        user_id=user.id,
        full_name=full_name,
        document=f"NEXUS{user.id:08d}",
        document_type="cpf",
        phone=payload.phone.strip(),
        department=role.upper(),
        position=role.upper(),
        salary_base=Decimal("0.00"),
        hiring_date=date.today(),
        employment_type="clt",
        created_by=actor.id,
        is_active=True,
    )
    db.add(employee)
    await db.flush()
    db.add(
        EmployeeAuditEvent(
            employee_id=employee.id,
            action="access_created",
            description=f"Acesso {username} criado para {full_name} com perfil {role.upper()}",
            user_id=actor.id,
            after_data={"username": username, "role": role, "is_active": True},
        )
    )
    await db.commit()
    await db.refresh(user)
    await db.refresh(employee)
    return _response(user, employee)


@router.put("/access/{user_id}", response_model=CollaboratorAccessResponse)
async def update_collaborator_access(
    user_id: int,
    payload: CollaboratorAccessUpdate,
    db: DbSession,
    actor: ManagerUser,
) -> CollaboratorAccessResponse:
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    employee = await db.scalar(select(Employee).where(Employee.user_id == target.id))

    changes = payload.model_dump(exclude_unset=True)
    next_role = str(changes.get("role", "gestao" if target.role == "super_admin" else target.role)).strip().lower()
    if next_role not in OFFICIAL_ACCESS_ROLES:
        raise HTTPException(status_code=422, detail="Perfil deve ser LAB, GESTÃO ou ADM.")
    next_active = bool(changes.get("is_active", target.is_active))

    if actor.id == target.id and not next_active:
        raise HTTPException(status_code=400, detail="Você não pode desativar seu próprio acesso.")
    await _ensure_not_last_manager(db, target, next_role=next_role, next_active=next_active)

    next_username = str(changes.get("username", target.username)).strip().lower()
    await _ensure_access_unique(db, next_username, exclude_user_id=target.id)

    first_name, last_name = _split_name(target.name)
    first_name = str(changes.get("first_name", first_name)).strip()
    last_name = str(changes.get("last_name", last_name)).strip()
    full_name = f"{first_name} {last_name}".strip()

    before = {
        "name": target.name,
        "username": target.username,
        "role": target.role,
        "is_active": target.is_active,
    }

    target.name = full_name
    target.username = next_username
    target.email = _internal_email(next_username)
    target.role = next_role
    target.modules = normalize_modules(next_role, None)
    target.is_active = next_active

    invalidate_sessions = False
    if "password" in changes and changes["password"]:
        target.password_hash = hash_password(str(changes["password"]))
        invalidate_sessions = True
    if not next_active:
        invalidate_sessions = True

    if employee:
        employee.full_name = full_name
        employee.phone = str(changes.get("phone", employee.phone or "")).strip() or None
        employee.department = next_role.upper()
        employee.position = next_role.upper()
        employee.is_active = next_active

    if invalidate_sessions:
        await db.execute(UserSession.__table__.delete().where(UserSession.user_id == target.id))

    db.add(
        EmployeeAuditEvent(
            employee_id=employee.id if employee else None,
            action="access_updated",
            description=f"Acesso {next_username} atualizado por {actor.username}",
            user_id=actor.id,
            before_data=before,
            after_data={
                "name": full_name,
                "username": next_username,
                "role": next_role,
                "is_active": next_active,
                "password_reset": bool(changes.get("password")),
            },
        )
    )
    await db.commit()
    await db.refresh(target)
    if employee:
        await db.refresh(employee)
    return _response(target, employee)


# Endpoints funcionais legados permanecem disponíveis para dados históricos.
@router.get("", response_model=PaginatedEmployeeResponse)
async def list_employees(
    db: DbSession,
    _: ManagerUser,
    company_code: str = Query("universo_eletronica"),
    department: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    employees, total = await EmployeeService.get_employees(
        db, company_code, department, is_active, limit, offset
    )
    return PaginatedEmployeeResponse(
        total=total,
        limit=limit,
        offset=offset,
        data=[EmployeeListResponse.model_validate(item) for item in employees],
    )


@router.post("", response_model=EmployeeDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeCreate, db: DbSession, user: CurrentUser, _: User = Depends(require_admin)):
    exists = await db.scalar(
        select(Employee.id).where(
            Employee.company_code == payload.company_code,
            Employee.document == payload.document,
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="Já existe colaborador com este CPF/CNPJ para a empresa.")
    employee = await EmployeeService.create_employee(db, payload, user.id)
    return EmployeeDetailResponse.model_validate(employee)


@router.get("/{employee_id}", response_model=EmployeeDetailResponse)
async def get_employee(employee_id: int, db: DbSession, _: ManagerUser):
    employee = await EmployeeService.get_employee(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)


@router.put("/{employee_id}", response_model=EmployeeDetailResponse)
async def update_employee(employee_id: int, payload: EmployeeUpdate, db: DbSession, user: CurrentUser, _: User = Depends(require_admin)):
    employee = await EmployeeService.update_employee(db, employee_id, payload, user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)


@router.post("/{employee_id}/terminate", response_model=EmployeeDetailResponse)
async def terminate_employee(employee_id: int, payload: EmployeeTerminateRequest, db: DbSession, user: CurrentUser, _: User = Depends(require_admin)):
    employee = await EmployeeService.terminate_employee(db, employee_id, payload, user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)


@router.post("/{employee_id}/reactivate", response_model=EmployeeDetailResponse)
async def reactivate_employee(employee_id: int, db: DbSession, user: CurrentUser, _: User = Depends(require_admin)):
    employee = await EmployeeService.reactivate_employee(db, employee_id, user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)
