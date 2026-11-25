"""V47 — contratos da fixação de cabeçalhos sem alterar dados ou mobile."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "apps/web/src/shared/ui/sticky-tables.css"
MAIN = ROOT / "apps/web/src/main.tsx"


def test_estilo_importado_pelo_frontend():
    assert CSS.exists()
    assert 'import "./shared/ui/sticky-tables.css";' in MAIN.read_text()


def test_tabelas_operacionais_com_rolagem_e_cabecalho_fixo():
    source = CSS.read_text()
    for wrapper in (
        ".lab-table-card", ".com-table-wrap", ".com-items-wrap",
        ".employees-table-wrap", ".purchase-report-table-wrap",
        ".orders-table", ".finance-monthly-table",
        ".documents-table", ".relation-table",
    ):
        assert wrapper in source
    assert "max-height: min(70dvh, 760px);" in source
    assert "position: sticky;" in source
    assert "top: 0;" in source
    assert "background-color: #112a3e;" in source
    assert 'html[data-sentico-theme="claro"]' in source


def test_responsividade_e_impressao_preservadas():
    source = CSS.read_text()
    assert "@media screen and (max-width: 760px)" in source
    assert ".lab-work-orders-table {" in source
    assert "max-height: none;" in source
    assert "overflow: visible;" in source
    assert "@media print" in source
    assert "position: static !important;" in source
