from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    from filelock import FileLock
except ImportError:  # pragma: no cover - fallback for minimal environments
    class FileLock:  # type: ignore[override]
        _locks: dict[str, threading.Lock] = {}
        _global = threading.Lock()

        def __init__(self, path: str) -> None:
            self.path = path

        def __enter__(self) -> None:
            with FileLock._global:
                lock = FileLock._locks.setdefault(self.path, threading.Lock())
            lock.acquire()
            self._lock = lock

        def __exit__(self, exc_type, exc, tb) -> None:
            self._lock.release()

from .schemas import Task


class TaskStore:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.tasks_dir = self.root / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def lock_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.lock"

    @contextmanager
    def task_lock(self, task_id: str) -> Iterator[None]:
        lock = FileLock(str(self.lock_path(task_id)))
        with lock:
            yield

    def save_task(self, task: Task) -> None:
        path = self.task_path(task.task_id)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def load_task(self, task_id: str) -> Task:
        path = self.task_path(task_id)
        if not path.exists():
            raise FileNotFoundError(f"task not found: {task_id}")
        with open(path, "r", encoding="utf-8") as f:
            return Task.from_dict(json.load(f))

    def list_tasks(self) -> list[str]:
        return [p.stem for p in self.tasks_dir.glob("*.json")]
