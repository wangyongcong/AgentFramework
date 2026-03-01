from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from orchestrator.broker import Broker


def run_codex_once(task: dict, output_dir: Path, codex_cmd: str) -> tuple[str, list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    response_file = output_dir / "codex_last_message.txt"

    prompt = (
        "You are the assigned worker.\n"
        f"TASK_ID: {task['task_id']}\n"
        "Follow the dev_spec and make required code edits in this repository.\n"
        "At completion, explain what changed and why.\n"
    )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as prompt_file:
        prompt_file.write(prompt + "\n\nDEV_SPEC:\n" + task["dev_spec"])
        prompt_path = prompt_file.name

    cmd = f'{codex_cmd} exec --json --output-last-message "{response_file}" - < "{prompt_path}"'
    completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode != 0:
        raise RuntimeError(f"Codex failed ({completed.returncode}):\n{stdout}\n{stderr}")
    if not response_file.exists():
        raise RuntimeError("Codex run completed without output-last-message artifact")

    content = response_file.read_text(encoding="utf-8")
    artifacts = [str(response_file)]
    return content, artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex worker loop for MAS-GDM")
    parser.add_argument("--root", default=".")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--tool", default="codex-cli")
    parser.add_argument("--codex-cmd", default="codex")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args()

    broker = Broker(root=args.root)
    root = Path(args.root).resolve()

    print(f"[worker] starting agent_id={args.agent_id}")
    while True:
        claim = broker.claim_task(agent_id=args.agent_id, role="worker", tool=args.tool)
        if not claim.get("ok"):
            time.sleep(args.sleep_seconds)
            continue
        task = claim["task"]
        task_id = task["task_id"]
        print(f"[worker] claimed task {task_id}")

        while True:
            state = broker.get_task(task_id)["task"]
            if state["status"] in {"COMPLETED", "TERMINAL_FAILED", "MANUAL_TAKEOVER"}:
                print(f"[worker] task {task_id} ended in {state['status']}")
                break

            content, artifacts = run_codex_once(
                task=state,
                output_dir=root / "artifacts" / task_id / f"v{state['submission_version'] + 1}",
                codex_cmd=args.codex_cmd,
            )
            result = broker.submit_worker_output(
                task_id=task_id,
                agent_id=args.agent_id,
                content=content,
                artifacts=artifacts,
                reasoning="Codex worker submitted implementation output.",
                idempotency_key=f"{task_id}-worker-{state['submission_version'] + 1}",
            )
            if not result.get("ok"):
                raise RuntimeError(json.dumps(result))

            last_seq = 0
            while True:
                wait = broker.wait_for_task_signal(task_id=task_id, last_event_seq=last_seq, timeout_seconds=30)
                signals = wait.get("signals", [])
                if signals:
                    last_seq = max(sig["seq"] for sig in signals)
                updated = broker.get_task(task_id)["task"]
                if updated["status"] in {"IN_PROGRESS", "COMPLETED", "TERMINAL_FAILED", "MANUAL_TAKEOVER"}:
                    break
                time.sleep(args.sleep_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

