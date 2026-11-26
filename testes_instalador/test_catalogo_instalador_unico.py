"""Testes de contrato não destrutivos da entrega Windows unificada."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'scripts_recuperacao' / 'catalogar_bancos_existentes.sh'

# Mock de psql para simular consultas READ-ONLY sem PostgreSQL nem credenciais reais.
MOCK = '''#!/bin/sh
case "$*" in
  *"FROM pg_database"*)
    [ "${SCENARIO:-}" = connfail ] && exit 1
    case "${SCENARIO:-}" in
      defaultdb) printf 'postgres\\n' ;;
      empty) printf 'postgres\\n' ;;
      *) printf 'sentico_green\\npostgres\\n' ;;
    esac
    ;;
  *"FROM pg_class"*)
    case "${SCENARIO:-}" in
      empty) echo 0 ;;
      defaultdb) echo 5 ;;
      *) case "$*" in *"-d sentico_green"*) echo 5 ;; *) echo 0 ;; esac ;;
    esac
    ;;
  *"version_num"*)
    case "${SCENARIO:-}" in
      badrevision) echo 20991231_01 ;;
      latestrevision) echo 20261126_01 ;;
      *) echo 20261028_01 ;;
    esac
    ;;
  *"SELECT (SELECT count"*)
    case "${SCENARIO:-}" in
      zerousers) echo '0|0|0|0' ;;
      noorders) echo '12|292|0|8' ;;
      *) echo '12|292|1045|8' ;;
    esac
    ;;
  *) exit 99 ;;
esac
'''

class CatalogoTests(unittest.TestCase):
    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / 'psql'
            fake.write_text(MOCK)
            fake.chmod(0o700)
            env = {**os.environ, 'PATH': f'{temp}:{os.environ["PATH"]}',
                   'POSTGRES_USER': 'erp_administrador', 'POSTGRES_PASSWORD': 'test-secret',
                   'SCENARIO': scenario}
            return subprocess.run(['sh', str(CATALOG)], capture_output=True, text=True, env=env)

    def test_os_zero_is_a_compatible_erp(self):
        r = self.run_scenario('noorders')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('CANDIDATO|sentico_green|20261028_01|12|292|0|8', r.stdout)

    def test_postgres_default_database_can_contain_erp(self):
        r = self.run_scenario('defaultdb')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('CANDIDATO|postgres|20261028_01', r.stdout)

    def test_zero_users_remains_a_candidate_but_warns(self):
        r = self.run_scenario('zerousers')
        self.assertEqual(r.returncode, 0)
        self.assertIn('BANCO_SEM_USUARIOS=sentico_green', r.stdout)

    def test_empty_postgres_does_not_get_accepted(self):
        r = self.run_scenario('empty')
        self.assertEqual(r.returncode, 35)
        self.assertIn('BANCO_DESCARTADO_ESTRUTURA=postgres', r.stdout)
        self.assertIn('ERRO_CATALOGO_NENHUM_BANCO_COMPATIVEL', r.stdout)

    def test_unknown_alembic_revision_stops_safely(self):
        r = self.run_scenario('badrevision')
        self.assertEqual(r.returncode, 35)
        self.assertIn('BANCO_DESCARTADO_REVISAO=sentico_green', r.stdout)

    def test_individual_receipt_revision_remains_compatible_on_repeat_install(self):
        r = self.run_scenario('latestrevision')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('CANDIDATO|sentico_green|20261126_01|12|292|1045|8', r.stdout)

    def test_tcp_connection_failure_is_explained(self):
        r = self.run_scenario('connfail')
        self.assertEqual(r.returncode, 34)
        self.assertIn('ERRO_CATALOGO_CONEXAO_TCP', r.stdout)

    def test_only_one_launcher_and_one_engine(self):
        self.assertEqual(sorted(p.name for p in ROOT.glob('INICIAR_*.cmd')), ['INICIAR_SENTICO.cmd', 'INICIAR_TESTE_V48.cmd'])
        self.assertEqual(sorted(p.name for p in ROOT.glob('INSTALAR_*.ps1')), ['INSTALAR_SENTICO.ps1'])
        launcher = (ROOT/'INICIAR_SENTICO.cmd').read_text(encoding='utf-8')
        self.assertIn('INSTALAR_SENTICO.ps1', launcher)
        local_test = (ROOT/'INICIAR_TESTE_V48.cmd').read_text(encoding='utf-8')
        self.assertIn('TESTE_LOCAL_V48.ps1', local_test)
        self.assertNotIn('INSTALAR_SENTICO.ps1', local_test)

    def test_docker_project_and_volumes_unchanged(self):
        content = (ROOT/'INSTALAR_SENTICO.ps1').read_text(encoding='utf-8-sig')
        for literal in ('sentico-v14-recuperado','sentico-v14-recuperado_pgdata',
                        'sentico-v14-recuperado_uploads','sentico-v14-recuperado_node_modules',
                        'Sentico\\RecuperacaoV14'):
            self.assertIn(literal, content)
        self.assertNotIn("Docker @('volume','rm'", content)
        self.assertNotIn("Compose @('down','-v'", content)

if __name__ == '__main__':
    unittest.main()
