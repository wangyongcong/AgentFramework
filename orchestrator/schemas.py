from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


STATUSES = {
    "READY_FOR_WORK",
    "IN_PROGRESS",
    "WAITING_FOR_QA",
    "UNDER_TEST",
    "FAILED_QA",
    "COMPLETED",
    "TERMINAL_FAILED",
    "MANUAL_TAKEOVER",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Assignment:
    agent_id: str | None = None
    role: str | None = None
    started_at: str | None = None


@dataclass
class QaReport:
    passed: bool | None = None
    summary: str = ""
    logs: str = ""


@dataclass
class LatestOutput:
    content: str = ""
    qa_report: QaReport = field(default_factory=QaReport)


@dataclass
class HistoryEvent:
    timestamp: str
    event_id: str
    agent: dict[str, str]
    action: str
    reasoning: str
    artifacts: list[str]
    status_change: str
    event_seq: int


@dataclass
class Task:
    task_id: str
    status: str
    metadata: dict[str, Any]
    dev_spec: str
    current_assignment: Assignment = field(default_factory=Assignment)
    latest_output: LatestOutput = field(default_factory=LatestOutput)
    history: list[HistoryEvent] = field(default_factory=list)
    attempt_count: int = 0
    submission_version: int = 0
    artifact_hash: str = ""
    terminal_reason: str | None = None
    manual_owner: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    idempotency_keys: list[str] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["history"] = [asdict(h) for h in self.history]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        assignment = Assignment(**data.get("current_assignment", {}))
        qa_raw = data.get("latest_output", {}).get("qa_report", {})
        latest_output = LatestOutput(
            content=data.get("latest_output", {}).get("content", ""),
            qa_report=QaReport(**qa_raw),
        )
        history = [HistoryEvent(**h) for h in data.get("history", [])]
        return cls(
            task_id=data["task_id"],
            status=data["status"],
            metadata=data.get("metadata", {}),
            dev_spec=data.get("dev_spec", ""),
            current_assignment=assignment,
            latest_output=latest_output,
            history=history,
            attempt_count=data.get("attempt_count", 0),
            submission_version=data.get("submission_version", 0),
            artifact_hash=data.get("artifact_hash", ""),
            terminal_reason=data.get("terminal_reason"),
            manual_owner=data.get("manual_owner"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
            completed_at=data.get("completed_at"),
            idempotency_keys=data.get("idempotency_keys", []),
            signals=data.get("signals", []),
        )


def new_task(metadata: dict[str, Any], dev_spec: str, task_id: str | None = None) -> Task:
    return Task(
        task_id=task_id or str(uuid4()),
        status="READY_FOR_WORK",
        metadata=metadata,
        dev_spec=dev_spec,
    )

