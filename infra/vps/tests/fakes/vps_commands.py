"""Small, stateful command double used only by test_v48_vps_update.py.

The harness writes this module behind executable names in its temporary PATH.
Unknown commands fail, so additions to the real updater must be modeled explicitly.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile


PROJECT = "sentico-green-hml"
API = f"{PROJECT}-api-1"
WEB = f"{PROJECT}-web-1"
DB = f"{PROJECT}-db-1"
GATEWAY = f"{PROJECT}-gateway-1"
TARGET_REVISION = "20261126_01"
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
state_path = Path(os.environ["SENTICO_FAKE_STATE"])
state = json.loads(state_path.read_text())
input_bytes = sys.stdin.buffer.read()
event = {
    "tool": tool,
    "args": args,
    "stdin": input_bytes.decode("utf-8", errors="replace"),
    "tag": os.environ.get("TAG"),
    "env": (Path(state["project_dir"]) / ".env.production").read_text(),
}
with Path(os.environ["SENTICO_FAKE_EVENTS"]).open("a") as log:
    log.write(json.dumps(event) + "\n")


def done(output="", code=0):
    state_path.write_text(json.dumps(state))
    if isinstance(output, bytes):
        sys.stdout.buffer.write(output)
    elif output:
        print(output)
    raise SystemExit(code)


def unsupported():
    print(f"FAKE UNSUPPORTED: {tool} {args!r}", file=sys.stderr)
    done(code=97)


def fail_if(name):
    if state["failure"] == name:
        state.setdefault("injected_failures", []).append(name)
        print(f"Injected fixture failure: {name}", file=sys.stderr)
        done(code=23)


def inventory_snapshot(*, copy=False):
    snapshot = {"inventory_items": {"rows": 10, "quantity": "10", "value": "125.00", "sha256": "items-fixture"},
                "inventory_movements": {"rows": 10, "quantity": "10", "value": "125.00", "sha256": "movements-fixture"}}
    if copy and state["failure"] == "copy-data":
        state.setdefault("injected_failures", []).append("copy-data")
        snapshot["inventory_movements"]["quantity"] = "11"
    return json.dumps(snapshot, sort_keys=True)


def env_tag():
    if os.environ.get("TAG"):
        return os.environ["TAG"]
    for line in event["env"].splitlines():
        if line.startswith("TAG="):
            return line.partition("=")[2]
    raise AssertionError("Fixture .env.production has no TAG")


def html():
    original = state["images"][f"sentico-green-web:{state['old_tag']}"]
    release = "47" if state["containers"][WEB]["Image"] == original else "48"
    return (
        f'<!doctype html><html><head><script type="module" src="/assets/index-v{release}.js"></script>'
        f'<link rel="stylesheet" href="/assets/index-v{release}.css"></head><body>Fixture V{release}</body></html>\n'
    ).encode()


def asset(path):
    if path.endswith(".js"):
        return f"console.log({json.dumps(path)});\n".encode()
    if path.endswith(".css"):
        return f"/* {path} */ body {{ color: #123; }}\n".encode()
    raise AssertionError(f"Unexpected fixture asset: {path}")


def maintenance():
    return state["caddy"] != state["initial_caddy"]


def inspect_value(value, template):
    if template in ("{{.Id}}", "{{.Image}}", "{{.Config.Image}}"):
        item = value
        for part in template.removeprefix("{{.").removesuffix("}}").split("."):
            item = item[part]
        return item
    if template == "{{.State.Running}}":
        return str(value["State"]["Running"]).lower()
    if template == '{{index .Config.Labels "com.docker.compose.project"}}':
        return PROJECT
    if '"/var/lib/postgresql/data"' in template or '"/app/storage"' in template:
        target = "/app/storage" if '"/app/storage"' in template else "/var/lib/postgresql/data"
        return next((m["Name"] for m in value["Mounts"] if m["Destination"] == target), "")
    if "NetworkSettings.Networks" in template and "IPAddress" in template:
        return value["NetworkSettings"]["Networks"][f"{PROJECT}_green_private"]["IPAddress"]
    unsupported()


def compose(command):
    operation = command[0]
    tag = env_tag()
    if operation == "version":
        done("Docker Compose fixture")
    if operation == "config":
        fail_if("config")
        if "--quiet" in command:
            done()
        if command[1:] == ["--format", "json"]:
            done(json.dumps({
                "name": PROJECT,
                "services": {
                    "api": {"image": f"sentico-green-api:{tag}", "volumes": [{"source": "green_uploads_data", "target": "/app/storage"}]},
                    "web": {"image": f"sentico-green-web:{tag}"},
                    "db": {"image": "postgres:17-alpine", "volumes": [{"source": "green_postgres_data", "target": "/var/lib/postgresql/data"}]},
                },
                "volumes": {
                    "green_postgres_data": {"external": True, "name": f"{PROJECT}_green_postgres_data"},
                    "green_uploads_data": {"external": True, "name": f"{PROJECT}_green_uploads_data"},
                },
            }))
        unsupported()
    if operation == "build" and command[1:] == ["api", "web"]:
        fail_if("build")
        assert tag.startswith("v48-"), tag
        state["images"][f"sentico-green-api:{tag}"] = state["new_api"]
        state["images"][f"sentico-green-web:{tag}"] = state["new_web"]
        done("Fixture build complete")
    if operation == "run" and "inventory-snapshot" in command:
        assert command[-3:] == ["-", "inventory-snapshot", state["revision"]]
        assert "PGOPTIONS=-c default_transaction_read_only=on" in command
        assert "--no-deps" in command and "--rm" in command and "--entrypoint" in command
        assert command[command.index("--entrypoint") + 1] == "python"
        assert input_bytes
        done(inventory_snapshot())
    if operation == "run" and "alembic" in command:
        assert command[-3:] == ["api", "upgrade", TARGET_REVISION]
        assert command[command.index("--entrypoint") + 1] == "alembic"
        assert maintenance() and not state["containers"][API]["State"]["Running"]
        assert state.get("copy_verified"), "Real migration requires a restored and verified migrated copy"
        assert state["revision"] == "20261123_02"
        state["migration_calls"] = state.get("migration_calls", 0) + 1
        fail_if("migration")
        state["revision"] = TARGET_REVISION
        fail_if("migration-after-commit")
        done("Fixture live migration committed")
    if operation == "run" and "--name" in command and command[-1] == "api":
        assert "--no-deps" in command and "--service-ports" not in command and "--use-aliases" not in command
        assert "PGOPTIONS=-c default_transaction_read_only=on" in command
        name = command[command.index("--name") + 1]
        assert name.startswith(f"{PROJECT}-preflight-")
        reference = f"sentico-green-api:{tag}"
        state["containers"][name] = {
            "Id": name, "Image": state["images"][reference], "Config": {"Image": reference},
            "State": {"Running": True},
        }
        done(name)
    if operation == "stop" and command[1:] == ["-t", "45", "api"]:
        assert maintenance(), "Live API must not be stopped before gateway maintenance"
        state["containers"][API]["State"]["Running"] = False
        done()
    if operation == "up" and command[1:] == ["-d", "--no-deps", "--no-build", "--pull", "never", "api", "web"]:
        assert maintenance(), "Application images must not be swapped while public traffic is open"
        for service, name in (("api", API), ("web", WEB)):
            reference = f"sentico-green-{service}:{tag}"
            image = state["images"][reference]
            state["containers"][name]["Id"] = f"replacement-{name}-{tag}"
            state["containers"][name]["Image"] = image
            state["containers"][name]["Config"]["Image"] = reference
            state["containers"][name]["State"]["Running"] = True
            if tag.startswith("v48-") and service == "api":
                fail_if("switch")  # A realistic partial replacement: API changed, web still old.
        done()
    unsupported()


def docker_exec(command):
    while command and command[0].startswith("-"):
        option = command.pop(0)
        if option in ("-e", "--env"):
            command.pop(0)
        else:
            assert option in ("-i", "-t", "-it"), option
    name = command.pop(0)
    assert name in state["containers"], f"No fixture container: {name}"
    assert state["containers"][name]["State"]["Running"], f"Fixture container stopped: {name}"
    if command[:2] == ["python", "-"]:
        mode = command[2]
        assert input_bytes, "The real helper must be streamed into the container"
        if mode == "probe-http":
            if name.startswith(f"{PROJECT}-preflight-"):
                fail_if("preflight")
            elif name == API and state["containers"][API]["Image"] == state["new_api"]:
                fail_if("readiness")
            done("probe-http OK")
        if mode == "probe-db":
            assert name.startswith(f"{PROJECT}-preflight-")
            assert command[3:] == ["172.30.0.2", "sentico_fixture", "fixture", state["revision"]]
            fail_if("database-target")
            done("probe-db OK")
        if mode == "probe-uploads":
            done("probe-uploads OK")
        unsupported()
    if name == DB and command[:2] == ["sh", "-ec"]:
        shell = command[2]
        if "pg_dump" in shell:
            assert not state["containers"][API]["State"]["Running"], "Backup must follow API stop"
            if state["failure"] == "backup":
                state.setdefault("injected_failures", []).append("backup")
                done(b"PGDMP-incomplete-fixture", code=23)
            done(b"PGDMP-complete-fixture-database\n")
        if "psql" in shell:
            assert "default_transaction_read_only=on" in shell
            if input_bytes.strip() == b"SELECT pg_database_size(current_database());":
                if state["failure"] == "disk-space":
                    state.setdefault("injected_failures", []).append("disk-space")
                    done(str(1 << 100))
                done("65536")
            assert input_bytes.strip() == b"SELECT version_num FROM public.alembic_version;"
            done(state["revision"])
        unsupported()
    if name == DB and command[:1] == ["pg_restore"]:
        assert input_bytes == b"PGDMP-complete-fixture-database\n"
        assert "-d" not in command and not any(a.startswith("--dbname") for a in command)
        if command[1:] == ["--list"]:
            done("; Fixture dump inventory\n1; 0 0 TABLE DATA public fixture")
        if command[1:] == ["--no-owner", "--no-privileges", "--file=/dev/null"]:
            fail_if("backup-validation")
            done()
        unsupported()
    if name == DB and command[:1] == ["printenv"]:
        done({"POSTGRES_DB": "sentico_fixture", "POSTGRES_USER": "fixture"}[command[1]])
    if name.startswith(f"{PROJECT}-copy-"):
        if command[:1] == ["pg_isready"]:
            fail_if("copy-start")
            done()
        if command[:1] == ["pg_restore"]:
            assert input_bytes == b"PGDMP-complete-fixture-database\n"
            assert "--single-transaction" in command and "--exit-on-error" in command
            assert "--no-owner" in command and "--no-privileges" in command
            assert command[-4:] == ["-U", "sentico_deploy_copy", "-d", "sentico_deploy_copy"]
            fail_if("copy-restore")
            state["copy_revision"] = state["revision"]
            done()
    if name == GATEWAY and command == ["wget", "-qO-", "http://127.0.0.1:2019/config/"]:
        done(json.dumps(state["caddy"]))
    if name == GATEWAY and command[:1] == ["caddy"]:
        assert command[1:] in (["validate", "--config", "-"], ["reload", "--config", "-"])
        config = json.loads(input_bytes)
        if command[1] == "reload":
            state["caddy"] = config
        done()
    if name == WEB and command == ["cat", "/srv/index.html"]:
        done(html())
    if name == WEB and command[:1] == ["sha256sum"]:
        data = asset(command[1].removeprefix("/srv"))
        done(f"{hashlib.sha256(data).hexdigest()}  {command[1]}")
    if name == WEB and command == ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]:
        done()
    unsupported()


def docker():
    if args == ["info", "--format", "{{.DockerRootDir}}"]:
        done(state["project_dir"])
    if args[:3] == ["network", "create", "--internal"]:
        assert len(args) == 4 and args[3].startswith(f"{PROJECT}-copy-network-")
        state.setdefault("copy_networks", []).append(args[3])
        done(args[3])
    if args[:2] == ["network", "rm"]:
        assert len(args) == 3 and args[2].startswith(f"{PROJECT}-copy-network-")
        state["copy_networks"].remove(args[2])
        done(args[2])
    if args[:1] == ["compose"]:
        command = args[1:]
        while command and command[0].startswith("-"):
            assert command[0] in ("--project-directory", "-p", "--env-file", "-f"), command
            command = command[2:]
        compose(command)
    if args[:1] == ["inspect"] and args[1:2] == ["--format"]:
        done(inspect_value(state["containers"][args[3]], args[2]))
    if args[:2] == ["image", "inspect"] and args[2:4] == ["--format", "{{.Id}}"]:
        done(state["images"][args[4]])
    if args[:2] == ["image", "tag"]:
        assert args[2] in (state["old_api"], state["old_web"])
        state["images"][args[3]] = args[2]
        done()
    if args[:2] == ["volume", "inspect"]:
        assert args[2:] == state["volume_names"]
        done(json.dumps([{"Name": name} for name in args[2:]]))
    if args[:1] == ["exec"]:
        docker_exec(args[1:])
    if args[:2] == ["rm", "-f"]:
        assert len(args) == 3 and args[2].startswith((f"{PROJECT}-preflight-", f"{PROJECT}-copy-"))
        state["containers"].pop(args[2], None)
        done()
    if args == ["start", API]:
        assert maintenance(), "Recovery must keep maintenance active until the old API is ready"
        state["containers"][API]["State"]["Running"] = True
        done(API)
    if args[:1] == ["run"] and "--network" in args and args[args.index("--network") + 1].startswith(f"{PROJECT}-copy-network-"):
        assert "--rm" in args and "--pull" in args
        assert "--mount" not in args and "-v" not in args and "--volume" not in args
        assert "-p" not in args and "--publish" not in args
        assert maintenance() and not state["containers"][API]["State"]["Running"]
        env_file = Path(args[args.index("--env-file") + 1])
        assert env_file.name == "copia.env" and env_file.stat().st_mode & 0o777 == 0o600
        copy_env = dict(line.split("=", 1) for line in env_file.read_text().splitlines())
        assert copy_env["POSTGRES_USER"] == copy_env["POSTGRES_DB"] == "sentico_deploy_copy"
        assert copy_env["DATABASE_URL"].startswith("postgresql+psycopg://sentico_deploy_copy:")
        if "--name" in args:
            name = args[args.index("--name") + 1]
            assert name.startswith(f"{PROJECT}-copy-") and args[-1] == state["pg_image"]
            assert f"@{name}:5432/sentico_deploy_copy" in copy_env["DATABASE_URL"]
            state["containers"][name] = {"Id": name, "Image": state["pg_image"], "State": {"Running": True}}
            done(name)
        if "inventory-snapshot" in args:
            assert args[-3:] == ["-", "inventory-snapshot", state["copy_revision"]]
            if state["copy_revision"] == TARGET_REVISION:
                state["copy_verified"] = True
            done(inventory_snapshot(copy=True))
        if "alembic" in args:
            assert args[-2:] == ["upgrade", TARGET_REVISION]
            assert state["copy_revision"] == "20261123_02"
            fail_if("copy-migration")
            state["copy_revision"] = TARGET_REVISION
            done("Fixture isolated migration committed")
        unsupported()
    if args[:1] == ["run"] and "--entrypoint" in args and "du" in args:
        assert "--network" in args and args[args.index("--network") + 1] == "none"
        assert "--read-only" in args
        assert f"type=volume,src={PROJECT}_green_uploads_data,dst=/uploads,readonly" in args
        assert args[-2:] == ["-sk", "/uploads"]
        assert not maintenance() and state["containers"][API]["State"]["Running"]
        done("4\t/uploads")
    if args[:1] == ["run"] and "--entrypoint" in args and "tar" in args:
        assert "--network" in args and args[args.index("--network") + 1] == "none"
        assert "--read-only" in args
        assert f"type=volume,src={PROJECT}_green_uploads_data,dst=/uploads,readonly" in args
        assert not state["containers"][API]["State"]["Running"]
        if state["failure"] == "uploads-backup":
            state.setdefault("injected_failures", []).append("uploads-backup")
            done(b"invalid-gzip-archive")
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            data = b"Existing fixture attachment is preserved.\n"
            entry = tarfile.TarInfo("uploads/fixture-document.txt")
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
        done(stream.getvalue())
    unsupported()


def curl():
    url = next((arg for arg in args if arg.startswith(("http://", "https://"))), None)
    assert url, args
    public = url.startswith("https://")
    if public:
        fail_if("public")
    header = next((arg for arg in args if arg.startswith("X-Sentico-Deploy-Check:")), "")
    bypass = bool(header)
    if maintenance() and bypass:
        servers = state["caddy"]["apps"]["http"]["servers"]
        routes = next(iter(servers.values()))["routes"]
        allowed = routes[0]["match"][0]["header"]["X-Sentico-Deploy-Check"]
        bypass = header.partition(":")[2].strip() in allowed
    if "-w" in args:
        assert not bypass and not public
        done("503" if maintenance() else "200")
    if maintenance() and not bypass:
        done(code=22)
    if url.endswith("/api/health/ready"):
        body = b'{"status":"ok"}\n'
    elif url.endswith("/api/health/version"):
        if not public and not bypass and state["containers"][API]["Image"] == state["new_api"]:
            fail_if("released-gateway")
        original = state["images"][f"sentico-green-api:{state['old_tag']}"]
        version = "47" if state["containers"][API]["Image"] == original else "48"
        body = json.dumps({"version": version}).encode()
    elif "/assets/" in url:
        body = asset("/assets/" + url.split("/assets/", 1)[1])
        if state["failure"] == "gateway-assets":
            state.setdefault("injected_failures", []).append("gateway-assets")
            body = b"stale-cached-asset"
    elif url.endswith("/"):
        body = html()
    else:
        unsupported()
    if "-o" in args:
        Path(args[args.index("-o") + 1]).write_bytes(body)
        done()
    done(body)


if tool == "id" and args == ["-u"]:
    done("0")
elif tool == "sleep":
    done()
elif tool == "docker":
    docker()
elif tool == "curl":
    curl()
unsupported()
