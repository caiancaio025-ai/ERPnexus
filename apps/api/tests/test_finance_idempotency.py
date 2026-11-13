from app.finance.idempotency import fingerprint_mapping


def test_fingerprint_is_stable_for_same_payload_with_different_key_order():
    first = {"company_code": "universo_eletronica", "nfse_number": "100", "amount": "500.00", "due_date": "2026-09-10"}
    second = {"due_date": "2026-09-10", "amount": "500.00", "nfse_number": "100", "company_code": "universo_eletronica"}
    assert fingerprint_mapping(first) == fingerprint_mapping(second)


def test_fingerprint_changes_when_installment_due_date_changes():
    first = {"nfse_number": "100", "amount": "500.00", "due_date": "2026-09-10"}
    second = {"nfse_number": "100", "amount": "500.00", "due_date": "2026-10-10"}
    assert fingerprint_mapping(first) != fingerprint_mapping(second)


def test_fingerprint_changes_when_amount_changes():
    first = {"nfse_number": "100", "amount": "500.00", "due_date": "2026-09-10"}
    second = {"nfse_number": "100", "amount": "250.00", "due_date": "2026-09-10"}
    assert fingerprint_mapping(first) != fingerprint_mapping(second)
