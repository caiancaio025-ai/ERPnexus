"""Exercise the VPS updater with real Bash/Git and an isolated fake Docker daemon.

These tests never contact a VPS, launch Docker or use an operational database.
Only the daemon/network commands are substituted; the updater, its helper, Git,
backup files, archive validation, file replacement and shell traps run normally.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
FAKE_COMMANDS = Path(__file__).with_name("fakes") / "vps_commands.py"
PROJECT = "sentico-green-hml"
API = f"{PROJECT}-api-1"
WEB = f"{PROJECT}-web-1"
DB = f"{PROJECT}-db-1"
GATEWAY = f"{PROJECT}-gateway-1"
OLD_API = "sha256:" + "a" * 64
OLD_WEB = "sha256:" + "b" * 64
NEW_API = "sha256:" + "c" * 64
NEW_WEB = "sha256:" + "d" * 64
PG_IMAGE = "sha256:" + "e" * 64
OLD_TAG = "v47-fixture"
BASE_REVISION = "20261123_02"
TARGET_REVISION = "20261126_01"


class UpdaterSandbox:
    def __init__(self, path: Path):
        self.path = path
        self.app = path / "checkout"
        self.origin = path / "origin.git"
        self.bin = path / "bin"
        self.backups = path / "backups"
        self.events_path = path / "events.jsonl"
        self.state_path = path / "state.json"
        self.app.mkdir()
        self.bin.mkdir()
        self.backups.mkdir()
        for name in ("infra/vps/atualizar.sh", "infra/vps/deploy_v48.py", "docker-compose.prod.yml", "Caddyfile.green"):
            source = ROOT / name
            assert source.is_file(), f"Required updater file is missing: {source}"
            destination = self.app / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        (self.app / ".gitignore").write_text(".env.production\n.tag\n", encoding="utf-8")
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Updater test fixture")
        self.git("config", "user.email", "updater-test@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "Fixture release")
        self.git("init", "--bare", "--initial-branch=main", str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "--set-upstream", "origin", "main")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.old_env = (
            "# Fixture only: no operational credentials.\n"
            f"TAG={OLD_TAG}\n"
            "POSTGRES_DB=sentico_fixture\n"
            "POSTGRES_USER=fixture\n"
            "POSTGRES_PASSWORD=fixture-password\n"
            "DATABASE_URL=postgresql+psycopg://fixture:fixture-password@db:5432/sentico_fixture\n"
            "APP_ENV=production\n"
            "APP_NAME=Sentico Fixture\n"
            "SECRET_KEY=fixture-key-with-no-real-secret\n"
            "SENTICO_PUBLIC_URL=https://fixture.example.invalid\n"
        )
        (self.app / ".env.production").write_text(self.old_env, encoding="utf-8")
        (self.app / ".env.production").chmod(0o600)
        self.old_tag_bytes = f"{OLD_TAG}\n".encode()
        (self.app / ".tag").write_bytes(self.old_tag_bytes)
        self.initial_caddy = {
            "apps": {"http": {"servers": {"srv0": {
                "listen": [":8080"],
                "routes": [{"handle": [{"handler": "reverse_proxy", "upstreams": [{"dial": f"{WEB}:8080"}]}]}],
            }}}}
        }

        def container(name: str, image: str, reference: str, mounts: list[dict] | None = None):
            return {
                "Id": f"fixture-{name}-unchanged",
                "Name": f"/{name}",
                "Image": image,
                "Config": {"Image": reference, "Env": ["POSTGRES_DB=sentico_fixture", "POSTGRES_USER=fixture"]},
                "State": {"Running": True, "Health": {"Status": "healthy"}},
                "Mounts": mounts or [],
                "NetworkSettings": {"Networks": {f"{PROJECT}_green_private": {"IPAddress": "172.30.0.2"}}},
            }

        self.initial_state = {
            "failure": "",
            "project_dir": str(self.app),
            "old_tag": OLD_TAG,
            "old_api": OLD_API,
            "old_web": OLD_WEB,
            "new_api": NEW_API,
            "new_web": NEW_WEB,
            "pg_image": PG_IMAGE,
            "revision": "20261123_02",
            "caddy": self.initial_caddy,
            "initial_caddy": self.initial_caddy,
            "images": {
                f"sentico-green-api:{OLD_TAG}": OLD_API,
                f"sentico-green-web:{OLD_TAG}": OLD_WEB,
                "postgres:17-alpine": PG_IMAGE,
            },
            "containers": {
                API: container(API, OLD_API, f"sentico-green-api:{OLD_TAG}", [{"Type": "volume", "Name": f"{PROJECT}_green_uploads_data", "Destination": "/app/storage"}]),
                WEB: container(WEB, OLD_WEB, f"sentico-green-web:{OLD_TAG}"),
                DB: container(DB, PG_IMAGE, "postgres:17-alpine", [{"Type": "volume", "Name": f"{PROJECT}_green_postgres_data", "Destination": "/var/lib/postgresql/data"}]),
                GATEWAY: container(GATEWAY, "sha256:" + "f" * 64, "caddy:2.10-alpine"),
            },
            "volume_names": [f"{PROJECT}_green_postgres_data", f"{PROJECT}_green_uploads_data"],
        }
        self.write_state(self.initial_state)
        self.events_path.write_text("")
        for command in ("docker", "curl", "id", "sleep"):
            executable = self.bin / command
            executable.write_text(f"#!{sys.executable}\n" + FAKE_COMMANDS.read_text(encoding="utf-8"), encoding="utf-8")
            executable.chmod(0o755)

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.app, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"},
        )

    def write_state(self, value: dict) -> None:
        self.state_path.write_text(json.dumps(value), encoding="utf-8")

    @property
    def state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    @property
    def events(self) -> list[dict]:
        return [json.loads(line) for line in self.events_path.read_text().splitlines()]

    def run(self, failure: str = "") -> subprocess.CompletedProcess[str]:
        state = self.state
        state["failure"] = failure
        self.write_state(state)
        env = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "SENTICO_FAKE_STATE": str(self.state_path),
            "SENTICO_FAKE_EVENTS": str(self.events_path),
            "SENTICO_BACKUP_ROOT": str(self.backups),
            "SENTICO_LOCK_FILE": str(self.path / "deploy.lock"),
            "SENTICO_DEPLOY_RETRY_DELAY": "0",
            "SENTICO_DEPLOY_ATTEMPTS": "2",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        env.pop("TAG", None)
        return subprocess.run(
            ["bash", str(self.app / "infra/vps/atualizar.sh")],
            cwd=self.path, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
        )

    def assert_data_untouched(self, *, revision: str = BASE_REVISION) -> None:
        state = self.state
        assert state["containers"][DB] == self.initial_state["containers"][DB]
        assert state["volume_names"] == self.initial_state["volume_names"]
        assert state["revision"] == revision
        assert not state.get("copy_networks", [])
        assert not any(name.startswith(f"{PROJECT}-copy-") for name in state["containers"])
        for event in self.events:
            args = event["args"]
            command = " ".join(args)
            if event["tool"] == "docker":
                assert not ("volume" in args and any(item in args for item in ("rm", "prune"))), command
                assert not ("system" in args and "prune" in args), command
                assert not ("down" in args and any(item in args for item in ("-v", "--volumes"))), command
                if "pg_restore" in command and DB in args:
                    assert " -l" in command or "--list" in command or "--file" in command or "-f" in command, command
                    assert "--dbname" not in args and "-d" not in args, command

    def assert_old_application(self, *, had_tag: bool = True, revision: str = BASE_REVISION) -> None:
        state = self.state
        assert state["containers"][API]["Image"] == OLD_API
        assert state["containers"][WEB]["Image"] == OLD_WEB
        assert state["containers"][API]["State"]["Running"] is True
        assert state["containers"][WEB]["State"]["Running"] is True
        assert state["caddy"] == self.initial_caddy
        assert (self.app / ".env.production").read_text() == self.old_env
        assert (self.app / ".env.production").stat().st_mode & 0o777 == 0o600
        if had_tag:
            assert (self.app / ".tag").read_bytes() == self.old_tag_bytes
        else:
            assert not (self.app / ".tag").exists()
        assert not any("-preflight-" in name for name in state["containers"])
        self.assert_data_untouched(revision=revision)

    def details(self, result: subprocess.CompletedProcess[str]) -> str:
        logs = "\n".join(f"{p.name}:\n{p.read_text(errors='replace')[-2500:]}" for p in self.backups.rglob("*.log"))
        return f"exit={result.returncode}\n{result.stdout}\n{result.stderr}\n{logs}"

    def compose_events(self, operation: str) -> list[dict]:
        return [e for e in self.events if e["tool"] == "docker" and e["args"][:1] == ["compose"] and operation in e["args"]]


@pytest.fixture
def updater(tmp_path: Path) -> UpdaterSandbox:
    return UpdaterSandbox(tmp_path)


def test_dirty_checkout_is_rejected_before_docker_or_backup(updater: UpdaterSandbox):
    with (updater.app / "Caddyfile.green").open("a") as source:
        source.write("\n# local uncommitted change\n")
    result = updater.run()
    assert result.returncode != 0, updater.details(result)
    assert "sem alteracoes locais" in result.stderr
    assert not any(event["tool"] == "docker" for event in updater.events)
    assert not list(updater.backups.iterdir())
    updater.assert_old_application()


@pytest.mark.parametrize("failure", ["preflight", "database-target", "disk-space"])
def test_failed_candidate_preflight_never_interrupts_current_application(updater: UpdaterSandbox, failure: str):
    result = updater.run(failure)
    assert result.returncode != 0, updater.details(result)
    assert failure in updater.state.get("injected_failures", []), updater.details(result)
    assert updater.compose_events("build"), updater.details(result)
    assert not updater.compose_events("stop")
    assert not updater.compose_events("up")
    assert not any("pg_dump" in " ".join(e["args"]) for e in updater.events)
    assert not any("reload" in e["args"] for e in updater.events)
    assert any(e["args"][:2] == ["rm", "-f"] for e in updater.events)
    updater.assert_old_application()


@pytest.mark.parametrize("failure", ["backup", "backup-validation", "uploads-backup"])
def test_failed_backup_restarts_old_api_without_switching_images_or_environment(updater: UpdaterSandbox, failure: str):
    result = updater.run(failure)
    assert result.returncode != 0, updater.details(result)
    assert failure in updater.state.get("injected_failures", []), updater.details(result)
    assert "RETORNO_APLICACAO_ANTERIOR=OK" in result.stdout, updater.details(result)
    assert updater.compose_events("stop")
    assert not updater.compose_events("up")
    assert any(e["args"] == ["start", API] for e in updater.events)
    reloads = [e for e in updater.events if "caddy" in e["args"] and "reload" in e["args"]]
    assert len(reloads) >= 2
    assert json.loads(reloads[0]["stdin"]) != updater.initial_caddy
    assert json.loads(reloads[-1]["stdin"]) == updater.initial_caddy
    assert list(updater.backups.glob("*/banco.dump")), "Retain partial backup and logs for diagnosis"
    updater.assert_old_application()


def test_success_backs_up_before_switch_and_keeps_database_and_upload_volumes(updater: UpdaterSandbox):
    result = updater.run()
    assert result.returncode == 0, updater.details(result)
    assert "SENTICO_V48_ATUALIZADO=OK" in result.stdout
    new_tag = (updater.app / ".tag").read_text().strip()
    assert new_tag.startswith(f"v48-{updater.commit[:12]}-")
    assert (updater.app / ".env.production").read_text() == updater.old_env.replace(f"TAG={OLD_TAG}\n", f"TAG={new_tag}\n")
    assert (updater.app / ".tag").read_text() == new_tag + "\n"
    assert (updater.app / ".env.production").stat().st_mode & 0o777 == 0o600
    assert updater.state["containers"][API]["Image"] == NEW_API
    assert updater.state["containers"][WEB]["Image"] == NEW_WEB
    assert updater.state["caddy"] == updater.initial_caddy
    assert not any("-preflight-" in name for name in updater.state["containers"])
    updater.assert_data_untouched(revision=TARGET_REVISION)
    assert updater.git("status", "--porcelain").stdout == ""
    assert updater.git("rev-parse", "HEAD").stdout.strip() == updater.commit

    backups = list(updater.backups.iterdir())
    assert len(backups) == 1
    backup = backups[0]
    assert backup.stat().st_mode & 0o777 == 0o700
    assert (backup / "env.production.anterior").read_text() == updater.old_env
    assert (backup / "tag.anterior").read_bytes() == updater.old_tag_bytes
    assert "fixture-document.txt" in (backup / "uploads-inventario.txt").read_text()
    for line in (backup / "SHA256SUMS").read_text().splitlines():
        digest, filename = line.split()
        assert hashlib.sha256((backup / filename).read_bytes()).hexdigest() == digest

    events = updater.events
    build = next(i for i, e in enumerate(events) if "build" in e["args"])
    probe = next(i for i, e in enumerate(events) if "probe-db" in e["args"])
    maintenance = next(i for i, e in enumerate(events) if "caddy" in e["args"] and "reload" in e["args"])
    stopped = next(i for i, e in enumerate(events) if "stop" in e["args"])
    dump = next(i for i, e in enumerate(events) if "pg_dump" in " ".join(e["args"]))
    verified = next(i for i, e in enumerate(events) if "--file=/dev/null" in e["args"])
    archive = next(i for i, e in enumerate(events) if "--entrypoint" in e["args"] and "tar" in e["args"])
    restored = next(i for i, e in enumerate(events) if "pg_restore" in e["args"] and "--single-transaction" in e["args"])
    copy_migrated = next(i for i, e in enumerate(events) if "alembic" in e["args"] and "compose" not in e["args"])
    live_migrated = next(i for i, e in enumerate(events) if "alembic" in e["args"] and "compose" in e["args"])
    switched = next(i for i, e in enumerate(events) if e["args"][:1] == ["compose"] and "up" in e["args"])
    assert build < probe < maintenance < stopped < dump < verified < archive < restored < copy_migrated < live_migrated < switched
    assert len(updater.compose_events("up")) == 1
    backup_manifest = (backup / "imagens-e-revisao.txt").read_text()
    assert f"API_ANTERIOR={OLD_API}" in backup_manifest and f"WEB_ANTERIOR={OLD_WEB}" in backup_manifest
    assert f"REVISAO_ANTERIOR={BASE_REVISION}" in backup_manifest
    assert f"REVISAO_ALVO={TARGET_REVISION}" in backup_manifest
    assert (backup / "revisao-final.txt").read_text() == f"REVISAO_ANTERIOR={BASE_REVISION}\nREVISAO_FINAL={TARGET_REVISION}\n"
    assert (backup / "estoque.anterior.json").read_bytes() == (backup / "estoque.migrado.json").read_bytes()
    assert (backup / "estoque.anterior.json").read_bytes() == (backup / "estoque.copia.migrada.json").read_bytes()
    assert not (backup / "copia.env").exists()


@pytest.mark.parametrize("failure,had_tag", [
    ("switch", True), ("switch", False), ("readiness", True),
    ("gateway-assets", True), ("released-gateway", True),
])
def test_post_switch_failure_restores_exact_old_images_and_environment_without_database_restore(
    updater: UpdaterSandbox, failure: str, had_tag: bool,
):
    if not had_tag:
        (updater.app / ".tag").unlink()
    result = updater.run(failure)
    assert result.returncode != 0, updater.details(result)
    assert failure in updater.state.get("injected_failures", []), updater.details(result)
    assert "RETORNO_APLICACAO_ANTERIOR=OK" in result.stdout, updater.details(result)
    swaps = updater.compose_events("up")
    assert len(swaps) == 2, updater.details(result)
    assert swaps[0]["tag"].startswith(f"v48-{updater.commit[:12]}-")
    assert f"TAG={swaps[0]['tag']}\n" in swaps[0]["env"]
    assert swaps[1]["tag"].startswith("rollback-")
    assert swaps[1]["env"] == updater.old_env
    assert updater.state["images"][f"sentico-green-api:{swaps[1]['tag']}"] == OLD_API
    assert updater.state["images"][f"sentico-green-web:{swaps[1]['tag']}"] == OLD_WEB
    updater.assert_old_application(had_tag=had_tag, revision=TARGET_REVISION)
    if failure == "released-gateway":
        reloads = [json.loads(e["stdin"]) for e in updater.events if "caddy" in e["args"] and "reload" in e["args"]]
        assert len(reloads) == 4
        assert reloads[0] != updater.initial_caddy
        assert reloads[1] == updater.initial_caddy
        assert reloads[2] != updater.initial_caddy
        assert reloads[3] == updater.initial_caddy


def test_public_proxy_failure_keeps_verified_v48_running_and_returns_distinct_status(updater: UpdaterSandbox):
    result = updater.run("public")
    assert result.returncode == 2, updater.details(result)
    assert "public" in updater.state.get("injected_failures", []), updater.details(result)
    assert "V48_INTERNA=OK" in result.stderr
    assert "ACESSO_PUBLICO=NAO_CONFIRMADO" in result.stderr
    assert "RETORNO_APLICACAO_ANTERIOR" not in result.stdout
    assert len(updater.compose_events("up")) == 1
    assert updater.state["containers"][API]["Image"] == NEW_API
    assert updater.state["containers"][WEB]["Image"] == NEW_WEB
    assert updater.state["caddy"] == updater.initial_caddy
    assert (updater.app / ".tag").read_text().startswith(f"v48-{updater.commit[:12]}-")
    updater.assert_data_untouched(revision=TARGET_REVISION)


def test_repeating_same_commit_uses_new_tag_and_can_restore_previous_successful_build(updater: UpdaterSandbox):
    first = updater.run()
    assert first.returncode == 0, updater.details(first)
    previous_tag = (updater.app / ".tag").read_bytes()
    previous_env = (updater.app / ".env.production").read_bytes()
    previous_reference = previous_tag.decode().strip()
    state = updater.state
    state["old_api"] = NEW_API
    state["old_web"] = NEW_WEB
    # Building the identical commit may pull changed base layers/dependencies.
    # A new candidate must not overwrite the old tag that rollback depends on.
    state["new_api"] = "sha256:" + "1" * 64
    state["new_web"] = "sha256:" + "2" * 64
    updater.write_state(state)

    second = updater.run("readiness")
    assert second.returncode != 0, updater.details(second)
    assert "RETORNO_APLICACAO_ANTERIOR=OK" in second.stdout, updater.details(second)
    builds = updater.compose_events("build")
    assert len(builds) == 2 and builds[0]["tag"] != builds[1]["tag"]
    assert all(e["tag"].startswith(f"v48-{updater.commit[:12]}-") for e in builds)
    state = updater.state
    assert state["images"][f"sentico-green-api:{previous_reference}"] == NEW_API
    assert state["images"][f"sentico-green-web:{previous_reference}"] == NEW_WEB
    assert state["containers"][API]["Image"] == NEW_API
    assert state["containers"][WEB]["Image"] == NEW_WEB
    assert state["containers"][API]["State"]["Running"] is True
    assert state["containers"][WEB]["State"]["Running"] is True
    assert state["caddy"] == updater.initial_caddy
    assert (updater.app / ".env.production").read_bytes() == previous_env
    assert (updater.app / ".tag").read_bytes() == previous_tag
    assert len(list(updater.backups.iterdir())) == 2
    updater.assert_data_untouched(revision=TARGET_REVISION)
    assert updater.state["migration_calls"] == 1, "A repeat run must not reapply the committed migration"


@pytest.mark.parametrize("failure", ["copy-start", "copy-restore", "copy-data", "copy-migration"])
def test_failed_isolated_rehearsal_keeps_live_revision_and_restores_old_api(updater: UpdaterSandbox, failure: str):
    result = updater.run(failure)
    assert result.returncode != 0, updater.details(result)
    assert failure in updater.state.get("injected_failures", []), updater.details(result)
    assert "RETORNO_APLICACAO_ANTERIOR=OK" in result.stdout, updater.details(result)
    assert not updater.state.get("migration_calls", 0)
    assert not updater.compose_events("up")
    assert not list(updater.backups.glob("*/copia.env"))
    updater.assert_old_application()


@pytest.mark.parametrize("failure,expected_revision", [
    ("migration", BASE_REVISION), ("migration-after-commit", TARGET_REVISION),
])
def test_migration_failure_never_downgrades_or_restores_database(
    updater: UpdaterSandbox, failure: str, expected_revision: str,
):
    result = updater.run(failure)
    assert result.returncode != 0, updater.details(result)
    assert failure in updater.state.get("injected_failures", []), updater.details(result)
    assert updater.state.get("copy_verified")
    assert updater.state["migration_calls"] == 1
    assert "RETORNO_APLICACAO_ANTERIOR=OK" in result.stdout, updater.details(result)
    assert f"REVISAO_BANCO_APOS_RETORNO={expected_revision}" in result.stdout
    assert not any("downgrade" in e["args"] for e in updater.events)
    assert not updater.compose_events("up")
    updater.assert_old_application(revision=expected_revision)
    backup = next(updater.backups.iterdir())
    assert f"REVISAO_FINAL={expected_revision}\n" in (backup / "revisao-final.txt").read_text()


def test_already_migrated_database_is_verified_without_reapplying_migration(updater: UpdaterSandbox):
    state = updater.state
    state["revision"] = TARGET_REVISION
    updater.write_state(state)
    result = updater.run()
    assert result.returncode == 0, updater.details(result)
    assert not any("alembic" in e["args"] for e in updater.events)
    assert any("--single-transaction" in e["args"] for e in updater.events)
    updater.assert_data_untouched(revision=TARGET_REVISION)


def test_unknown_database_revision_is_rejected_before_build_or_stop(updater: UpdaterSandbox):
    state = updater.state
    state["revision"] = "unexpected_revision"
    updater.write_state(state)
    result = updater.run()
    assert result.returncode != 0, updater.details(result)
    assert "nenhuma migracao foi executada" in result.stderr
    assert not updater.compose_events("build") and not updater.compose_events("stop")
    updater.assert_old_application(revision="unexpected_revision")
