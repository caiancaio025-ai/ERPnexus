"""Regressão dos cartões monetários no cabeçalho do Laboratório (V39)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "web" / "src" / "features" / "laboratory"


def test_totais_monetarios_tem_classe_especifica():
    dashboard = (ROOT / "LaboratoryDashboard.tsx").read_text(encoding="utf-8")
    assert dashboard.count('className="lab-kpi-money"') == 2
    assert "Total aprovado" in dashboard
    assert "Aguardando aprovação" in dashboard


def test_totais_reservam_espaco_e_nao_quebram_linha():
    stylesheet = (ROOT / "laboratory.css").read_text(encoding="utf-8")
    v39 = stylesheet.split("/* V39 — valores monetários", 1)[1]
    assert "grid-column: span 2" in v39
    assert "white-space: nowrap" in v39
    assert "word-break: keep-all" in v39
    assert "overflow-x: auto" in v39
    assert "@media (max-width: 480px)" in v39
