"""Preflight de escrita, somente no banco isolado da recuperacao V14.

Sem DDL permanente: CREATE TEMP TABLE dentro de transacao revertida.
Nunca imprime DATABASE_URL, excecoes contendo credenciais ou dados de cliente.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import settings


EXPECTED_DATABASE = os.environ.get("SENTICO_DB_NAME", "")
EXPECTED_ROLE = os.environ.get("SENTICO_DB_ROLE", "sentico_green")
ALLOWED_REVISIONS = {"20261013_02", "20261022_01", "20261022_02", "20261026_01",
                     "20261026_02", "20261026_03", "20261027_01", "20261027_02",
                     "20261027_03", "20261027_04", "20261027_05", "20261028_01", "20261112_01"}


def fail(marker: str, code: int = 1) -> None:
    print(marker, flush=True)
    raise SystemExit(code)


def main() -> None:
    if not EXPECTED_DATABASE.isidentifier() or EXPECTED_DATABASE == "postgres" or not EXPECTED_DATABASE.isascii():
        fail("ERRO_API_NOME_BANCO_NAO_APROVADO")
    if not EXPECTED_ROLE.isidentifier() or not EXPECTED_ROLE.isascii():
        fail("ERRO_API_NOME_ROLE_INVALIDO")
    engine = None
    try:
        engine = create_engine(settings.database_url, poolclass=NullPool, connect_args={"connect_timeout": 8})
        with engine.connect() as connection:
            database, role, is_recovery, read_only = connection.execute(
                text("SELECT current_database(), current_user, pg_is_in_recovery(), current_setting('transaction_read_only')")
            ).one()
            if database != EXPECTED_DATABASE or role != EXPECTED_ROLE:
                fail("ERRO_API_IDENTIDADE")
            # Garantir que a conexao e com um banco SÊNTICO reconhecido.
            rev = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
            if rev not in ALLOWED_REVISIONS:
                fail("ERRO_API_REVISAO_NAO_COMPATIVEL")
            if is_recovery:
                fail("ERRO_API_EM_RECUPERACAO")
            if read_only == "on":
                fail("ERRO_API_READ_ONLY")
            if read_only != "off":
                fail("ERRO_API_ESTADO_TRANSACAO_INESPERADO")
            # Cria tabela TEMPORARIA somente na conexao, em transacao revertida.
            # Assim comprova escrita real sem alterar estrutura persistente.
            try:
                connection.execute(text("CREATE TEMP TABLE sentico_v14_preflight_write(id integer) ON COMMIT DROP"))
            except Exception as exc:
                state = getattr(getattr(exc, "orig", None), "sqlstate", None)
                if state == "25006":
                    fail("ERRO_API_READ_ONLY")
                fail("ERRO_API_DDL_TEMPORARIO")
            finally:
                connection.rollback()
        print("OK_API_ESCRITA_TRANSACIONAL", flush=True)
    except SystemExit:
        raise
    except Exception:
        fail("ERRO_API_CONEXAO_OU_CONFIGURACAO")
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
