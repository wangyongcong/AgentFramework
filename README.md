# AgentFramework (MAS-GDM v1)

Local-first generic multi-agent orchestrator for autonomous software workflows.

## Setup
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
```

## Preferred Workflow (Codex-Driven)
1. Open Codex CLI and create your implementation plan.
2. Save plan into `dev_spec.md` and metadata into `metadata.json`.
3. Start everything with one command:

```powershell
python -m orchestrator.workflow --root . start --metadata-json metadata.json --dev-spec-file dev_spec.md
```

This will:
- Create a task from your plan.
- Start orchestrator watcher.
- Start Codex worker agent.
- Start QA agent.

Check running status:
```powershell
python -m orchestrator.workflow --root . status
```

Stop all launched processes:
```powershell
python -m orchestrator.workflow --root . stop
```

## Manual Task Creation (Optional)
```powershell
python -m orchestrator.cli --root . create_task --metadata-json metadata.json --dev-spec-file dev_spec.md
```

## Run Worker and QA Loops
```powershell
python workers/worker_codex.py --root . --agent-id worker-codex-1
python workers/qa_agent.py --root . --agent-id qa-1
```

## Inspect Task
```powershell
python -m orchestrator.cli --root . get_task --task-id <TASK_ID>
```

## Manual Control
```powershell
python -m orchestrator.cli --root . pause_task --task-id <TASK_ID> --owner you --reason "manual fix"
python -m orchestrator.cli --root . resume_task --task-id <TASK_ID> --owner you
```

## Notes
- Worker ownership is sticky across QA retries.
- QA reruns only on newer `submission_version`.
- After 3 QA failures, task becomes `MANUAL_TAKEOVER`.
- Workflow launcher registry: `.runtime/processes.json`.
- Process logs: `logs/orchestrator.log`, `logs/worker.log`, `logs/qa.log`.
