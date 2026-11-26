"""Unit tests for the deployment helper; no Docker or application fixture."""

from contextlib import contextmanager
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location("deploy_v48_helper", Path(__file__).parents[1] / "deploy_v48.py")
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
TOKEN = "a9" * 32


@pytest.mark.parametrize(("before", "after"), [
    (b"DB_PASSWORD=opaque\nTAG=old\nEND=yes\n", b"DB_PASSWORD=opaque\nTAG=v48-next\nEND=yes\n"),
    (b"\xef\xbb\xbfTAG = old\r\nX=\xff\r\n", b"\xef\xbb\xbfTAG = v48-next\r\nX=\xff\r\n"),
    (b"\texport TAG \t= 'old'  # keep this\r\nX=42", b"\texport TAG \t= 'v48-next'  # keep this\r\nX=42"),
    (b'TAG="old"\n', b'TAG="v48-next"\n'),
    (b"# TAG=commented\nTAG=\nTAG_OTHER=unchanged", b"# TAG=commented\nTAG=v48-next\nTAG_OTHER=unchanged"),
    (b"TAG=old", b"TAG=v48-next"),
    (b"TAG= # preserve empty-value comment\n", b"TAG= v48-next # preserve empty-value comment\n"),
])
def test_rewrite_tag_preserves_all_other_bytes_and_metadata(tmp_path, before, after):
    path = tmp_path / ".env"
    path.write_bytes(before)
    path.chmod(0o640)
    original = path.stat()
    helper.rewrite_tag(path, "v48-next")
    result = path.stat()
    assert path.read_bytes() == after
    assert stat.S_IMODE(result.st_mode) == stat.S_IMODE(original.st_mode)
    assert (result.st_uid, result.st_gid) == (original.st_uid, original.st_gid)
    assert result.st_ino != original.st_ino
    assert sorted(p.name for p in tmp_path.iterdir()) == [".env"]


@pytest.mark.parametrize("content", [
    b"OTHER=old\n", b"TAG=one\nTAG=two\n", b"export TAG=one\n TAG =two",
    b'TAG="unclosed\n', b"TAG=two words\n",
])
def test_rewrite_tag_rejects_ambiguous_or_invalid_assignment_without_writing(tmp_path, content):
    path = tmp_path / ".env"
    path.write_bytes(content)
    with pytest.raises(helper.CheckError):
        helper.rewrite_tag(path, "v48")
    assert path.read_bytes() == content


@pytest.mark.parametrize("tag", ["", "-bad", "a" * 129, "good\nPASSWORD=changed", "bad:tag", "v48/path", "v48 #comment"])
def test_rewrite_tag_rejects_invalid_new_tag(tmp_path, tag):
    path = tmp_path / ".env"
    path.write_bytes(b"TAG=old\n")
    with pytest.raises(helper.CheckError):
        helper.rewrite_tag(path, tag)
    assert path.read_bytes() == b"TAG=old\n"


def test_rewrite_tag_rejects_symlink(tmp_path):
    original = tmp_path / "real.env"
    original.write_bytes(b"TAG=old\n")
    path = tmp_path / ".env"
    path.symlink_to(original)
    with pytest.raises(helper.CheckError):
        helper.rewrite_tag(path, "new")
    assert path.is_symlink() and original.read_bytes() == b"TAG=old\n"


def test_failed_atomic_replace_keeps_original_and_removes_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_bytes(b"TAG=old\nPASSWORD=opaque\n")
    inode = path.stat().st_ino

    def fail_replace(*args):
        raise OSError("Sensitive path or connection detail")

    monkeypatch.setattr(helper.os, "replace", fail_replace)
    with pytest.raises(OSError):
        helper.rewrite_tag(path, "new")
    assert path.stat().st_ino == inode
    assert path.read_bytes() == b"TAG=old\nPASSWORD=opaque\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == [".env"]


