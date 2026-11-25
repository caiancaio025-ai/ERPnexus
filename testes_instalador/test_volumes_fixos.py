"""Contrato real do instalador V14; testes estaticos, nao homologacao no Docker Desktop."""
from pathlib import Path
import ast
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / 'compose.recuperacao.yml'
INST = ROOT / 'INSTALAR_SENTICO.ps1'
EXPECTED = {
    'v14_pgdata': '${SENTICO_PGDATA_VOLUME:-sentico-v14-recuperado_pgdata}',
    'v14_uploads': '${SENTICO_UPLOADS_VOLUME:-sentico-v14-recuperado_uploads}',
    'v14_node_modules': '${SENTICO_NODE_VOLUME:-sentico-v14-recuperado_node_modules}',
}


def test_volumes_originais_sao_externos_e_imutaveis():
    obj = yaml.safe_load(COMP.read_text(encoding='utf-8'))
    assert obj['name'] == 'sentico-v14-recuperado'
    assert {k: v['name'] for k, v in obj['volumes'].items()} == EXPECTED
    assert all(v.get('external') is True for v in obj['volumes'].values())
    script = INST.read_text(encoding='utf-8')
    for vol in EXPECTED.values():
        assert vol.split(':-')[-1].rstrip('}') in script
    assert 'sentico_v14_local_pgdata' not in script


def test_portas_localhost_e_sem_conflitos_com_blue():
    obj = yaml.safe_load(COMP.read_text(encoding='utf-8'))
    ports = [x for svc in obj['services'].values() for x in svc.get('ports', [])]
    assert set(ports) == {'127.0.0.1:5543:5432', '127.0.0.1:5184:8080',
                          '127.0.0.1:5183:8080', '127.0.0.1:8183:8000'}
    assert all(str(p).startswith('127.0.0.1:') for p in ports)


def test_inspecao_readonly_usa_marcador_e_nao_contagem_de_linhas():
    script = INST.read_text(encoding='utf-8')
    section = script.split('function EstadoVolume([string]$nome,[bool]$silencioso=$false)',1)[1].split('function LerEnv',1)[0]
    assert 'EstadoVolume' in script
    assert 'type=volume,source=$nome,target=/dados,readonly' in section
    assert 'type=bind,source=$ScriptsDir,target=/scripts,readonly' in section
    assert "'--network','none'" in section
    assert 'estado_volume_v14.sh' in section
    assert 'SENTICO_ESTADO_VOLUME=' in section
    assert '$r.Lines.Count -ne 1' not in section
    assert 'ERRO_INSPECAO_VOLUME_DOCKER' in section
    helper = (ROOT/'scripts_recuperacao/estado_volume_v14.sh').read_text()
    assert 'SENTICO_ESTADO_VOLUME=PG_VERSION=17' in helper
    assert 'SENTICO_ESTADO_VOLUME=VAZIO' in helper
    assert 'SENTICO_ESTADO_VOLUME=INESPERADO' in helper
    assert '/dados/global/pg_control' in helper


def test_sem_operacoes_destrutivas_e_sem_migracoes_antes_dos_checks():
    t = INST.read_text(encoding='utf-8')
    for op in (r"Docker\s+@\('volume','rm'",r"Compose\s+@\('down'",
               r"Docker\s+@\('system','prune'",r"Docker\s+@\('volume','prune'"):
        assert re.search(op, t) is None
    assert t.index('EstadoVolume $VolumeBanco') < t.index("Compose @('up','-d','--no-build','db')")
    assert t.index('$write=TestarEscritaApi') < t.index("Compose @('exec','-T','api','alembic','upgrade','head')")
    assert t.index("ExecutarScriptNoBanco 'catalogar_bancos_existentes.sh'") < t.index("Compose @('build','api','web')")
    assert 'sentico-dev-entrega_dev_postgres_data' not in (ROOT/'compose.recuperacao.yml').read_text()


def test_sem_contagens_exatas_e_escolha_de_banco_por_migracao():
    t = INST.read_text(encoding='utf-8')
    assert 'ERRO_NENHUM_BACKUP_COM_12_USUARIOS' not in t
    assert 'catalogar_bancos_existentes.sh' in t
    assert 'MelhorBanco' in t
    assert 'sentico_green' in t


def test_versoes_migration_encadeadas():
    path = ROOT / 'apps/api/migrations/versions'
    versions = {}
    for f in path.glob('*.py'):
        tree = ast.parse(f.read_text(encoding='utf-8'))
        vals = {}
        for x in tree.body:
            if isinstance(x, (ast.Assign, ast.AnnAssign)):
                targets = x.targets if isinstance(x, ast.Assign) else [x.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in ('revision', 'down_revision'):
                        try:
                            vals[target.id] = ast.literal_eval(x.value)
                        except (ValueError, TypeError):
                            pass
        if vals.get('revision'):
            versions[vals['revision']] = vals.get('down_revision')
    rev = '20261116_01'
    chain = [rev]
    while rev != '20261013_02':
        rev = versions[rev]
        assert rev not in chain
        chain.append(rev)
    assert len(chain) == 14


def test_api_preflight_e_lancador():
    script = (ROOT / 'apps/api/scripts/verificar_escrita_recuperacao.py').read_text()
    for x in ('SENTICO_DB_NAME', 'ALLOWED_REVISIONS', 'CREATE TEMP TABLE', 'pg_is_in_recovery()'):
        assert x in script
    assert 'INSTALAR_SENTICO.ps1' in (ROOT / 'INICIAR_SENTICO.cmd').read_text()
    t = INST.read_text(encoding='utf-8')
    assert "'Sentico\\RecuperacaoV14'" in t
    assert 'LerEnv' in t and 'EscreverEnv' in t
