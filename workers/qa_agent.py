from __future__ import annotations

import argparse
import time
from pathlib import Path

from orchestrator.broker import Broker
from orchestrator.qa_executor import QAExecutor


def _qa_command(task: dict) -> str:
    metadata = task.get("metadata", {})
    # Generic default command; override per task metadata for engine-specific builds/tests.
    return metadata.get("qa_command", "python -m pytest -q")


def main() -> int:
    parser = argparse.ArgumentParser(description="QA agent loop for MAS-GDM")
    parser.add_argument("--root", default=".")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--tool", default="qa-agent")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args()

    broker = Broker(root=args.root)
    executor = QAExecutor()
    root = Path(args.root).resolve()
    print(f"[qa] starting agent_id={args.agent_id}")

    while True:
        claim = broker.claim_task(agent_id=args.agent_id, role="qa", tool=args.tool)
        if not claim.get("ok"):
            time.sleep(args.sleep_seconds)
            continue

        task = claim["task"]
        task_id = task["task_id"]
        submission_version = task["submission_version"]
        cmd = _qa_command(task)
        print(f"[qa] testing task={task_id} submission_version={submission_version} cmd={cmd}")

        result = executor.run(cmd)
        logs_file = root / "artifacts" / task_id / f"qa_v{submission_version}" / "qa.log"
        logs_file.parent.mkdir(parents=True, exist_ok=True)
        logs_file.write_text(result.logs, encoding="utf-8")

        broker.submit_qa_report(
            task_id=task_id,
            agent_id=args.agent_id,
            passed=result.passed,
            summary=result.summary,
            logs=result.logs,
            tested_submission_version=submission_version,
            artifacts=[str(logs_file)],
            idempotency_key=f"{task_id}-qa-{submission_version}",
        )
        time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

