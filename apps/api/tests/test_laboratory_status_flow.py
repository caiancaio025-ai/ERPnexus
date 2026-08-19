from app.laboratory.service import can_transition_status


def test_received_can_move_to_analysis() -> None:
    assert can_transition_status("received", "in_analysis") is True


def test_received_cannot_jump_to_delivered() -> None:
    assert can_transition_status("received", "delivered") is False


def test_terminal_status_cannot_reopen() -> None:
    assert can_transition_status("delivered", "in_repair") is False


def test_same_status_is_allowed() -> None:
    assert can_transition_status("in_analysis", "in_analysis") is True


def test_unknown_status_cannot_transition() -> None:
    assert can_transition_status("unknown", "in_analysis") is False
