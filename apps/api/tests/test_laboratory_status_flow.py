from app.laboratory.service import can_transition_status


def test_received_can_move_to_analysis() -> None:
    assert can_transition_status("received", "in_analysis") is True


def test_received_can_jump_to_any_active_builtin_status_without_hierarchy() -> None:
    assert can_transition_status("received", "invoiced") is True
    assert can_transition_status("in_testing", "received") is True
    assert can_transition_status("cancelled", "approved") is True


def test_legacy_substatus_codes_cannot_be_used_as_main_status_targets() -> None:
    assert can_transition_status("received", "quote_sent") is False
    assert can_transition_status("received", "completed") is False
    assert can_transition_status("received", "delivered") is False


def test_same_status_is_allowed() -> None:
    assert can_transition_status("in_analysis", "in_analysis") is True


def test_unknown_status_cannot_transition() -> None:
    assert can_transition_status("unknown", "in_analysis") is False
    assert can_transition_status("in_analysis", "unknown") is False
