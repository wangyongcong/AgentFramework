from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class TaskEventHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger("orchestrator.watchdog")

    def on_any_event(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        self.logger.info("task fs event: %s %s", event.event_type, event.src_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="MAS-GDM Orchestrator Watch Service")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    observer = Observer()
    observer.schedule(TaskEventHandler(), str(tasks_dir), recursive=False)
    observer.start()
    logging.info("watching tasks dir: %s", tasks_dir)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

