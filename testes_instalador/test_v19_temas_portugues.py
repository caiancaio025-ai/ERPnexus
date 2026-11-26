"""Contratos estáticos da atualização visual V19 (não acessam banco/volumes)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'apps/web/src'


def test_seletor_de_tema_globais():
    tema = (WEB / 'shared/theme/theme.ts').read_text(encoding='utf-8')
    assert 'sentico:preferencia-tema:v1' in tema
    assert 'data-sentico-theme' in tema
    assert 'storage' in tema
    assert 'escuro' in tema and 'claro' in tema
    assert 'iniciarTema();' in (WEB / 'main.tsx').read_text(encoding='utf-8')


def test_controle_tema_no_cabecalho_compartilhado():
    menu = (WEB / 'shared/ui/SenticoSidebar.tsx').read_text(encoding='utf-8')
    header = (WEB / 'shared/ui/SenticoHeaderActions.tsx').read_text(encoding='utf-8')
    appearance = (WEB / 'shared/theme/AppearanceMenu.tsx').read_text(encoding='utf-8')
    assert '<ThemeSwitcher' not in menu
    assert '<AppearanceMenu' in header
    assert '<ThemeSwitcher' in appearance
    assert 'Tema claro' in (WEB / 'shared/theme/ThemeSwitcher.tsx').read_text(encoding='utf-8')
    assert 'Tema escuro' in (WEB / 'shared/theme/ThemeSwitcher.tsx').read_text(encoding='utf-8')


def test_traducoes_da_garantia_e_os_duplicada():
    i18n = (WEB / 'shared/i18n/portugues.ts').read_text(encoding='utf-8')
    assert 'warranty: "Garantia"' in i18n
    assert r'OS\s+OS' in i18n
    labor = (ROOT / 'apps/api/app/laboratory/router.py').read_text(encoding='utf-8')
    assert '"warranty": "Garantia"' in labor
    assert 'previous_label = status_labels.get(previous' in labor


def test_central_lida_com_filtros_e_dados():
    ui = (WEB / 'features/notifications/NotificationCenter.tsx').read_text(encoding='utf-8')
    assert 'Mais filtros' in ui and 'Não lidas' in ui and 'somenteHoje' in ui
    for coluna in ['actor_name', 'work_order_number', 'equipment_name', 'activity_module']:
        assert coluna in ui
    assert 'textoEmPortugues(item.title)' in ui
    assert 'textoEmPortugues(item.message)' in ui


def test_tema_claro_isolado_e_sem_inversao_de_imagens():
    css = (WEB / 'shared/theme/light-theme.css').read_text(encoding='utf-8')
    assert len(re.findall(r'html\[data-sentico-theme="claro"\]', css)) > 700
    assert 'filter: invert(' not in css
    assert 'color-scheme: light' in css
