from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from .broker import Broker


RUNTIME_DIR = ".runtime"
REGISTRY_FILE = "processes.json"


def _runtime_paths(root: Path) -> tuple[Path, Path, Path]:
    runtime_dir = root / RUNTIME_DIR
    logs_dir = root / "logs"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir, logs_dir, runtime_dir / REGISTRY_FILE


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _spawn_background(cmd: list[str], cwd: Path, log_file: Path) -> int:
    log_handle = open(log_file, "a", encoding="utf-8")
    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        flags = 0
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True

    process = subprocess.Popen(cmd, **kwargs)
    log_handle.close()
    return process.pid


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)


def cmd_start(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    runtime_dir, logs_dir, registry_path = _runtime_paths(root)
    broker = Broker(root=root, max_failures=args.max_failures)

    registry = _load_json(registry_path, {})
    if registry and any(_is_alive(proc.get("pid", -1)) for proc in registry.values()):
        print(json.dumps({"ok": False, "error": "processes already running; run stop first"}, indent=2))
        return 1

    created_task = None
    if not args.no_create_task:
        metadata = json.loads(Path(args.metadata_json).read_text(encoding="utf-8"))
        dev_spec = Path(args.dev_spec_file).read_text(encoding="utf-8")
        created_task = broker.create_task(metadata=metadata, dev_spec=dev_spec, task_id=args.task_id)

    processes = {}
    service_cmd = [sys.executable, "-m", "orchestrator.service", "--root", str(root)]
    worker_cmd = [
        sys.executable,
        str(root / "workers" / "worker_codex.py"),
        "--root",
        str(root),
        "--agent-id",
        args.worker_agent_id,
        "--tool",
        args.worker_tool,
        "--codex-cmd",
        args.codex_cmd,
    ]
    qa_cmd = [
        sys.executable,
        str(root / "workers" / "qa_agent.py"),
        "--root",
        str(root),
        "--agent-id",
        args.qa_agent_id,
        "--tool",
        args.qa_tool,
    ]

    processes["orchestrator"] = {
        "pid": _spawn_background(service_cmd, root, logs_dir / "orchestrator.log"),
        "cmd": service_cmd,
        "log": str(logs_dir / "orchestrator.log"),
    }
    processes["worker"] = {
        "pid": _spawn_background(worker_cmd, root, logs_dir / "worker.log"),
        "cmd": worker_cmd,
        "log": str(logs_dir / "worker.log"),
    }
    processes["qa"] = {
        "pid": _spawn_background(qa_cmd, root, logs_dir / "qa.log"),
        "cmd": qa_cmd,
        "log": str(logs_dir / "qa.log"),
    }

    _save_json(registry_path, {"root": str(root), "processes": processes})
    print(
        json.dumps(
            {
                "ok": True,
                "task": created_task,
                "registry": str(registry_path),
                "processes": processes,
            },
            indent=2,
        )
    )
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    _, _, registry_path = _runtime_paths(root)
    data = _load_json(registry_path, {})
    processes = data.get("processes", {})
    stopped = []
    for name, proc in processes.items():
        pid = proc.get("pid")
        if isinstance(pid, int) and _is_alive(pid):
            _terminate(pid)
            stopped.append({"name": name, "pid": pid})
    _save_json(registry_path, {"root": str(root), "processes": {}})
    print(json.dumps({"ok": True, "stopped": stopped}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    _, _, registry_path = _runtime_paths(root)
    data = _load_json(registry_path, {})
    processes = data.get("processes", {})
    status = {}
    for name, proc in processes.items():
        pid = proc.get("pid")
        status[name] = {
            "pid": pid,
            "alive": isinstance(pid, int) and _is_alive(pid),
            "log": proc.get("log"),
        }
    print(json.dumps({"ok": True, "status": status}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MAS-GDM workflow launcher")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Create task and launch orchestrator/worker/qa")
    p_start.add_argument("--metadata-json")
    p_start.add_argument("--dev-spec-file")
    p_start.add_argument("--task-id")
    p_start.add_argument("--max-failures", type=int, default=3)
    p_start.add_argument("--worker-agent-id", default="worker-codex-1")
    p_start.add_argument("--qa-agent-id", default="qa-1")
    p_start.add_argument("--worker-tool", default="codex-cli")
    p_start.add_argument("--qa-tool", default="qa-agent")
    p_start.add_argument("--codex-cmd", default="codex")
    p_start.add_argument("--no-create-task", action="store_true")

    p_stop = sub.add_parser("stop", help="Stop launched orchestrator/worker/qa")

    p_status = sub.add_parser("status", help="Show launched process status")

    args = parser.parse_args(argv)
    if args.cmd == "start":
        if not args.no_create_task and (not args.metadata_json or not args.dev_spec_file):
            print(json.dumps({"ok": False, "error": "start requires --metadata-json and --dev-spec-file"}, indent=2))
            return 2
        return cmd_start(args)
    if args.cmd == "stop":
        return cmd_stop(args)
    if args.cmd == "status":
        return cmd_status(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
