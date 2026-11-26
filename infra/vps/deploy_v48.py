#!/usr/bin/env python3
"""Small deployment checks; executable as a file or with ``python - COMMAND``.

Only rewrite-tag and maintenance write configuration files. Database probes use
SELECT statements in a read-only transaction. Upload probes only mutate their
own exclusive temporary files. Never include exception text or secrets in CLI
errors: this helper is also run inside the API image through stdin.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from html.parser import HTMLParser
from urllib import request


class CheckError(Exception):
    """A fixed, safe diagnostic that may be shown to the operator."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error echoes argv, which may contain secrets.
        raise CheckError("Argumentos inválidos para o helper de implantação.")


TAG_PREFIX = re.compile(rb"(?m)^(?:\xef\xbb\xbf)?[ \t]*(?:export[ \t]+)?TAG[ \t]*=[ \t]*")
TAG_BODY = re.compile(rb"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^ \t#\r\n'\"]*)(?P<suffix>[ \t]*(?:#[^\r\n]*)?)\Z")
ASSET_PATH = re.compile(r"/assets/[A-Za-z0-9_.-]+\Z")
MAX_JSON_BYTES = 1024 * 1024


def rewrite_tag(env_path: str | Path, tag: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag):
        raise CheckError("TAG de imagem inválida.")
    target = Path(env_path)
    metadata = target.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise CheckError("O arquivo de ambiente deve ser um arquivo regular, sem link simbólico.")
    fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise CheckError("O arquivo de ambiente deve ser um arquivo regular.")
        original = source.read()
    matches = list(TAG_PREFIX.finditer(original))
    if len(matches) != 1:
        raise CheckError("O arquivo de ambiente deve conter exatamente uma linha TAG=.")
    match = matches[0]
    end = original.find(b"\n", match.end())
    if end < 0:
        end = len(original)
    if original[match.end():end].endswith(b"\r"):
        end -= 1
    body = TAG_BODY.fullmatch(original[match.end():end])
    if body is None:
        raise CheckError("A linha TAG do arquivo de ambiente é inválida.")
    previous = body.group("value")
    replacement = tag.encode("ascii")
    if previous[:1] in {b"'", b'"'}:
        replacement = previous[:1] + replacement + previous[-1:]
    suffix = body.group("suffix")
    if not previous and suffix.startswith(b"#"):
        suffix = b" " + suffix
    updated = original[:match.end()] + replacement + suffix + original[end:]
    temporary: str | None = None
    fd = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".sentico-tag-", dir=target.parent)
        os.fchown(fd, metadata.st_uid, metadata.st_gid)
        os.fchmod(fd, stat.S_IMODE(metadata.st_mode))
        with os.fdopen(fd, "wb") as output:
            fd = None
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        current = target.lstat()
        if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
            metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
        ):
            raise CheckError("O arquivo de ambiente mudou durante a atualização; nenhuma troca foi aplicada.")
        os.replace(temporary, target)
        temporary = None
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _load_json(path: str | Path) -> dict:
    value = json.loads(Path(path).read_bytes())
    if not isinstance(value, dict):
        raise CheckError("O documento JSON deve conter um objeto.")
    return value


