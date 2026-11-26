"""Isolation contracts for the Windows manual launcher; no Docker mutations."""
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_manual_compose_has_its_own_persistent_volumes_and_private_network():
    config = yaml.safe_load((ROOT / 'compose.teste-local.yml').read_text())
    assert config['name'] == 'sentico-v48-teste-local'
    assert config['volumes'] == {
        'pgdata': {'name': 'sentico-v48-teste-local_pgdata'},
        'uploads': {'name': 'sentico-v48-teste-local_uploads'},
    }
    assert config['networks'] == {'teste_local': {'name': 'sentico-v48-teste-local_rede', 'internal': True}}
    assert config['services']['db']['volumes'] == ['pgdata:/var/lib/postgresql/data']
    assert config['services']['api']['volumes'] == ['uploads:/app/storage']
    for service in config['services'].values():
        assert service['networks'] == ['teste_local']
        assert 'env_file' not in service and 'container_name' not in service
    assert 'ports' not in config['services']['db']
    assert 'ports' not in config['services']['api']
    assert config['services']['web']['ports'] == ['127.0.0.1:${SENTICO_V48_TEST_PORT:-5185}:8080']


def test_manual_api_is_built_from_current_source_and_waits_for_the_guarded_bootstrap():
    services = yaml.safe_load((ROOT / 'compose.teste-local.yml').read_text())['services']
    assert services['api']['build'] == {'context': './apps/api', 'dockerfile': 'Dockerfile'}
    assert services['web']['build'] == {'context': './apps/web', 'dockerfile': 'Dockerfile'}
    assert services['api']['image'] == services['bootstrap']['image']
    assert services['api']['depends_on']['bootstrap']['condition'] == 'service_completed_successfully'
    assert services['bootstrap']['entrypoint'] == ['python', '/bootstrap/bootstrap_v48.py']
    assert services['bootstrap']['volumes'] == [{
        'type': 'bind', 'source': './infra/teste-local/bootstrap_v48.py',
        'target': '/bootstrap/bootstrap_v48.py', 'read_only': True,
    }]
    assert services['db']['environment']['POSTGRES_DB'] == 'sentico_v48_test'
    assert services['db']['environment']['POSTGRES_USER'] == 'sentico_v48_test'
    environment = services['api']['environment']
    assert environment['APP_ENV'] == 'development'
    assert environment['SESSION_COOKIE_NAME'] == 'sentico_v48_teste_local_session'
    assert environment['TRACKING_BASE_URL'].endswith('/api/e')
    assert environment['SENTICO_DEV_TEST_ACCOUNT'] == '0'
    assert 'SENTICO_LOCAL_TEST_PASSWORD' not in environment


def test_manual_start_pins_local_context_project_and_config_before_mutating_docker():
    script = (ROOT / 'TESTE_LOCAL_V48.ps1').read_text(encoding='utf-8-sig')
    assert "'^npipe:////\\./pipe/[A-Za-z0-9_.-]+$'" in script
    assert "@('info','--format','{{.OSType}}')" in script
    assert '& docker.exe --context $ContextoDocker @Argumentos' in script
    assert "@('compose','--project-directory',$PSScriptRoot,'-p',$ProjetoTeste,'--env-file',$ArquivoAmbiente,'-f',$ArquivoCompose)" in script
    assert '[Environment]::SetEnvironmentVariable($chave, $valores[$chave], \'Process\')' in script
    assert '[Environment]::SetEnvironmentVariable($chave, $AmbienteAnterior[$chave], \'Process\')' in script
    assert script.index('    ConfirmarDockerLocal') < script.index('        ConferirCompose $BaseCompose') < script.index("@('build','api','web')")
    assert "'name=sentico-v48-teste-local_'" in script


def test_manual_stop_preserves_data_and_credentials_survive_zip_extraction():
    script = (ROOT / 'TESTE_LOCAL_V48.ps1').read_text(encoding='utf-8-sig')
    stop = (ROOT / 'PARAR_TESTE_V48.cmd').read_text()
    assert '-Acao Parar' in stop
    assert "Join-Path $env:LOCALAPPDATA 'Sentico\\TesteLocalV48'" in script
    assert "'acesso.txt'" in script and 'Senha inicial:' in script
    assert "[Security.Cryptography.RandomNumberGenerator]::Create()" in script
    assert 'Local\\SenticoV48TesteLocal' in script
    assert "@('stop','--time','30') + $ids" in script
    assert 'if ($ids.Count -gt 0)' in script
    for dangerous in ("'down'", "'prune'", "'volume','rm'", 'compose.recuperacao.yml', '.env.production', 'INSTALAR_SENTICO.ps1'):
        assert dangerous not in script


def test_browser_opens_only_after_both_real_health_checks_and_version_48():
    script = (ROOT / 'TESTE_LOCAL_V48.ps1').read_text(encoding='utf-8-sig')
    assert '$Url/api/health/ready' in script and '$Url/api/health/version' in script
    assert '-TimeoutSec 5' in script and 'AddSeconds(180)' in script
    assert script.index('        EsperarAplicacao $UrlTeste') < script.index("Write-Host 'SENTICO_TESTE_V48=OK'") < script.index('Start-Process $UrlTeste')
    assert 'EscolherPorta $desejada $explicita' in script and 'PortaDoProprioTeste' in script
    assert "'run','--rm','--no-deps','--pull','never','bootstrap'" in script
