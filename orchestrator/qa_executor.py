from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class QaResult:
    passed: bool
    summary: str
    logs: str
    artifacts: list[str]


class QAExecutor:
    def run(self, command: str) -> QaResult:
        completed = subprocess.run(command, shell=True, capture_output=True, text=True)
        logs = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        return QaResult(
            passed=completed.returncode == 0,
            summary="QA command passed." if completed.returncode == 0 else "QA command failed.",
            logs=logs.strip(),
            artifacts=[],
        )

