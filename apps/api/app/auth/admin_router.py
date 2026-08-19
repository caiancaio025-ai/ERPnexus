from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import normalize_modules, normalize_role
from app.auth.dependencies import require_admin
from app.auth.models import User, UserSession
from app.auth.schemas import AdminUserCreate, AdminUserUpdate, UserOutput
from app.auth.security import hash_password
from app.core.db import get_db

router = APIRouter(prefix="/admin/users")

AdminUser = Annotated[User, Depends(require_admin)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _ensure_super_admin_control(actor: User, target_role: str) -> None:
    if target_role == "super_admin" and actor.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente um super_admin pode gerenciar outro super_admin.",
        )


async def _user_or_404(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return user


async def _ensure_unique(
    db: AsyncSession,
    email: str,
    username: str,
    exclude_user_id: int | None = None,
) -> None:
    query = select(User).where(or_(User.email == email, User.username == username))
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    if await db.scalar(query):
        raise HTTPException(status_code=409, detail="E-mail ou usuário já cadastrado.")


@router.get("", response_model=list[UserOutput])
async def list_users(
    _: AdminUser,
    db: DbSession,
) -> list[User]:
    return list((await db.scalars(select(User).order_by(User.name, User.id))).all())


@router.post("", response_model=UserOutput, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate,
    actor: AdminUser,
    db: DbSession,
) -> User:
    role = normalize_role(payload.role)
    _ensure_super_admin_control(actor, role)
    email = payload.email.strip().lower()
    username = payload.username.strip().lower()
    await _ensure_unique(db, email, username)

    user = User(
        name=payload.name.strip(),
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
        role=role,
        modules=normalize_modules(role, payload.modules),
        is_active=payload.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOutput)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    actor: AdminUser,
    db: DbSession,
) -> User:
    target = await _user_or_404(db, user_id)
    _ensure_super_admin_control(actor, target.role)

    changes = payload.model_dump(exclude_unset=True)
    next_role = normalize_role(changes.get("role", target.role))
    _ensure_super_admin_control(actor, next_role)

    if actor.id == target.id and changes.get("is_active") is False:
        raise HTTPException(status_code=400, detail="Você não pode desativar seu próprio usuário.")

    next_email = str(changes.get("email", target.email)).strip().lower()
    next_username = str(changes.get("username", target.username)).strip().lower()
    await _ensure_unique(db, next_email, next_username, exclude_user_id=target.id)

    if "name" in changes:
        target.name = str(changes["name"]).strip()
    target.email = next_email
    target.username = next_username
    target.role = next_role
    if "password" in changes:
        target.password_hash = hash_password(str(changes["password"]))
    if "is_active" in changes:
        target.is_active = bool(changes["is_active"])
    selected_modules = changes.get("modules")
    if selected_modules is None and "role" not in changes:
        selected_modules = target.modules
    target.modules = normalize_modules(next_role, selected_modules)

    if not target.is_active:
        await db.execute(UserSession.__table__.delete().where(UserSession.user_id == target.id))

    await db.commit()
    await db.refresh(target)
    return target


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    actor: AdminUser,
    db: DbSession,
) -> Response:
    target = await _user_or_404(db, user_id)
    _ensure_super_admin_control(actor, target.role)
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail="Você não pode desativar seu próprio usuário.")
    target.is_active = False
    await db.execute(UserSession.__table__.delete().where(UserSession.user_id == target.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
