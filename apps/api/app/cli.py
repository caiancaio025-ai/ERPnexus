import argparse
import asyncio
import getpass

from sqlalchemy import or_, select

from app.auth.access import AVAILABLE_MODULES
from app.auth.models import User
from app.auth.security import hash_password
from app.core.db import session_factory


def required(label: str) -> str:
    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} é obrigatório.")
    return value


async def create_admin() -> None:
    name = required("Nome completo")
    email = required("E-mail").lower()
    username = required("Usuário").lower()
    password = getpass.getpass("Senha: ")
    confirmation = getpass.getpass("Confirmar senha: ")

    if password != confirmation:
        raise ValueError("As senhas não conferem.")
    if len(password) < 12:
        raise ValueError("A senha deve ter pelo menos 12 caracteres.")

    async with session_factory() as session:
        existing = await session.scalar(
            select(User).where(or_(User.email == email, User.username == username))
        )
        if existing:
            raise ValueError("E-mail ou usuário já cadastrado.")

        session.add(
            User(
                name=name,
                email=email,
                username=username,
                password_hash=hash_password(password),
                role="super_admin",
                modules=list(AVAILABLE_MODULES),
                is_active=True,
            )
        )
        await session.commit()

    print("Administrador criado com sucesso.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="nexus")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("create-admin")
    args = parser.parse_args()

    try:
        if args.command == "create-admin":
            asyncio.run(create_admin())
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
