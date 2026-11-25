"""Checagens de integração dos campos de cliente no formulário e detalhe da OS."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps/web/src/features/laboratory"


def test_ambos_os_usam_componente_compartilhado():
    content = (SRC / "LaboratoryDashboard.tsx").read_text(encoding="utf-8")
    assert content.count("<CustomerSearchSelect ") == 2
    assert 'required customers={customers} companyCode={form.company_code}' in content
    assert 'customers={customers} companyCode={detail.company_code}' in content
    assert "customer_id: String(customer.id), customer_name: customer.legal_name" in content
    assert "Cliente<select" not in content


def test_carrega_clientes_independente_do_filtro_geral():
    content = (SRC / "LaboratoryDashboard.tsx").read_text(encoding="utf-8")
    assert 'apiClient.get<Customer[]>("/laboratory/customers?include_inactive=true")' in content
    assert 'customer_id: form.customer_id ? Number(form.customer_id) : null' in content


def test_acessibilidade_e_selecao_explicita():
    content = (SRC / "components/CustomerSearchSelect.tsx").read_text(encoding="utf-8")
    assert 'role="combobox"' in content
    assert 'role="listbox"' in content
    assert 'role="option"' in content
    assert 'event.key === "ArrowDown"' in content
    assert 'event.key === "Enter"' in content
    assert 'onChange(customer)' in content
    assert '"Escolha um cliente da lista de sugestões."' in content


def test_pesquisa_com_nome_fantasia_e_documento():
    content = (SRC / "components/customerSearch.ts").read_text(encoding="utf-8")
    assert 'customer.trade_name?.trim() || customer.legal_name' in content
    assert 'document.includes(digits)' in content
    assert 'normalize("NFD")' in content
    assert 'customer.is_active || customer.id === currentId' in content
