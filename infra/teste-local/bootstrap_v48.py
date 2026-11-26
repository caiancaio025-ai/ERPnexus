"""Bootstrap exclusivo do Compose local; não importa nem redefine dados existentes."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


BASELINE = "20261009_01"
TARGET = "20261126_04"
READY_UPGRADES = {"20261126_01", "20261126_02", "20261126_03"}
DATABASE = "sentico_v48_test"
USERNAME = "teste_v48"
MARKER = "sentico_local_test_bootstrap"
SIGNATURE = "sentico-v48-teste-local/v1"
LOCK = 148048


class BootstrapError(Exception):
    """Somente mensagens fixas, sem credenciais nem conteúdo de exceções externas."""


@dataclass(frozen=True)
class LocalConfig:
    database_url: str = field(repr=False)
    instance: str = field(repr=False)
    password: str = field(repr=False)


def local_config(environ=None) -> LocalConfig:
    env = os.environ if environ is None else environ
    if env.get("APP_ENV") != "development" or env.get("SENTICO_LOCAL_TEST_RUN") != "v48":
        raise BootstrapError("Ambiente de teste local não confirmado.")
    instance = env.get("SENTICO_LOCAL_TEST_INSTANCE", "")
    password = env.get("SENTICO_LOCAL_TEST_PASSWORD", "")
    if not re.fullmatch(r"[0-9a-f]{48}", instance) or not re.fullmatch(r"[0-9a-f]{32}", password):
        raise BootstrapError("Identificação ou credencial local inválida.")
    raw_url = env.get("DATABASE_URL", "")
    try:
        url = make_url(raw_url)
        valid = (
            url.drivername == "postgresql+psycopg" and url.host == "db" and url.port == 5432
            and url.database == DATABASE and url.username == DATABASE
            and re.fullmatch(r"[0-9a-f]{64}", url.password or "") and not url.query
        )
    except Exception:
        valid = False
    if not valid:
        raise BootstrapError("O destino não corresponde ao banco exclusivo de teste local.")
    return LocalConfig(raw_url, instance, password)


def migration_plan(workdir: Path) -> list[str]:
    if not (workdir / "alembic.ini").is_file() or not (workdir / "migrations").is_dir():
        raise BootstrapError("Arquivos de migração ausentes na imagem de teste.")
    config = Config(str(workdir / "alembic.ini"))
    config.set_main_option("script_location", str(workdir / "migrations"))
    script = ScriptDirectory.from_config(config)
    if script.get_heads() != [TARGET]:
        raise BootstrapError("A imagem não corresponde à revisão esperada para este teste.")
    revisions = [revision.revision for revision in reversed(list(script.walk_revisions()))]
    if BASELINE not in revisions:
        raise BootstrapError("A imagem não contém a migração inicial esperada.")
    return revisions


def open_engine(config: LocalConfig):
    return create_engine(config.database_url, poolclass=NullPool, connect_args={"connect_timeout": 10})


def upgrade(revision: str, workdir: Path) -> None:
    # Alembic pode escrever detalhes SQL em erros: saída fica somente em memória.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision], cwd=workdir,
        env=os.environ.copy(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=300, check=False,
    )
    if result.returncode:
        raise BootstrapError("A preparação do esquema não foi concluída; os dados foram preservados.")


def current_revision(connection) -> str | None:
    if connection.scalar(text("SELECT to_regclass('public.alembic_version')")) is None:
        return None
    rows = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all()
    if len(rows) != 1:
        raise BootstrapError("Revisão do banco local ausente ou ambígua.")
    return rows[0]


def claim_database(connection, config: LocalConfig) -> dict:
    identity = connection.execute(text("SELECT current_database(), current_user, session_user")).one()
    if tuple(identity) != (DATABASE, DATABASE, DATABASE):
        raise BootstrapError("A identidade real do banco não corresponde ao teste local.")
    tables = [tuple(row) for row in connection.execute(text("""
        SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
          AND c.relkind IN ('r','p','v','m','S','f')
    """))]
    if ("public", MARKER) not in tables:
        if tables:
            raise BootstrapError("Banco não vazio sem identificação deste teste; nenhuma alteração aplicada.")
        connection.execute(text(f"""
            CREATE TABLE public.{MARKER} (
                id INTEGER PRIMARY KEY CHECK (id=1), signature TEXT NOT NULL,
                instance VARCHAR(48) NOT NULL, stage VARCHAR(20) NOT NULL,
                owner_user_id INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        connection.execute(text(f"INSERT INTO public.{MARKER} (id,signature,instance,stage) VALUES (1,:signature,:instance,'claimed')"),
                           {"signature": SIGNATURE, "instance": config.instance})
        connection.commit()
    rows = connection.execute(text(f"SELECT * FROM public.{MARKER}")).mappings().all()
    if (len(rows) != 1 or rows[0]["id"] != 1 or rows[0]["signature"] != SIGNATURE
            or rows[0]["instance"] != config.instance or rows[0]["stage"] not in {"claimed", "owner", "ready"}):
        raise BootstrapError("Este banco pertence a outra instalação ou possui identificação inválida.")
    return dict(rows[0])


def create_owner(connection, config: LocalConfig) -> None:
    from argon2 import PasswordHasher
    from app.auth.access import AVAILABLE_MODULES

    if connection.scalar(text("SELECT count(*) FROM public.users")):
        raise BootstrapError("Usuário já existente antes da etapa de criação; nenhum acesso foi sobrescrito.")
    owner_id = connection.scalar(text("""
        INSERT INTO public.users (name,email,username,password_hash,role,modules,is_active)
        VALUES (:name,:email,:username,:password,'gestao',CAST(:modules AS json),true) RETURNING id
    """), {
        "name": "Gestor do Teste Local", "email": "teste-v48@example.invalid", "username": USERNAME,
        "password": PasswordHasher().hash(config.password), "modules": json.dumps(list(AVAILABLE_MODULES)),
    })
    connection.execute(text(f"UPDATE public.{MARKER} SET stage='owner', owner_user_id=:id WHERE id=1"), {"id": owner_id})
    connection.commit()


def bootstrap(workdir: Path | None = None) -> None:
    config = local_config()
    workdir = Path.cwd() if workdir is None else workdir
    revisions = migration_plan(workdir)
    engine = open_engine(config)
    try:
        with engine.connect() as connection:
            if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK}):
                raise BootstrapError("Outra inicialização deste banco já está em andamento.")
            try:
                marker = claim_database(connection, config)
                revision = current_revision(connection)
                if revision is not None and revision not in revisions:
                    raise BootstrapError("O banco possui uma revisão incompatível com este pacote.")
                if marker["stage"] == "claimed":
                    if revision is not None and revisions.index(revision) > revisions.index(BASELINE):
                        raise BootstrapError("A etapa inicial do banco não corresponde à identificação local.")
                    connection.commit()
                    upgrade(BASELINE, workdir)
                    if current_revision(connection) != BASELINE:
                        raise BootstrapError("A etapa inicial do esquema não foi confirmada.")
                    create_owner(connection, config)
                    marker = dict(connection.execute(text(f"SELECT * FROM public.{MARKER} WHERE id=1")).mappings().one())
                if marker["owner_user_id"] is None or not connection.scalar(
                    text("SELECT id FROM public.users WHERE id=:id"), {"id": marker["owner_user_id"]},
                ):
                    raise BootstrapError("O usuário proprietário do teste não foi encontrado; nenhum acesso foi recriado.")
                if marker["stage"] == "owner":
                    revision = current_revision(connection)
                    if revision is None or revisions.index(revision) < revisions.index(BASELINE):
                        raise BootstrapError("A etapa do esquema diverge do proprietário local.")
                    connection.commit()
                    upgrade(TARGET, workdir)
                    if current_revision(connection) != TARGET:
                        raise BootstrapError("A revisão final do esquema não foi confirmada.")
                    for code, name in (
                        ("universo_eletronica", "Universo Eletrônica"),
                        ("universo_automacao", "Universo Automação"),
                        ("solucoes_eletronica", "Soluções Eletrônica"),
                    ):
                        connection.execute(text("UPDATE public.commercial_company_profiles SET trade_name=:name WHERE company_code=:code"),
                                           {"name": name, "code": code})
                    connection.execute(text(f"UPDATE public.{MARKER} SET stage='ready' WHERE id=1"))
                    connection.commit()
                if marker["stage"] == "ready" and current_revision(connection) in READY_UPGRADES:
                    # Uma instalação local já usada mantém usuário, senha e dados;
                    # somente a migração incremental do pacote é executada.
                    connection.commit()
                    upgrade(TARGET, workdir)
                if current_revision(connection) != TARGET:
                    raise BootstrapError("O banco local não está na revisão esperada; nenhuma regressão será aplicada.")
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK})
                connection.commit()
    finally:
        engine.dispose()


def main() -> int:
    try:
        bootstrap()
    except BootstrapError as error:
        print(f"BOOTSTRAP_TESTE_V48=ERRO\nMOTIVO={error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("BOOTSTRAP_TESTE_V48=ERRO\nMOTIVO=Inicialização interrompida; dados preservados.", file=sys.stderr)
        return 130
    except Exception:
        print("BOOTSTRAP_TESTE_V48=ERRO\nMOTIVO=Não foi possível concluir a inicialização local; configuração e dados foram preservados.", file=sys.stderr)
        return 1
    print(f"BOOTSTRAP_TESTE_V48=OK\nREVISAO={TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
