from orchestrator.state_machine import can_transition


def test_valid_transitions():
    assert can_transition("READY_FOR_WORK", "IN_PROGRESS")
    assert can_transition("IN_PROGRESS", "WAITING_FOR_QA")
    assert can_transition("UNDER_TEST", "COMPLETED")
    assert can_transition("UNDER_TEST", "FAILED_QA")
    assert can_transition("UNDER_TEST", "TERMINAL_FAILED")


def test_invalid_transitions():
    assert not can_transition("READY_FOR_WORK", "COMPLETED")
    assert not can_transition("WAITING_FOR_QA", "COMPLETED")
    assert not can_transition("COMPLETED", "IN_PROGRESS")

