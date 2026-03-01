from __future__ import annotations


TRANSITIONS = {
    "READY_FOR_WORK": {"IN_PROGRESS"},
    "IN_PROGRESS": {"WAITING_FOR_QA", "MANUAL_TAKEOVER"},
    "WAITING_FOR_QA": {"UNDER_TEST", "MANUAL_TAKEOVER"},
    "UNDER_TEST": {"COMPLETED", "FAILED_QA", "TERMINAL_FAILED"},
    "FAILED_QA": {"IN_PROGRESS", "MANUAL_TAKEOVER"},
    "TERMINAL_FAILED": {"MANUAL_TAKEOVER"},
    "MANUAL_TAKEOVER": {"IN_PROGRESS", "COMPLETED", "TERMINAL_FAILED"},
    "COMPLETED": set(),
}


def can_transition(current: str, nxt: str) -> bool:
    return nxt in TRANSITIONS.get(current, set())


def assert_transition(current: str, nxt: str) -> None:
    if not can_transition(current, nxt):
        raise ValueError(f"invalid transition: {current} -> {nxt}")