def maintenance(snapshot_json: str | Path, output_json: str | Path, token: str) -> None:
    if not re.fullmatch(r"[0-9A-Fa-f]{32,}", token):
        raise CheckError("Token de verificação inválido.")
    source = Path(snapshot_json)
    target = Path(output_json)
    if source.resolve() == target.resolve():
        raise CheckError("O arquivo de manutenção deve ser diferente do snapshot original.")
    configuration = _load_json(source)
    apps = configuration.get("apps")
    http = apps.get("http") if isinstance(apps, dict) else None
    servers = http.get("servers") if isinstance(http, dict) else None
    if not isinstance(servers, dict) or len(servers) != 1:
        raise CheckError("O snapshot deve conter exatamente um servidor HTTP.")
    server = next(iter(servers.values()))
    if not isinstance(server, dict) or server.get("listen") != [":8080"]:
        raise CheckError("O único servidor HTTP deve escutar exclusivamente em :8080.")
    routes = server.get("routes")
    if not isinstance(routes, list) or not routes or any(not isinstance(route, dict) for route in routes):
        raise CheckError("O snapshot não contém rotas HTTP válidas para preservar.")
    server["routes"] = [
        {
            "match": [{"header": {"X-Sentico-Deploy-Check": [token]}}],
            "handle": [{"handler": "subroute", "routes": routes}],
            "terminal": True,
        },
        {
            "handle": [{
                "handler": "static_response", "status_code": 503,
                "headers": {
                    "Retry-After": ["60"],
                    "Content-Type": ["text/plain; charset=utf-8"],
                    "Cache-Control": ["no-store"],
                },
                "body": "SENTICO em manutenção. Tente novamente em instantes.\n",
            }],
            "terminal": True,
        },
    ]
    # The snapshot is never modified. Atomic output avoids loading partial JSON.
    fd, temporary = tempfile.mkstemp(prefix=".sentico-maintenance-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(configuration, output, ensure_ascii=False, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def json_field(path: str | Path, dotted_key: str, expected: str) -> None:
    keys = dotted_key.split(".")
    if not keys or any(not key for key in keys):
        raise CheckError("Caminho de campo JSON inválido.")
    value = _load_json(path)
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise CheckError("Campo JSON ausente ou valor inesperado.")
        value = value[key]
    if not isinstance(value, str) or value != expected:
        raise CheckError("Campo JSON ausente ou valor inesperado.")


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paths: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        for name, value in attrs:
            if name not in {"src", "href"} or value is None or not value.startswith("/assets/"):
                continue
            if not ASSET_PATH.fullmatch(value) or value.removeprefix("/assets/") in {".", ".."}:
                raise CheckError("O HTML contém um caminho de asset inválido.")
            if value not in self.paths:
                self.paths.append(value)

    handle_startendtag = handle_starttag


def assets(index_html: str | Path) -> list[str]:
    parser = AssetParser()
    parser.feed(Path(index_html).read_text(encoding="utf-8"))
    parser.close()
    if not parser.paths:
        raise CheckError("O HTML não contém assets locais válidos.")
    return parser.paths


def _load_settings():
    from app.core.config import settings
    return settings


def _check_storage_access(root: Path) -> None:
    if not root.is_dir() or root.resolve() != root:
        raise CheckError("O volume de uploads deve existir no caminho esperado, sem redirecionamento.")

    def walk_error(error):
        raise CheckError("Não foi possível percorrer o volume de uploads.")

    def validate_path(path: Path, *, directory: bool) -> None:
        if path.is_symlink() and not path.resolve(strict=True).is_relative_to(root):
            raise CheckError("O volume de uploads contém um link para fora do armazenamento.")
        access = os.R_OK | os.W_OK | os.X_OK if directory else os.R_OK
        if not os.access(path, access):
            raise CheckError("Há arquivos ilegíveis ou diretórios sem permissão no volume de uploads.")
        if not directory:
            if not path.is_file():
                raise CheckError("Há um arquivo especial inválido no volume de uploads.")
            with path.open("rb") as stream:
                stream.read(1)

    for directory, subdirectories, files in os.walk(root, onerror=walk_error, followlinks=False):
        validate_path(Path(directory), directory=True)
        for name in subdirectories:
            validate_path(Path(directory) / name, directory=True)
        for name in files:
            validate_path(Path(directory) / name, directory=False)


def _storage_roundtrip(root: Path) -> None:
    created: list[Path] = []
    descriptors: set[int] = set()
    cleanup_failed = False
    try:
        source_fd, source_name = tempfile.mkstemp(prefix=".sentico-v48-probe-", dir=root)
        descriptors.add(source_fd)
        created.append(Path(source_name))
        target_fd, target_name = tempfile.mkstemp(prefix=".sentico-v48-probe-", dir=root)
        descriptors.add(target_fd)
        created.append(Path(target_name))
        os.close(target_fd)
        descriptors.remove(target_fd)
        payload = os.urandom(64)
        with os.fdopen(source_fd, "wb") as stream:
            descriptors.remove(source_fd)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(source_name, target_name)
        if Path(target_name).read_bytes() != payload:
            raise CheckError("A leitura do arquivo temporário de uploads não confirmou a escrita.")
    finally:
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except OSError:
                cleanup_failed = True
        for path in created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True
        if cleanup_failed:
            raise CheckError("Não foi possível limpar os arquivos temporários da verificação.")


def probe_uploads() -> None:
    configured = str(_load_settings().storage_root)
    if configured.rstrip("/") != "/app/storage":
        raise CheckError("STORAGE_ROOT deve apontar para /app/storage.")
    root = Path("/app/storage")
    _check_storage_access(root)
    _storage_roundtrip(root)


def probe_db(expected_ip: str, expected_db: str, expected_user: str, revision: str) -> None:
    try:
        address = ipaddress.ip_address(expected_ip)
    except ValueError:
        raise CheckError("Endereço esperado do banco inválido.") from None
    if not expected_db or not expected_user or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", revision):
        raise CheckError("Identidade ou revisão esperada do banco inválida.")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool

    url = make_url(_load_settings().database_url)
    if url.get_backend_name() != "postgresql":
        raise CheckError("A verificação exige um banco PostgreSQL.")
    engine = create_engine(
        url, poolclass=NullPool,
        connect_args={
            "connect_timeout": 10,
            "options": "-c default_transaction_read_only=on -c statement_timeout=10000",
        },
    )
    try:
        with engine.connect() as connection:
            identity = connection.execute(text(
                "SELECT host(inet_server_addr()) AS server_addr, "
                "current_database() AS database_name, current_user AS user_name, "
                "current_setting('transaction_read_only') AS read_only"
            )).mappings().one()
            if identity["read_only"] != "on":
                raise CheckError("A conexão de verificação não está em modo somente leitura.")
            try:
                actual_address = ipaddress.ip_address(identity["server_addr"])
            except (TypeError, ValueError):
                raise CheckError("Não foi possível confirmar o endereço do banco.") from None
            if (actual_address != address or identity["database_name"] != expected_db
                    or identity["user_name"] != expected_user):
                raise CheckError("A identidade do banco não corresponde ao ambiente esperado.")
            revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            if revisions != [revision]:
                raise CheckError("A revisão única do banco não corresponde à revisão esperada.")
    finally:
        engine.dispose()


def _validate_receipt_schema(connection) -> None:
    """Validate the additive unit-receipt schema, not only the Alembic marker."""
    from sqlalchemy import text

    column = connection.execute(text(
        "SELECT a.attnotnull AS required, t.typname AS type, "
        "pg_get_expr(d.adbin, d.adrelid) AS default_value "
        "FROM pg_attribute a JOIN pg_type t ON t.oid = a.atttypid "
        "LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
        "WHERE a.attrelid = 'public.inventory_movements'::regclass "
        "AND a.attname = 'receipt_unit_index' AND a.attnum > 0 AND NOT a.attisdropped"
    )).mappings().one_or_none()
    if (column is None or column["required"] is not True or column["type"] != "int4"
            or column["default_value"] != "1"):
        raise CheckError("A coluna de identificação das unidades recebidas não está correta.")
    constraints = connection.execute(text(
        "SELECT c.contype AS kind, pg_get_constraintdef(c.oid) AS definition, "
        "ARRAY(SELECT a.attname::text FROM unnest(c.conkey) WITH ORDINALITY k(attnum, position) "
        "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum "
        "ORDER BY k.position) AS columns FROM pg_constraint c "
        "WHERE c.conrelid = 'public.inventory_movements'::regclass"
    )).mappings().all()
    unique_keys = {tuple(row["columns"]) for row in constraints if row["kind"] == "u"}
    expected_keys = {("purchase_order_id", "receipt_unit_index"), ("material_request_id", "receipt_unit_index")}
    positive_index = any(
        row["kind"] == "c" and re.sub(r"[\s()]", "", row["definition"]).lower()
        == "checkreceipt_unit_index>0"
        for row in constraints
    )
    if (not expected_keys.issubset(unique_keys) or not positive_index
            or ("purchase_order_id",) in unique_keys or ("material_request_id",) in unique_keys):
        raise CheckError("As restrições de recebimento individual não correspondem à migração esperada.")


def _validate_grouped_quote_schema(connection) -> None:
    """The revision marker alone must not accept a partial document migration."""
    from sqlalchemy import bindparam, text

    required_columns = {
        ("laboratory_quote_groups", "code"): ("varchar", True),
        ("laboratory_quote_groups", "customer_id"): ("int4", True),
        ("laboratory_quote_groups", "creation_fingerprint"): ("varchar", True),
        ("laboratory_grouped_quotes", "version"): ("int4", True),
        ("laboratory_grouped_quotes", "content"): ("json", True),
        ("laboratory_grouped_quotes", "document_snapshot"): ("json", False),
        ("laboratory_grouped_quotes", "pdf_content"): ("bytea", False),
        ("laboratory_grouped_quotes", "pdf_sha256"): ("varchar", False),
        ("laboratory_grouped_quote_work_orders", "work_order_id"): ("int4", True),
        ("laboratory_grouped_quote_work_orders", "total"): ("numeric", True),
        ("laboratory_grouped_quote_items", "work_order_id"): ("int4", True),
        ("laboratory_grouped_quote_items", "quantity"): ("numeric", True),
    }
    tables = tuple(sorted({table for table, _ in required_columns}))
    rows = connection.execute(text(
        "SELECT table_name, column_name, udt_name, is_nullable "
        "FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name IN :tables"
    ).bindparams(bindparam("tables", expanding=True)), {"tables": tables}).mappings().all()
    actual = {
        (row["table_name"], row["column_name"]): (row["udt_name"], row["is_nullable"] == "NO")
        for row in rows
    }
    if any(actual.get(column) != expected for column, expected in required_columns.items()):
        raise CheckError("As tabelas de orçamentos conjuntos estão incompletas ou incompatíveis.")
    required_constraints = {
        ("laboratory_quote_groups", "uq_lab_quote_group_creation_key", "u"),
        ("laboratory_grouped_quotes", "uq_lab_grouped_quote_revision", "u"),
        ("laboratory_grouped_quotes", "ck_lab_grouped_quote_version", "c"),
        ("laboratory_grouped_quotes", "ck_lab_grouped_quote_status", "c"),
        ("laboratory_grouped_quotes", "ck_lab_grouped_quote_totals", "c"),
        ("laboratory_grouped_quote_work_orders", "uq_lab_grouped_quote_os", "u"),
        ("laboratory_grouped_quote_work_orders", "uq_lab_grouped_quote_os_position", "u"),
        ("laboratory_grouped_quote_work_orders", "ck_lab_grouped_quote_os_totals", "c"),
        ("laboratory_grouped_quote_items", "fk_lab_grouped_quote_item_os", "f"),
        ("laboratory_grouped_quote_items", "uq_lab_grouped_quote_item_position", "u"),
        ("laboratory_grouped_quote_items", "ck_lab_grouped_quote_item_values", "c"),
    }
    rows = connection.execute(text(
        "SELECT t.relname AS table_name, c.conname, c.contype FROM pg_constraint c "
        "JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
        "WHERE n.nspname='public' AND t.relname IN :tables AND c.convalidated"
    ).bindparams(bindparam("tables", expanding=True)), {"tables": tables}).mappings().all()
    actual_constraints = {(row["table_name"], row["conname"], row["contype"]) for row in rows}
    if not required_constraints.issubset(actual_constraints):
        raise CheckError("As restrições dos orçamentos conjuntos não correspondem à migração esperada.")


def inventory_snapshot(revision: str) -> dict:
    """Read-only fingerprints prove that the receipt migration kept every row.

    The old revision has no unit index. Its expected value is represented as 1
    before hashing, so a legacy snapshot equals the upgraded snapshot only when
    all existing fields and the new default value were preserved.
    """
    if revision not in {"20261123_02", "20261126_01", "20261126_02"}:
        raise CheckError("Revisão não suportada para a conferência do estoque.")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool

    url = make_url(_load_settings().database_url)
    if url.get_backend_name() != "postgresql":
        raise CheckError("A conferência do estoque exige PostgreSQL.")
    engine = create_engine(
        url, poolclass=NullPool, isolation_level="REPEATABLE READ",
        connect_args={
            "connect_timeout": 10,
            "options": "-c default_transaction_read_only=on -c statement_timeout=120000 -c timezone=UTC",
        },
    )
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT current_setting('transaction_read_only')")).scalar_one() != "on":
                raise CheckError("A conferência do estoque não está em modo somente leitura.")
            if connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() != [revision]:
                raise CheckError("A revisão do estoque mudou durante a conferência.")
            if revision in {"20261126_01", "20261126_02"}:
                _validate_receipt_schema(connection)
            if revision == "20261126_02":
                _validate_grouped_quote_schema(connection)
            snapshot = {}
            for table in ("inventory_items", "inventory_movements"):
                projection = "to_jsonb(t)"
                if table == "inventory_movements" and revision == "20261123_02":
                    projection += " || jsonb_build_object('receipt_unit_index', 1)"
                digest = hashlib.sha256()
                rows = 0
                statement = text(f"SELECT ({projection})::text FROM public.{table} t ORDER BY id")
                result = connection.execution_options(stream_results=True).execute(statement)
                for row in result:
                    digest.update(row[0].encode("utf-8"))
                    digest.update(b"\n")
                    rows += 1
                totals = connection.execute(text(
                    f"SELECT count(*) AS rows, coalesce(sum(quantity), 0) AS quantity, "
                    f"coalesce(sum(quantity * unit_cost), 0) AS value FROM public.{table}"
                )).mappings().one()
                if rows != totals["rows"]:
                    raise CheckError("A contagem do estoque mudou durante a conferência.")
                snapshot[table] = {
                    "rows": rows, "quantity": str(totals["quantity"]),
                    "value": str(totals["value"]), "sha256": digest.hexdigest(),
                }
            return snapshot
    finally:
        engine.dispose()


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_json(opener, path: str, host: str) -> dict:
    query = request.Request(
        "http://127.0.0.1:8000" + path,
        headers={"Host": host, "Accept": "application/json"},
    )
    with opener.open(query, timeout=10) as response:
        if response.getcode() != 200:
            raise CheckError("A API local não confirmou a verificação HTTP.")
        content = response.read(MAX_JSON_BYTES + 1)
    if len(content) > MAX_JSON_BYTES:
        raise CheckError("A resposta HTTP da API local é inválida.")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise CheckError("A resposta HTTP da API local é inválida.")
    return value


def probe_http(expected_version: str | None = None) -> None:
    host = os.environ.get("SENTICO_HEALTH_HOST", "localhost")
    if not host or any(character in host for character in "\r\n"):
        raise CheckError("Host de verificação HTTP inválido.")
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    if _http_json(opener, "/health/ready", host).get("status") != "ok":
        raise CheckError("A API local ainda não está pronta.")
    if expected_version is not None:
        version = _http_json(opener, "/health/version", host).get("version")
        if not isinstance(version, str) or version != expected_version:
            raise CheckError("A versão da API local não corresponde à versão esperada.")


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(prog="deploy_v48.py")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=SafeArgumentParser)
    rewrite = commands.add_parser("rewrite-tag")
    rewrite.add_argument("env_path")
    rewrite.add_argument("tag")
    maintenance_parser = commands.add_parser("maintenance")
    maintenance_parser.add_argument("snapshot_json")
    maintenance_parser.add_argument("output_json")
    maintenance_parser.add_argument("token")
    field = commands.add_parser("json-field")
    field.add_argument("path")
    field.add_argument("key")
    field.add_argument("expected")
    asset = commands.add_parser("assets")
    asset.add_argument("index_html")
    commands.add_parser("probe-uploads")
    database = commands.add_parser("probe-db")
    database.add_argument("expected_ip")
    database.add_argument("expected_db")
    database.add_argument("expected_user")
    database.add_argument("revision")
    inventory = commands.add_parser("inventory-snapshot")
    inventory.add_argument("revision")
    http = commands.add_parser("probe-http")
    http.add_argument("expected_version", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "rewrite-tag":
            rewrite_tag(args.env_path, args.tag)
        elif args.command == "maintenance":
            maintenance(args.snapshot_json, args.output_json, args.token)
        elif args.command == "json-field":
            json_field(args.path, args.key, args.expected)
        elif args.command == "assets":
            print("\n".join(assets(args.index_html)))
        elif args.command == "probe-uploads":
            probe_uploads()
        elif args.command == "probe-db":
            probe_db(args.expected_ip, args.expected_db, args.expected_user, args.revision)
        elif args.command == "inventory-snapshot":
            print(json.dumps(inventory_snapshot(args.revision), sort_keys=True))
        elif args.command == "probe-http":
            probe_http(args.expected_version)
        return 0
    except CheckError as error:
        print(f"ERRO: {error}", file=sys.stderr)
    except Exception:
        # Driver, parser, path and network errors can embed credentials or tokens.
        print("ERRO: Não foi possível concluir a verificação solicitada.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