def test_concurrent_environment_edit_is_not_silently_overwritten(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_bytes(b"TAG=old\n")
    actual = helper.tempfile.mkstemp

    def create(**kwargs):
        result = actual(**kwargs)
        path.write_bytes(b"TAG=another-writer\n")
        return result

    monkeypatch.setattr(helper.tempfile, "mkstemp", create)
    with pytest.raises(helper.CheckError, match="mudou"):
        helper.rewrite_tag(path, "new")
    assert path.read_bytes() == b"TAG=another-writer\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == [".env"]


def caddy_config():
    return {
        "admin": {"listen": "localhost:2019"}, "logging": {"logs": {"default": {"level": "INFO"}}},
        "apps": {
            "tls": {"automation": {"policies": []}},
            "http": {"http_port": 80, "servers": {"srv0": {
                "listen": [":8080"], "protocols": ["h1", "h2"], "idle_timeout": 60000000000,
                "routes": [{"handle": [{"handler": "reverse_proxy", "upstreams": [{"dial": "api:8000"}]}], "terminal": True}],
                "automatic_https": {"disable": True},
            }}},
        },
    }


def test_maintenance_preserves_snapshot_globals_server_and_original_routes(tmp_path):
    original = caddy_config()
    source = tmp_path / "live.json"
    output = tmp_path / "maintenance.json"
    source.write_text(json.dumps(original, indent=2))
    source_bytes = source.read_bytes()
    helper.maintenance(source, output, TOKEN)
    changed = json.loads(output.read_bytes())
    assert source.read_bytes() == source_bytes
    expected = json.loads(source_bytes)
    routes = changed["apps"]["http"]["servers"]["srv0"]["routes"]
    assert len(routes) == 2 and all(row["terminal"] is True for row in routes)
    assert routes[0]["match"] == [{"header": {"X-Sentico-Deploy-Check": [TOKEN]}}]
    assert routes[0]["handle"] == [{"handler": "subroute", "routes": original["apps"]["http"]["servers"]["srv0"]["routes"]}]
    response = routes[1]["handle"][0]
    assert response["handler"] == "static_response" and response["status_code"] == 503
    assert response["headers"]["Retry-After"] == ["60"]
    assert response["headers"]["Content-Type"] == ["text/plain; charset=utf-8"]
    changed["apps"]["http"]["servers"]["srv0"]["routes"] = expected["apps"]["http"]["servers"]["srv0"]["routes"]
    assert changed == expected
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


@pytest.mark.parametrize("kind", ["zero", "extra", "wrong-port", "extra-listener", "no-routes", "bad-routes"])
def test_maintenance_rejects_unexpected_server_topology(tmp_path, kind):
    config = caddy_config()
    servers = config["apps"]["http"]["servers"]
    if kind == "zero":
        servers.clear()
    elif kind == "extra":
        servers["srv1"] = {"listen": [":9090"]}
    elif kind == "wrong-port":
        servers["srv0"]["listen"] = [":80"]
    elif kind == "extra-listener":
        servers["srv0"]["listen"] = [":8080", ":9090"]
    elif kind == "no-routes":
        servers["srv0"].pop("routes")
    else:
        servers["srv0"]["routes"] = ["invalid"]
    source = tmp_path / "live.json"
    output = tmp_path / "maintenance.json"
    source.write_text(json.dumps(config))
    with pytest.raises(helper.CheckError):
        helper.maintenance(source, output, TOKEN)
    assert not output.exists()


@pytest.mark.parametrize("token", ["a" * 31, "g" * 64, "a" * 32 + "\n", "token/secret"])
def test_maintenance_rejects_invalid_token_before_reading_files(tmp_path, token):
    with pytest.raises(helper.CheckError, match="Token"):
        helper.maintenance(tmp_path / "missing.json", tmp_path / "out.json", token)


def test_maintenance_cannot_overwrite_original_snapshot(tmp_path):
    path = tmp_path / "live.json"
    path.write_text(json.dumps(caddy_config()))
    original = path.read_bytes()
    with pytest.raises(helper.CheckError):
        helper.maintenance(path, path, TOKEN)
    assert path.read_bytes() == original


def test_json_field_checks_exact_nested_string(tmp_path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"health": {"status": "ok"}, "version": "48", "number": 48}))
    helper.json_field(path, "health.status", "ok")
    helper.json_field(path, "version", "48")
    for dotted, expected in [("number", "48"), ("health.status", "OK"), ("missing.key", "ok"), ("health..status", "ok"), ("version.foo", "48")]:
        with pytest.raises(helper.CheckError):
            helper.json_field(path, dotted, expected)


