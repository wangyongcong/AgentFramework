from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from .events import append_history, emit_signal
from .schemas import Task, new_task, utc_now
from .state_machine import assert_transition
from .state_store import TaskStore


class Broker:
    def __init__(self, root: str | Path = ".", max_failures: int = 3) -> None:
        self.store = TaskStore(root)
        self.max_failures = max_failures

    def create_task(self, metadata: dict[str, Any], dev_spec: str, task_id: str | None = None) -> dict[str, Any]:
        task = new_task(metadata, dev_spec, task_id=task_id)
        append_history(
            task=task,
            action="TASK_CREATED",
            reasoning="Manager created task from technical specification.",
            status_change="TO_READY_FOR_WORK",
            agent_id="manager",
            role="manager",
            tool=metadata.get("tool_preference", "manual"),
        )
        emit_signal(task, "TASK_READY", {"task_id": task.task_id})
        with self.store.task_lock(task.task_id):
            self.store.save_task(task)
        return {"task_id": task.task_id, "status": task.status}

    def claim_task(self, agent_id: str, role: str, tool: str, task_id: str | None = None) -> dict[str, Any]:
        if task_id:
            candidate_ids = [task_id]
        else:
            candidate_ids = self.store.list_tasks()
        for tid in sorted(candidate_ids):
            with self.store.task_lock(tid):
                task = self.store.load_task(tid)
                if role == "worker" and task.status in {"READY_FOR_WORK", "FAILED_QA"}:
                    self._assign(task, agent_id, role, tool)
                    self.store.save_task(task)
                    return {"ok": True, "task": task.to_dict()}
                if role == "qa" and task.status == "WAITING_FOR_QA":
                    self._assign(task, agent_id, role, tool)
                    self._transition(task, "UNDER_TEST")
                    emit_signal(task, "QA_STARTED", {"task_id": task.task_id})
                    self.store.save_task(task)
                    return {"ok": True, "task": task.to_dict()}
        return {"ok": False, "error": "no claimable task"}

    def submit_worker_output(
        self,
        task_id: str,
        agent_id: str,
        content: str,
        artifacts: list[str],
        reasoning: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        with self.store.task_lock(task_id):
            task = self.store.load_task(task_id)
            self._ensure_assigned(task, agent_id, "worker")
            self._idempotent_check(task, idempotency_key)

            if task.status not in {"IN_PROGRESS", "FAILED_QA"}:
                raise ValueError(f"worker submit invalid in state {task.status}")

            task.submission_version += 1
            task.latest_output.content = content
            task.latest_output.qa_report.passed = None
            task.latest_output.qa_report.summary = ""
            task.latest_output.qa_report.logs = ""
            task.artifact_hash = _hash_payload(content, artifacts, task.submission_version)
            self._transition(task, "WAITING_FOR_QA")

            append_history(
                task=task,
                action="CODE_SUBMITTED",
                reasoning=reasoning,
                status_change="TO_WAITING_FOR_QA",
                agent_id=agent_id,
                role="worker",
                tool=task.metadata.get("tool_preference", "codex-cli"),
                artifacts=artifacts,
            )
            emit_signal(
                task,
                "WORKER_SUBMITTED",
                {"task_id": task_id, "submission_version": task.submission_version},
            )
            self.store.save_task(task)
            return {"ok": True, "status": task.status, "submission_version": task.submission_version}

    def submit_qa_report(
        self,
        task_id: str,
        agent_id: str,
        passed: bool,
        summary: str,
        logs: str,
        tested_submission_version: int,
        artifacts: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        with self.store.task_lock(task_id):
            task = self.store.load_task(task_id)
            self._ensure_assigned(task, agent_id, "qa")
            self._idempotent_check(task, idempotency_key)

            if task.status != "UNDER_TEST":
                raise ValueError(f"qa submit invalid in state {task.status}")
            if tested_submission_version != task.submission_version:
                raise ValueError("stale qa report; submission_version mismatch")

            task.latest_output.qa_report.passed = passed
            task.latest_output.qa_report.summary = summary
            task.latest_output.qa_report.logs = logs

            if passed:
                self._transition(task, "COMPLETED")
                task.completed_at = utc_now()
                append_history(
                    task=task,
                    action="QA_PASSED",
                    reasoning=summary or "QA checks passed.",
                    status_change="TO_COMPLETED",
                    agent_id=agent_id,
                    role="qa",
                    tool="qa-agent",
                    artifacts=artifacts or [],
                )
                emit_signal(task, "QA_PASSED", {"task_id": task.task_id})
            else:
                task.attempt_count += 1
                append_history(
                    task=task,
                    action="QA_FAILED",
                    reasoning=summary or "QA checks failed.",
                    status_change="TO_FAILED_QA",
                    agent_id=agent_id,
                    role="qa",
                    tool="qa-agent",
                    artifacts=artifacts or [],
                )
                if task.attempt_count >= self.max_failures:
                    self._transition(task, "TERMINAL_FAILED")
                    task.terminal_reason = f"Reached max QA failures ({self.max_failures})."
                    emit_signal(
                        task,
                        "TERMINAL_FAILED",
                        {"task_id": task.task_id, "attempt_count": task.attempt_count},
                    )
                    self._transition(task, "MANUAL_TAKEOVER")
                    emit_signal(task, "MANUAL_TAKEOVER_REQUIRED", {"task_id": task.task_id})
                else:
                    self._transition(task, "FAILED_QA")
                    emit_signal(
                        task,
                        "QA_FAILED",
                        {
                            "task_id": task.task_id,
                            "attempt_count": task.attempt_count,
                            "summary": summary,
                        },
                    )
                    self._transition(task, "IN_PROGRESS")
                    worker_agent_id = task.metadata.get("worker_agent_id")
                    if worker_agent_id:
                        task.current_assignment.agent_id = worker_agent_id
                        task.current_assignment.role = "worker"
                        task.current_assignment.started_at = utc_now()
                    emit_signal(
                        task,
                        "WORKER_RETRY_REQUIRED",
                        {"task_id": task.task_id, "submission_version": task.submission_version},
                    )

            self.store.save_task(task)
            return {
                "ok": True,
                "status": task.status,
                "attempt_count": task.attempt_count,
                "terminal_reason": task.terminal_reason,
            }

    def wait_for_task_signal(
        self,
        task_id: str,
        last_event_seq: int = 0,
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            with self.store.task_lock(task_id):
                task = self.store.load_task(task_id)
                pending = [sig for sig in task.signals if sig["seq"] > last_event_seq]
                if pending:
                    return {"ok": True, "signals": pending, "status": task.status}
            time.sleep(0.5)
        return {"ok": True, "signals": [], "status": "TIMEOUT"}

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self.store.task_lock(task_id):
            task = self.store.load_task(task_id)
            return {"ok": True, "task": task.to_dict()}

    def pause_task(self, task_id: str, owner: str, reason: str) -> dict[str, Any]:
        with self.store.task_lock(task_id):
            task = self.store.load_task(task_id)
            if task.status in {"COMPLETED", "TERMINAL_FAILED"}:
                raise ValueError("cannot pause terminal/completed task")
            self._transition(task, "MANUAL_TAKEOVER")
            task.manual_owner = owner
            emit_signal(task, "TASK_PAUSED", {"owner": owner, "reason": reason})
            append_history(
                task=task,
                action="MANUAL_TAKEOVER_SET",
                reasoning=reason,
                status_change="TO_MANUAL_TAKEOVER",
                agent_id=owner,
                role="manager",
                tool="manual",
            )
            self.store.save_task(task)
            return {"ok": True, "status": task.status}

    def resume_task(self, task_id: str, owner: str) -> dict[str, Any]:
        with self.store.task_lock(task_id):
            task = self.store.load_task(task_id)
            if task.status != "MANUAL_TAKEOVER":
                raise ValueError("task is not in MANUAL_TAKEOVER")
            self._transition(task, "IN_PROGRESS")
            task.manual_owner = owner
            emit_signal(task, "TASK_RESUMED", {"owner": owner})
            append_history(
                task=task,
                action="TASK_RESUMED",
                reasoning="Manual owner resumed task for worker execution.",
                status_change="TO_IN_PROGRESS",
                agent_id=owner,
                role="manager",
                tool="manual",
            )
            self.store.save_task(task)
            return {"ok": True, "status": task.status}

    def _assign(self, task: Task, agent_id: str, role: str, tool: str) -> None:
        if task.status == "READY_FOR_WORK":
            self._transition(task, "IN_PROGRESS")
        elif task.status == "FAILED_QA":
            self._transition(task, "IN_PROGRESS")
        task.current_assignment.agent_id = agent_id
        task.current_assignment.role = role
        task.current_assignment.started_at = utc_now()
        if role == "worker":
            task.metadata["worker_agent_id"] = agent_id
        append_history(
            task=task,
            action="WORKER_CLAIMED" if role == "worker" else "QA_STARTED",
            reasoning=f"{role} claimed task.",
            status_change=f"TO_{task.status}",
            agent_id=agent_id,
            role=role,
            tool=tool,
        )
        emit_signal(task, "TASK_CLAIMED", {"task_id": task.task_id, "agent_id": agent_id, "role": role})

    def _transition(self, task: Task, nxt: str) -> None:
        assert_transition(task.status, nxt)
        task.status = nxt
        task.updated_at = utc_now()

    @staticmethod
    def _ensure_assigned(task: Task, agent_id: str, role: str) -> None:
        if task.current_assignment.agent_id != agent_id or task.current_assignment.role != role:
            raise ValueError("agent is not current assignee")

    @staticmethod
    def _idempotent_check(task: Task, idempotency_key: str | None) -> None:
        if not idempotency_key:
            return
        if idempotency_key in task.idempotency_keys:
            raise ValueError("duplicate idempotency key")
        task.idempotency_keys.append(idempotency_key)


def _hash_payload(content: str, artifacts: list[str], submission_version: int) -> str:
    sha = hashlib.sha256()
    sha.update(content.encode("utf-8"))
    sha.update(",".join(sorted(artifacts)).encode("utf-8"))
    sha.update(str(submission_version).encode("utf-8"))
    return sha.hexdigest()
