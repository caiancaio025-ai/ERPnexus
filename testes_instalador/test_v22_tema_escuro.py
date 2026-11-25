"""V22: aparência escura equivalente à clara, sem alterações de domínio."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web/src"
DARK = WEB / "shared/theme/dark-elevated.css"


def test_tema_escuro_importado_depois_dos_anteriores():
    source = (WEB / "main.tsx").read_text(encoding="utf-8")
    assert source.index('light-theme.css') < source.index('light-semantic-colors.css') < source.index('dark-elevated.css')


def test_folha_exclusiva_ao_tema_escuro():
    import tinycss2
    css = DARK.read_text(encoding="utf-8")
    assert 'html[data-sentico-theme="claro"]' not in css
    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    def check(css_rules):
        for rule in css_rules:
            assert rule.type != "error", getattr(rule, "message", "CSS inválido")
            if rule.type == "at-rule":
                if rule.content is not None:
                    check(tinycss2.parse_rule_list(rule.content, skip_comments=True, skip_whitespace=True))
                continue
            if rule.type == "qualified-rule":
                selector = tinycss2.serialize(rule.prelude).strip()
                # Toda regra deve começar com o escopo escuro. Nenhum seletor
                # agrupado pode ficar solto após uma vírgula.
                groups, depth, last = [], 0, 0
                for i, char in enumerate(selector):
                    if char == "(": depth += 1
                    elif char == ")": depth -= 1
                    elif char == "," and depth == 0:
                        groups.append(selector[last:i].strip())
                        last = i + 1
                groups.append(selector[last:].strip())
                for group in groups:
                    assert group.startswith('html[data-sentico-theme="escuro"]'), group
                for decl in tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True):
                    assert decl.type != "error", getattr(decl, "message", "Valor CSS inválido")
    check(rules)


def test_paleta_semantica_status_notificacoes_e_filtragem():
    css = DARK.read_text(encoding="utf-8")
    for code in ("no_repair", "approved", "awaiting_parts", "in_analysis", "warranty", "overdue"):
        assert f".{code}" in css
    for sector in ("laboratorio", "orcamentos", "compras", "estoque", "financeiro", "comercial", "colaboradores", "configuracoes"):
        assert f'data-modulo="{sector}"' in css
    for selector in (".work-queue--danger", ".event-filters button.active", ".sentico-notifications__item.is-unread", ".employees-shell", ".finance-kpi"):
        assert selector in css


def test_botao_preenchido_e_foco_legiveis():
    css = DARK.read_text(encoding="utf-8")
    assert "color: #fff !important" in css
    assert "button.active,button.is-active" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css


def test_nenhuma_migracao_de_banco_nova():
    expected = ROOT / "apps/api/migrations/versions"
    assert not list(expected.glob("*20261117_02*"))
