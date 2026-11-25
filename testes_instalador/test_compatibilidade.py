"""Contratos estaticos, complementados por testes de shell com psql simulado.
Nao substitui homologacao no Docker Desktop/Windows.
"""
from pathlib import Path
import re
import ast
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT/'compose.recuperacao.yml'
INSTALL = ROOT/'INSTALAR_SENTICO.ps1'
SCRIPTS = ROOT/'scripts_recuperacao'


def test_compose_permita_volumes_dinamicos_com_defaults_antigos():
    obj = yaml.safe_load(COMPOSE.read_text())
    assert obj['name'] == 'sentico-v14-recuperado'
    vals = obj['volumes']
    expected = {
        'v14_pgdata': ('SENTICO_PGDATA_VOLUME', 'sentico-v14-recuperado_pgdata'),
        'v14_uploads': ('SENTICO_UPLOADS_VOLUME', 'sentico-v14-recuperado_uploads'),
        'v14_node_modules': ('SENTICO_NODE_VOLUME', 'sentico-v14-recuperado_node_modules'),
    }
    for key, (env, default) in expected.items():
        assert vals[key]['external'] is True
        assert vals[key]['name'] == '${' + env + ':-' + default + '}'
    assert '${SENTICO_DB_ROLE:-sentico_green}' in obj['services']['db']['environment']['POSTGRES_USER']
    assert '${SENTICO_DB_ROLE:-sentico_green}' in obj['services']['api']['environment']['DATABASE_URL']
    assert obj['services']['api']['environment']['SENTICO_DB_ROLE'] == '${SENTICO_DB_ROLE:-sentico_green}'


def test_preservacao_e_identificacao_por_dados():
    ps = INSTALL.read_text()
    for forbid in ('docker volume rm', "Compose @('down'", "Docker @('volume','rm'", "Docker @('volume','prune'", "Compose @('down','-v'"):
        assert forbid not in ps
    assert 'VolumeDoProjeto' in ps
    assert 'AcharOrigemIsoladaCompativel' in ps
    assert 'ClonarOrigemCompativel' in ps
    assert 'BackupCompativel' in ps
    assert 'DetectarRoleOffline' in ps
    assert 'SENTICO_DB_ROLE' in ps
    assert 'SENTICO_PGDATA_VOLUME' in ps
    assert 'SENTICO_UPLOADS_VOLUME' in ps
    assert 'SENTICO_NODE_VOLUME' in ps
    assert ps.index('EscreverEnv $Senha $BancoPreferido') < ps.index("Compose @('up','-d','--no-build','db')")
    assert ps.index("$write=TestarEscritaApi") < ps.index("Compose @('exec','-T','api','alembic','upgrade','head')")


def test_catalogo_somente_schema_e_versoes_nao_nomes():
    content = (SCRIPTS/'catalogar_bancos_existentes.sh').read_text()
    assert 'datallowconn AND NOT datistemplate' in content
    assert "c.relname IN ('users','laboratory_customers','laboratory_work_orders','purchase_orders','alembic_version')" in content
    assert 'sentico_green_preview' not in content
    assert '-U "$role"' in content
    assert 'CANDIDATO|' in content
    assert 'CREATE TABLE' not in content


def test_scripts_shell_e_python_sintaxe():
    for sh in SCRIPTS.glob('*.sh'):
        p = subprocess.run(['sh','-n',str(sh)], capture_output=True, text=True)
        assert p.returncode == 0, (sh, p.stderr)
    p = ROOT/'apps/api/scripts/verificar_escrita_recuperacao.py'
    ast.parse(p.read_text())


def test_recuperar_role_e_ssl_sem_credenciais_em_logs():
    role=(SCRIPTS/'identificar_role_offline.sh').read_text()
    assert 'rolcanlogin AND rolsuper' in role
    assert 'ROLE_IDENTIFICADA=' in role
    reset=(SCRIPTS/'configurar_senha_offline.sh').read_text()
    assert 'SENTICO_DB_ROLE' in reset
    assert 'postgres --single' in reset
    tcp=(SCRIPTS/'verificar_tcp_copia.sh').read_text()
    assert 'POSTGRES_USER' in tcp
    assert 'ERRO_TCP_ROLE_AUSENTE' in tcp
    import_file=(SCRIPTS/'importar_pgdata_fixo.sh').read_text()
    assert 'ERRO_VOLUME_NAO_VAZIO' in import_file
    assert 'ERRO_BACKUP_CAMINHO_INSEGURO' in import_file
    clone=(SCRIPTS/'clonar_pgdata_compat.sh').read_text()
    assert '[ -z "$(ls -A /dados)" ]' in clone
    assert '/orig/postmaster.pid' in clone


def test_migration_corrente_existe():
    versions={}
    path=ROOT/'apps/api/migrations/versions'
    for f in path.glob('*.py'):
        tree=ast.parse(f.read_text())
        vals={}
        for x in tree.body:
            if isinstance(x,(ast.Assign,ast.AnnAssign)):
                targets=x.targets if isinstance(x,ast.Assign) else [x.target]
                for t in targets:
                    if isinstance(t,ast.Name) and t.id in ('revision','down_revision'):
                        try: vals[t.id]=ast.literal_eval(x.value)
                        except (ValueError, TypeError): pass
        if vals.get('revision'): versions[vals['revision']]=vals.get('down_revision')
    v='20261116_01'; seen={v}
    while v!='20261013_02':
        v=versions[v]
        assert v not in seen
        seen.add(v)
    assert len(seen)==14


def test_catalogo_reconhece_role_e_banco_com_nomes_diferentes(tmp_path):
    """Simula respostas psql reais em stdout, sem autenticar no DB verdadeiro."""
    mock = tmp_path/'psql'
    mock.write_text('''#!/usr/bin/env python3
import sys
args=sys.argv
query=args[args.index('-c')+1]
db=args[args.index('-d')+1]
if db=='postgres':
 print('erp_empresa\\nsentico_green\\nbanco_outro')
elif 'pg_class' in query:
 print('5' if db!='banco_outro' else '0')
elif 'version_num' in query:
 print('20261028_01' if db=='erp_empresa' else '20261013_02')
elif 'count(*)' in query:
 print('15|320|1090|12' if db=='erp_empresa' else '12|292|1045|8')
else:
 sys.exit(5)
''')
    mock.chmod(0o755)
    import os
    env={**os.environ, 'PATH':str(tmp_path)+':'+os.environ['PATH'],
         'POSTGRES_PASSWORD':'__FAKE_TEST__', 'POSTGRES_USER':'empresa_erp'}
    p = subprocess.run(['sh', str(SCRIPTS/'catalogar_bancos_existentes.sh')],
                       text=True, capture_output=True, env=env)
    assert p.returncode == 0, p.stderr
    assert 'CANDIDATO|erp_empresa|20261028_01|15|320|1090|12' in p.stdout
    assert 'CANDIDATO|sentico_green|20261013_02|12|292|1045|8' in p.stdout
    assert 'BANCO_DESCARTADO_ESTRUTURA=banco_outro' in p.stdout


def test_catalogo_rejeita_role_malformada(tmp_path):
    import os
    env={**os.environ, 'POSTGRES_PASSWORD':'__FAKE_TEST__',
         'POSTGRES_USER':'abc;drop_table'}
    p = subprocess.run(['sh', str(SCRIPTS/'catalogar_bancos_existentes.sh')],
                       text=True, capture_output=True, env=env)
    assert p.returncode == 31
    assert 'ERRO_CATALOGO_ROLE_INVALIDA' in p.stdout
