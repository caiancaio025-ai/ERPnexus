"""Run only inside the isolated test stack, never against the operational DB."""
import os
from pathlib import Path
import secrets
import subprocess
import sys

from argon2 import PasswordHasher
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> int:
    url = os.environ.get("SENTICO_TEST_DATABASE_URL", "")
    if (os.environ.get("SENTICO_ISOLATED_TEST_RUN") != "1"
        or url != os.environ.get("DATABASE_URL")
        or not url or not (make_url(url).database or "").endswith("_test")):
        raise SystemExit("Execute TESTAR_SENTICO.cmd: banco isolado de teste não confirmado.")
    root = Path(__file__).resolve().parents[1]
    engine = create_engine(url)
    with engine.connect() as connection:
        revision_table = connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
    if revision_table is None:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "20261009_01"], cwd=root, check=True)
        # Config Master associates imported defaults with an existing owner. This
        # synthetic account is never installed by INICIAR_SENTICO.cmd.
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (name,email,username,password_hash,role,modules,is_active) VALUES (:name,:email,:username,:password,'gestao','[]',true)"), {
                "name": "Owner teste isolado", "email": "bootstrap-test@example.invalid",
                "username": "test_bootstrap", "password": PasswordHasher().hash(secrets.token_urlsafe(32)),
            })
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, check=True)
    engine.dispose()
    reports = Path(os.environ.get("TEST_REPORT_DIR", "/tmp/sentico-test-results"))
    reports.mkdir(parents=True, exist_ok=True)
    return subprocess.run([
        sys.executable, "-m", "pytest", "tests", str(root.parents[1] / "testes_instalador"),
        "-q", "-ra", f"--junitxml={reports / 'api-e-instalador.xml'}",
    ], cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
