"""Checks that operational upgrades and disposable tests cannot share DB volumes."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT


def test_disposable_stack_has_no_operational_volumes_or_published_ports():
    operation = yaml.safe_load((CODE / "compose.recuperacao.yml").read_text())
    tests = yaml.safe_load((CODE / "compose.tests.yml").read_text())
    assert operation["name"] != tests["name"] == "sentico-v48-testes"
    assert not tests.get("volumes")
    assert tests["services"]["db"]["tmpfs"] == ["/var/lib/postgresql/data"]
    for service in tests["services"].values():
        assert not service.get("ports")
        for mount in service.get("volumes", []):
            assert mount.startswith("./resultados_testes:")
    env = tests["services"]["api-tests"]["environment"]
    assert env["DATABASE_URL"] == env["SENTICO_TEST_DATABASE_URL"]
    assert env["DATABASE_URL"].endswith("/sentico_test")


def test_operational_ui_is_compiled_and_api_is_not_auto_reloaded():
    runtime = yaml.safe_load((CODE / "compose.recuperacao.yml").read_text())
    services = runtime["services"]
    assert services["web"]["build"]["dockerfile"] == "Dockerfile"
    assert not services["web"].get("volumes")
    assert "--reload" not in services["api"]["command"]
    assert "--workers" in services["api"]["command"]
    assert "/health/ready" in " ".join(services["api"]["healthcheck"]["test"])
    assert "web:8080" in (CODE / "Caddyfile.runtime").read_text()
    assert "127.0.0.1:5183:8080" in services["web"]["ports"]


def test_test_runner_requires_explicit_disposable_database():
    runner = (CODE / "apps/api/scripts/run_v48_tests.py").read_text()
    assert 'SENTICO_ISOLATED_TEST_RUN' in runner
    assert 'endswith("_test")' in runner
    script = (ROOT / "TESTAR_SENTICO.ps1").read_text()
    assert "$ProjetoTeste = 'sentico-v48-testes'" in script
    assert "-p $ProjetoTeste -f $ArquivoTeste" in script
    assert "docker.exe volume" not in script
    assert "docker.exe system prune" not in script
