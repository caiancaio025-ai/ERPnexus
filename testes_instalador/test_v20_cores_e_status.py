"""V20: garantias estáticas sem modificar bancos existentes."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web/src"
CSS = WEB / "shared/theme/light-semantic-colors.css"


def test_cores_importadas_apos_tema_v19():
    source = (WEB / "main.tsx").read_text(encoding="utf8")
    assert source.index('light-theme.css') < source.index('light-semantic-colors.css')


def test_paleta_semantica_isolada_ao_claro():
    css = CSS.read_text(encoding="utf8")
    assert 'html[data-sentico-theme="escuro"]' not in css
    assert len(re.findall(r'html\[data-sentico-theme="claro"\]', css)) >= 20
    assert "--sentico-red-bg:" in css and "--sentico-green-bg:" in css
    assert "--sentico-amber-bg:" in css and "--sentico-blue-bg:" in css


def test_sem_conserto_volta_a_cor_vermelha():
    css = CSS.read_text(encoding="utf8")
    for selector in ('.lab-status,.com-tag).no_repair', 'customers-status-no_repair', '--sentico-red-text'):
        assert selector in css
    assert "background: var(--sentico-red-bg) !important;" in css


def test_status_reconhecidos_continuam_por_codigo():
    css = CSS.read_text(encoding="utf8")
    for selector in ['.approved', '.completed', '.awaiting_parts', '.in_analysis', '.in_repair', '.warranty', '.rejected']:
        assert selector in css
    assert "data-modulo" in (WEB / "features/notifications/NotificationCenter.tsx").read_text(encoding="utf8")


def test_nenhuma_alteracao_de_estado_persistido():
    source = (WEB / "features/laboratory/LaboratoryDashboard.tsx").read_text(encoding="utf8")
    backend = (ROOT / "apps/api/app/laboratory/status_flow.py").read_text(encoding="utf8")
    assert 'value: "in_analysis", label: "Analisado"' in source
    assert '"in_analysis"' in backend
    assert 'textoEmPortugues(workflowOptions.find' in source


def test_avisos_anteriores_podem_exibir_texto_corrigido():
    source = (WEB / "shared/i18n/portugues.ts").read_text(encoding="utf8")
    assert 'in_analysis: "Analisado"' in source
    assert r'\bEm\s+[Aa]nálise\b' in source
    for file in ["apps/api/app/laboratory/quote_pdf.py", "apps/api/app/tracking/router.py", "apps/api/app/laboratory/router.py"]:
        assert '"in_analysis": "Analisado"' in (ROOT / file).read_text(encoding="utf8")


def test_cores_de_modulos_na_central_e_painel():
    css = CSS.read_text(encoding="utf8")
    for modulo in ["laboratorio", "orcamentos", "compras", "estoque", "financeiro", "comercial", "colaboradores", "configuracoes"]:
        assert f'data-modulo="{modulo}"' in css
    dash = (WEB / "features/dashboard/Dashboard.tsx").read_text(encoding="utf8")
    assert dash.count('data-modulo={item.activity_module}') == 2
