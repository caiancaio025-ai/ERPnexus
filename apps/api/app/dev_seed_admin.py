"""Provisiona somente a conta ficticia de testes do SÊNTICO local.

NAO usar na VPS ou com banco real. Nunca atualiza senhas existentes.
"""

import asyncio
import os

from sqlalchemy import or_, select
from sqlalchemy.engine import make_url

from app.auth.access import AVAILABLE_MODULES
from app.auth.models import User
from app.auth.security import hash_password, verify_password
from app.core.config import settings
from app.core.db import session_factory

NAME = "adm"
EMAIL = "adm@.com.br"  # Literal solicitado; nao e endereco valido para entrega de e-mail.
USERNAME = "adm"
PASSWORD = "123"  # Apenas para testes locais. Nunca usar em producao.


def assert_local_dev_only() -> None:
    if settings.app_env != "development" or os.environ.get("SENTICO_DEV_TEST_ACCOUNT") != "1":
        raise RuntimeError("Conta ADM de teste permitida somente no ambiente de desenvolvimento isolado.")

    url = make_url(settings.database_url)
    if (url.host, url.database, url.username) != ("db", "sentico_dev", "sentico_dev"):
        raise RuntimeError("Banco diferente do sentico_dev isolado. Recusando cadastro de teste.")


async def provision() -> None:
    assert_local_dev_only()
    async with session_factory() as session:
        existing = await session.scalar(
            select(User).where(or_(User.username == USERNAME, User.email == EMAIL))
        )
        if existing is not None:
            if existing.username != USERNAME or existing.email != EMAIL:
                raise RuntimeError("Usuario/e-mail de teste ja esta ocupado por outra conta; sem sobrescrever.")
            if not verify_password(existing.password_hash, PASSWORD):
                raise RuntimeError("Conta adm existente possui outra senha; preservada sem alterar. Revisar manualmente.")
            if (
                existing.role != "super_admin"
                or not existing.is_active
                or not set(AVAILABLE_MODULES).issubset(set(existing.modules or []))
            ):
                raise RuntimeError("Conta adm ja existe com permissoes divergentes; preservada sem alterar.")
            print("ADM_TESTE_JA_EXISTIA=OK")
            return

        session.add(
            User(
                name=NAME,
                email=EMAIL,
                username=USERNAME,
                password_hash=hash_password(PASSWORD),
                role="super_admin",
                modules=list(AVAILABLE_MODULES),
                is_active=True,
            )
        )
        await session.commit()
        print("ADM_TESTE_CRIADO=OK")


if __name__ == "__main__":
    asyncio.run(provision())
