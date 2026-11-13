from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.access import ADMIN_ROLES, user_can_manage_collaborators, user_has_module
from app.auth.models import User
from app.auth.router import current_user

CurrentUser = Annotated[User, Depends(current_user)]


def require_module(module: str) -> Callable[..., Awaitable[User]]:
    async def dependency(user: CurrentUser) -> User:
        if not user_has_module(user.role, user.modules, module):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Seu usuário não possui acesso ao módulo {module}.",
            )
        return user

    return dependency


async def require_admin(user: CurrentUser) -> User:
    """Compatibilidade: administração de usuários é exclusiva da Gestão.

    super_admin é o usuário bootstrap legado e é tratado como Gestão para não
    bloquear o ambiente existente. O perfil ADM não gerencia colaboradores.
    """
    if not user_can_manage_collaborators(user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o perfil Gestão pode gerenciar colaboradores.",
        )
    return user


async def require_general_admin(user: CurrentUser) -> User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso administrativo necessário.",
        )
    return user


def require_any_module(*modules: str) -> Callable[..., Awaitable[User]]:
    async def dependency(user: CurrentUser) -> User:
        if not any(user_has_module(user.role, user.modules, module) for module in modules):
            allowed = ", ".join(modules)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Seu usuário precisa de acesso a um destes módulos: {allowed}.",
            )
        return user

    return dependency
