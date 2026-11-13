from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User, UserSession
from app.auth.rate_limit import (
    clear_identifier_failures,
    login_rate_limit_state,
    record_failed_login,
)
from app.auth.schemas import LoginInput, UserOutput
from app.auth.security import create_session_token, hash_session_token, verify_password
from app.core.config import settings
from app.core.db import get_db

router = APIRouter(prefix="/auth")

DbSession = Annotated[AsyncSession, Depends(get_db)]
SessionToken = Annotated[str | None, Cookie(alias=settings.session_cookie_name)]


async def current_user(
    db: DbSession,
    session_token: SessionToken = None,
) -> User:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão não encontrada.",
        )

    now = datetime.now(UTC)
    query = (
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(
            UserSession.token_hash == hash_session_token(session_token),
            UserSession.expires_at > now,
        )
    )
    user_session = await db.scalar(query)
    if not user_session or not user_session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida.")
    return user_session.user


def _raise_rate_limit(retry_after: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Muitas tentativas de acesso. Aguarde alguns minutos e tente novamente.",
        headers={"Retry-After": str(max(1, retry_after))},
    )


@router.post("/login", response_model=UserOutput)
async def login(
    payload: LoginInput,
    request: Request,
    response: Response,
    db: DbSession,
) -> User:
    identifier = payload.identifier.strip().lower()

    rate_limit = await login_rate_limit_state(db, request, identifier)
    if rate_limit.blocked:
        _raise_rate_limit(rate_limit.retry_after)

    user = await db.scalar(
        select(User).where(or_(User.email == identifier, User.username == identifier))
    )
    if not user or not user.is_active or not verify_password(user.password_hash, payload.password):
        rate_limit = await record_failed_login(db, request, identifier)
        if rate_limit.blocked:
            _raise_rate_limit(rate_limit.retry_after)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID, e-mail ou senha inválidos.",
        )

    await clear_identifier_failures(db, identifier)

    token = create_session_token()
    expires_at = datetime.now(UTC) + timedelta(hours=settings.session_hours)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
        )
    )
    await db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return user


@router.get("/me", response_model=UserOutput)
async def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: DbSession,
    session_token: SessionToken = None,
) -> Response:
    if session_token:
        await db.execute(
            delete(UserSession).where(
                UserSession.token_hash == hash_session_token(session_token)
            )
        )
        await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
