from pathlib import Path


API_ROOT = Path(__file__).parents[1]
WEB_ROOT = API_ROOT.parent / "web"


def test_frontend_allows_shared_and_individual_fields_but_protects_company() -> None:
    source = (
        WEB_ROOT / "src" / "features" / "finance" / "FinanceDashboard.tsx"
    ).read_text(encoding="utf-8")

    assert 'disabled={Boolean(selected?.obligation_id)} value={form.company_code}' in source
    assert 'disabled={Boolean(selected?.obligation_id)} required value={form.counterparty_name}' not in source
    assert 'disabled={Boolean(selected?.obligation_id)} required value={form.description}' not in source
    assert '<label>NFS-e<input disabled={Boolean(selected?.obligation_id)}' not in source
    assert '<label>Data de emissão<input disabled={Boolean(selected?.obligation_id)}' not in source
    assert '{!selected.obligation_id && <button className="delete"' in source
    assert "Salvar alterações" in source


def test_backend_updates_parent_siblings_and_total_atomically() -> None:
    source = (API_ROOT / "app" / "finance" / "router.py").read_text(encoding="utf-8")

    assert "async def _update_grouped_installment(" in source
    assert "GROUPED_INSTALLMENT_SHARED_FIELDS" in source
    assert "for sibling in siblings:" in source
    assert "obligation.total_amount = total_from_installments(siblings)" in source
    assert "await _assert_period_open(db, entry.company_code, payload.posting_date)" in source
    assert "_block_grouped_entry_delete(entry)" in source