def test_assets_collects_src_href_uniquely_and_preserves_order(tmp_path, capsys):
    html = tmp_path / "index.html"
    html.write_text('''<!doctype html><link href="/assets/main-abc.css"/><script type="module" src="/assets/index_A9.js"></script>
        <link href="/assets/main-abc.css"><img src="/branding/logo.png"><script src="https://example.invalid/ignored.js"></script>
        <!-- <script src="/assets/comment.js"></script> -->''')
    assert helper.main(["assets", str(html)]) == 0
    assert capsys.readouterr().out == "/assets/main-abc.css\n/assets/index_A9.js\n"


@pytest.mark.parametrize("path", ["/assets/", "/assets/.", "/assets/..", "/assets/../secret", "/assets/x.js?token=secret", "/assets/nested/x.js", "/assets/x%2F.js", "/assets/x.js#frag"])
def test_assets_rejects_malformed_local_paths(tmp_path, path):
    html = tmp_path / "index.html"
    html.write_text(f'<script src="{path}"></script>')
    with pytest.raises(helper.CheckError):
        helper.assets(html)


def test_assets_requires_nonempty_result(tmp_path):
    html = tmp_path / "index.html"
    html.write_text('<link href="/index.css">')
    with pytest.raises(helper.CheckError):
        helper.assets(html)


def test_storage_walk_and_roundtrip_preserve_existing_files(tmp_path):
    folder = tmp_path / "laboratory" / "OS-1"
    folder.mkdir(parents=True)
    document = folder / "original.pdf"
    document.write_bytes(b"Existing customer file")
    helper._check_storage_access(tmp_path)
    helper._storage_roundtrip(tmp_path)
    assert document.read_bytes() == b"Existing customer file"
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == [
        "laboratory", "laboratory/OS-1", "laboratory/OS-1/original.pdf",
    ]


@pytest.mark.parametrize("denied", ["directory", "file"])
def test_storage_walk_detects_unreadable_file_or_unwritable_directory(tmp_path, monkeypatch, denied):
    folder = tmp_path / "sub"
    folder.mkdir()
    file = folder / "data.bin"
    file.write_bytes(b"content")
    real_access = os.access
    target = folder if denied == "directory" else file
    calls = []

    def check(path, mode):
        calls.append((Path(path), mode))
        return False if Path(path) == target else real_access(path, mode)

    monkeypatch.setattr(helper.os, "access", check)
    with pytest.raises(helper.CheckError):
        helper._check_storage_access(tmp_path)
    requested = next(mode for path, mode in calls if path == target)
    assert requested & os.R_OK
    if denied == "directory":
        assert requested & os.W_OK and requested & os.X_OK


