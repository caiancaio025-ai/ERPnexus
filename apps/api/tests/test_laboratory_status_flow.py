from app.laboratory.service import can_transition_status


def test_status_is_free_between_valid_main_statuses() -> None:
    assert can_transition_status("received", "in_analysis") is True
    assert can_transition_status("received", "invoiced") is True
    assert can_transition_status("in_testing", "received") is True
    assert can_transition_status("cancelled", "approved") is True
    assert can_transition_status("invoiced", "received") is True


def test_historical_status_codes_remain_valid_main_status_targets() -> None:
    assert can_transition_status("received", "quote_sent") is True
    assert can_transition_status("received", "completed") is True
    assert can_transition_status("received", "delivered") is True


def test_same_status_is_allowed() -> None:
    assert can_transition_status("in_analysis", "in_analysis") is True


def test_unknown_status_cannot_transition() -> None:
    assert can_transition_status("unknown", "in_analysis") is False
    assert can_transition_status("in_analysis", "unknown") is False
