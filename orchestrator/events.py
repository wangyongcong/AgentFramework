from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from .schemas import HistoryEvent, Task, utc_now


def append_history(
    task: Task,
    action: str,
    reasoning: str,
    status_change: str,
    agent_id: str,
    role: str,
    tool: str,
    artifacts: list[str] | None = None,
) -> None:
    event = HistoryEvent(
        timestamp=utc_now(),
        event_id=str(uuid4()),
        agent={"id": agent_id, "role": role, "tool": tool},
        action=action,
        reasoning=reasoning,
        artifacts=artifacts or [],
        status_change=status_change,
        event_seq=len(task.history) + 1,
    )
    task.history.append(event)
    task.updated_at = utc_now()


def emit_signal(task: Task, signal_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    signal = {
        "seq": len(task.signals) + 1,
        "timestamp": utc_now(),
        "type": signal_type,
        "payload": payload or {},
    }
    task.signals.append(signal)
    task.updated_at = utc_now()
    return signal


def history_as_dict(task: Task) -> list[dict[str, Any]]:
    return [asdict(entry) for entry in task.history]

