"""Cria um administrador PADRAO de teste, se o banco ainda nao tiver nenhum usuario.

Uso exclusivo do ambiente LOCAL de teste (compose.dev). Recusa rodar fora de
APP_ENV=development e nao faz nada se ja existir qualquer usuario (idempotente).
As credenciais sao fracas de proposito, so para o banco isolado local — troque
depois de entrar.
"""

import asyncio
import os
import sys

sys.path.insert(0, "/app")  # garante que "app" seja importavel ao rodar por caminho

from sqlalchemy import func, select  # noqa: E402

from app.auth.access import AVAILABLE_MODULES  # noqa: E402
from app.auth.models import User  # noqa: E402
from app.auth.security import hash_password  # noqa: E402
from app.core.db import session_factory  # noqa: E402

ADMIN_PADRAO = {
    "name": "Administrador",
    "email": "admin@local.test",
    "username": "admin",
    "password": "senticolocal2026",  # 16 caracteres; so para o ambiente local isolado
}


async def main() -> None:
    if os.environ.get("APP_ENV", "") != "development":
        raise SystemExit("Recusado: criar_admin_padrao so roda em APP_ENV=development.")

    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(User))
        if total:
            print(f"Ja existe usuario ({total}); mantendo o login atual.")
            return
        session.add(
            User(
                name=ADMIN_PADRAO["name"],
                email=ADMIN_PADRAO["email"],
                username=ADMIN_PADRAO["username"],
                password_hash=hash_password(ADMIN_PADRAO["password"]),
                role="super_admin",
                modules=list(AVAILABLE_MODULES),
                is_active=True,
            )
        )
        await session.commit()

    print("Admin padrao criado -> usuario: admin | senha: senticolocal2026 (TROQUE depois).")


if __name__ == "__main__":
    asyncio.run(main())
