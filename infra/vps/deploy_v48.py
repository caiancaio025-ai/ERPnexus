#!/usr/bin/env python3
"""Small deployment checks; executable as a file or with ``python - COMMAND``.

Only rewrite-tag and maintenance write configuration files. Database probes use
SELECT statements in a read-only transaction. Upload probes only mutate their
own exclusive temporary files. Never include exception text or secrets in CLI
errors: this helper is also run inside the API image through stdin.
"""

from __future__ import annotations

import argparse
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
