from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .broker import Broker


def _read_json(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _print(data: dict) -> None:
    print(json.dumps(data, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MAS-GDM Broker CLI RPC")
    parser.add_argument("--root", default=".", help="Repository root path")
    parser.add_argument("--max-failures", default=3, type=int)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create_task")
    p_create.add_argument("--metadata-json", required=True)
    p_create.add_argument("--dev-spec-file", required=True)
    p_create.add_argument("--task-id")

    p_claim = sub.add_parser("claim_task")
    p_claim.add_argument("--agent-id", required=True)
    p_claim.add_argument("--role", required=True, choices=["worker", "qa"])
    p_claim.add_argument("--tool", required=True)
    p_claim.add_argument("--task-id")

    p_submit = sub.add_parser("submit_worker_output")
    p_submit.add_argument("--task-id", required=True)
    p_submit.add_argument("--agent-id", required=True)
    p_submit.add_argument("--content-file", required=True)
    p_submit.add_argument("--artifacts-json", default="[]")
    p_submit.add_argument("--reasoning", default="")
    p_submit.add_argument("--idempotency-key")

    p_qa = sub.add_parser("submit_qa_report")
    p_qa.add_argument("--task-id", required=True)
    p_qa.add_argument("--agent-id", required=True)
    p_qa.add_argument("--passed", required=True, choices=["true", "false"])
    p_qa.add_argument("--summary", default="")
    p_qa.add_argument("--logs-file")
    p_qa.add_argument("--tested-submission-version", required=True, type=int)
    p_qa.add_argument("--artifacts-json", default="[]")
    p_qa.add_argument("--idempotency-key")

    p_get = sub.add_parser("get_task")
    p_get.add_argument("--task-id", required=True)

    p_wait = sub.add_parser("wait_for_task_signal")
    p_wait.add_argument("--task-id", required=True)
    p_wait.add_argument("--last-event-seq", default=0, type=int)
    p_wait.add_argument("--timeout-seconds", default=60, type=int)

    p_pause = sub.add_parser("pause_task")
    p_pause.add_argument("--task-id", required=True)
    p_pause.add_argument("--owner", required=True)
    p_pause.add_argument("--reason", required=True)

    p_resume = sub.add_parser("resume_task")
    p_resume.add_argument("--task-id", required=True)
    p_resume.add_argument("--owner", required=True)

    args = parser.parse_args(argv)
    broker = Broker(root=Path(args.root), max_failures=args.max_failures)

    try:
        if args.cmd == "create_task":
            metadata = _read_json(args.metadata_json)
            dev_spec = Path(args.dev_spec_file).read_text(encoding="utf-8")
            _print(broker.create_task(metadata=metadata, dev_spec=dev_spec, task_id=args.task_id))
        elif args.cmd == "claim_task":
            _print(
                broker.claim_task(
                    agent_id=args.agent_id,
                    role=args.role,
                    tool=args.tool,
                    task_id=args.task_id,
                )
            )
        elif args.cmd == "submit_worker_output":
            content = Path(args.content_file).read_text(encoding="utf-8")
            artifacts = json.loads(args.artifacts_json)
            _print(
                broker.submit_worker_output(
                    task_id=args.task_id,
                    agent_id=args.agent_id,
                    content=content,
                    artifacts=artifacts,
                    reasoning=args.reasoning,
                    idempotency_key=args.idempotency_key,
                )
            )
        elif args.cmd == "submit_qa_report":
            artifacts = json.loads(args.artifacts_json)
            logs = Path(args.logs_file).read_text(encoding="utf-8") if args.logs_file else ""
            _print(
                broker.submit_qa_report(
                    task_id=args.task_id,
                    agent_id=args.agent_id,
                    passed=args.passed == "true",
                    summary=args.summary,
                    logs=logs,
                    tested_submission_version=args.tested_submission_version,
                    artifacts=artifacts,
                    idempotency_key=args.idempotency_key,
                )
            )
        elif args.cmd == "get_task":
            _print(broker.get_task(args.task_id))
        elif args.cmd == "wait_for_task_signal":
            _print(
                broker.wait_for_task_signal(
                    task_id=args.task_id,
                    last_event_seq=args.last_event_seq,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        elif args.cmd == "pause_task":
            _print(broker.pause_task(task_id=args.task_id, owner=args.owner, reason=args.reason))
        elif args.cmd == "resume_task":
            _print(broker.resume_task(task_id=args.task_id, owner=args.owner))
        else:
            return 2
    except Exception as exc:
        _print({"ok": False, "error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