def test_storage_roundtrip_cleans_both_exclusive_files_when_rename_fails(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("private filesystem details")
    monkeypatch.setattr(helper.os, "replace", fail)
    with pytest.raises(OSError):
        helper._storage_roundtrip(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_storage_roundtrip_cleans_first_file_when_second_creation_fails(tmp_path, monkeypatch):
    actual = helper.tempfile.mkstemp
    calls = 0

    def create(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("no space")
        return actual(**kwargs)

    monkeypatch.setattr(helper.tempfile, "mkstemp", create)
    with pytest.raises(OSError):
        helper._storage_roundtrip(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_probe_uploads_requires_expected_configuration_without_app_import(monkeypatch):
    monkeypatch.setattr(helper, "_load_settings", lambda: SimpleNamespace(storage_root="/wrong/storage"))
    with pytest.raises(helper.CheckError):
        helper.probe_uploads()
    checked = []
    monkeypatch.setattr(helper, "_load_settings", lambda: SimpleNamespace(storage_root="/app/storage"))
    monkeypatch.setattr(helper, "_check_storage_access", lambda root: checked.append(("access", root)))
    monkeypatch.setattr(helper, "_storage_roundtrip", lambda root: checked.append(("roundtrip", root)))
    helper.probe_uploads()
    assert checked == [("access", Path("/app/storage")), ("roundtrip", Path("/app/storage"))]


@pytest.fixture
def fake_database(monkeypatch):
    import sqlalchemy

    state = SimpleNamespace(
        identity={"server_addr": "172.20.0.7", "database_name": "sentico", "user_name": "sentico_green", "read_only": "on"},
        revisions=["20261123_02"], queries=[], disposed=False, settings=None, error=None,
    )

    class Result:
        def __init__(self, value): self.value = value
        def mappings(self): return self
        def scalars(self): return self
        def one(self): return self.value
        def all(self): return self.value

    class Engine:
        @contextmanager
        def connect(self):
            if state.error is not None:
                raise state.error
            yield self

        def execute(self, statement):
            sql = str(statement)
            state.queries.append(sql)
            return Result(state.revisions if "alembic_version" in sql else state.identity)

        def dispose(self): state.disposed = True

    def engine(url, **kwargs):
        state.settings = kwargs
        return Engine()

    monkeypatch.setattr(sqlalchemy, "create_engine", engine)
    monkeypatch.setattr(helper, "_load_settings", lambda: SimpleNamespace(
        database_url="postgresql+psycopg://sentico_green:do-not-print@db/sentico",
    ))
    return state


def test_database_probe_checks_identity_revision_and_read_only_without_writes(fake_database):
    helper.probe_db("172.20.0.7", "sentico", "sentico_green", "20261123_02")
    state = fake_database
    assert state.disposed
    assert state.settings["connect_args"]["connect_timeout"] == 10
    assert "default_transaction_read_only=on" in state.settings["connect_args"]["options"]
    assert state.settings["poolclass"].__name__ == "NullPool"
    assert len(state.queries) == 2 and all(query.startswith("SELECT ") for query in state.queries)


@pytest.mark.parametrize(("field", "value"), [
    ("server_addr", "172.20.0.8"), ("server_addr", None), ("database_name", "wrong_db"),
    ("user_name", "wrong_role"), ("read_only", "off"),
])
def test_database_probe_rejects_wrong_identity_or_writable_transaction(fake_database, field, value):
    fake_database.identity[field] = value
    with pytest.raises(helper.CheckError):
        helper.probe_db("172.20.0.7", "sentico", "sentico_green", "20261123_02")
    assert fake_database.disposed
    assert len(fake_database.queries) == 1


@pytest.mark.parametrize("revisions", [[], ["wrong"], ["20261123_02", "other"]])
def test_database_probe_requires_one_matching_alembic_revision(fake_database, revisions):
    fake_database.revisions = revisions
    with pytest.raises(helper.CheckError):
        helper.probe_db("172.20.0.7", "sentico", "sentico_green", "20261123_02")
    assert fake_database.disposed


def test_database_probe_sanitizes_credentials_on_driver_failure(fake_database, capsys):
    fake_database.error = RuntimeError("postgresql://username:top-secret@private-host/sentico")
    assert helper.main(["probe-db", "172.20.0.7", "sentico", "sentico_green", "20261123_02"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "top-secret" not in output.err and "private-host" not in output.err and "postgresql" not in output.err
    assert fake_database.disposed


@pytest.fixture
def fake_http(monkeypatch):
    state = SimpleNamespace(responses=[{"status": "ok"}, {"version": "48"}], calls=[], handlers=None)

    class Response:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def getcode(self): return 200
        def read(self, limit): return json.dumps(self.body).encode()[:limit]

    class Opener:
        def open(self, req, timeout):
            state.calls.append((req, timeout))
            body = state.responses.pop(0)
            if isinstance(body, Exception):
                raise body
            return Response(body)

    def build(*handlers):
        state.handlers = handlers
        return Opener()

    monkeypatch.setattr(helper.request, "build_opener", build)
    monkeypatch.delenv("SENTICO_HEALTH_HOST", raising=False)
    return state


def test_http_probe_without_version_only_checks_ready_and_uses_localhost(fake_http):
    helper.probe_http()
    assert len(fake_http.calls) == 1
    req, timeout = fake_http.calls[0]
    assert req.full_url == "http://127.0.0.1:8000/health/ready" and timeout == 10
    assert req.get_header("Host") == "localhost"
    assert fake_http.handlers[0].proxies == {}
    assert isinstance(fake_http.handlers[1], helper.NoRedirect)


def test_http_probe_checks_version_and_explicit_health_host(fake_http, monkeypatch):
    monkeypatch.setenv("SENTICO_HEALTH_HOST", "erp.universoeletronica.com")
    helper.probe_http("48")
    assert [req.full_url for req, _ in fake_http.calls] == [
        "http://127.0.0.1:8000/health/ready", "http://127.0.0.1:8000/health/version",
    ]
    assert all(req.get_header("Host") == "erp.universoeletronica.com" and timeout == 10 for req, timeout in fake_http.calls)


@pytest.mark.parametrize("responses", [
    [{"status": "error"}], [{"status": "ok"}, {"version": "47"}],
    [{"status": "ok"}, {"version": 48}], [["ok"]],
])
def test_http_probe_rejects_unhealthy_or_wrong_version(fake_http, responses):
    fake_http.responses = responses
    with pytest.raises(helper.CheckError):
        helper.probe_http("48")


def test_http_probe_sanitizes_network_exception(fake_http, capsys):
    fake_http.responses = [OSError("http://user:secret@private-host/")]
    assert helper.main(["probe-http", "48"]) == 1
    output = capsys.readouterr()
    assert not output.out and "secret" not in output.err and "private-host" not in output.err


def test_invalid_cli_arguments_are_sanitized(capsys):
    assert helper.main(["probe-db", "postgresql://user:secret@private-host/"]) == 1
    output = capsys.readouterr()
    assert not output.out and "secret" not in output.err and "private-host" not in output.err


def test_bad_json_is_reported_without_echoing_content_or_filename(tmp_path, capsys):
    path = tmp_path / "credential-secret.json"
    path.write_text("postgresql://user:secret@private-host/")
    assert helper.main(["json-field", str(path), "status", "ok"]) == 1
    output = capsys.readouterr()
    assert not output.out and "secret" not in output.err and "private-host" not in output.err


def test_helper_can_run_through_stdin_without_file_location_or_app_dependencies(tmp_path):
    path = tmp_path / "ready.json"
    path.write_text('{"status":"ok"}')
    program = Path(SPEC.origin).read_text()
    result = subprocess.run([sys.executable, "-", "json-field", str(path), "status", "ok"],
        input=program, text=True, capture_output=True, cwd=tmp_path, timeout=10)
    assert result.returncode == 0 and result.stdout == result.stderr == ""


def test_database_probe_accepts_real_postgresql_inet_address_format(monkeypatch):
    """Real regression: PostgreSQL inet::text includes /32 or /128; host() does not.

    Opt-in only, against an explicitly selected disposable test database. This
    test never imports the app or runs migrations; every statement is SELECT.
    """
    url = os.environ.get("SENTICO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL descartável não configurado para a regressão de inet.")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool

    configured = make_url(url)
    if url != os.environ.get("DATABASE_URL") or not (configured.database or "").endswith("_test"):
        pytest.fail("A regressão real exige o mesmo banco *_test explícito nas duas variáveis.")
    engine = create_engine(configured, poolclass=NullPool, connect_args={
        "connect_timeout": 10, "options": "-c default_transaction_read_only=on -c statement_timeout=10000",
    })
    try:
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT inet_server_addr()::text AS inet_text, "
                "host(inet_server_addr()) AS address, current_database() AS database_name, "
                "current_user AS user_name, current_setting('transaction_read_only') AS read_only"
            )).mappings().one()
            revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    finally:
        engine.dispose()
    assert row["read_only"] == "on" and len(revisions) == 1
    assert ipaddress.ip_interface(row["inet_text"]).ip == ipaddress.ip_address(row["address"])
    with pytest.raises(ValueError):
        ipaddress.ip_address(row["inet_text"])
    monkeypatch.setattr(helper, "_load_settings", lambda: SimpleNamespace(database_url=url))
    helper.probe_db(row["address"], row["database_name"], row["user_name"], revisions[0])
