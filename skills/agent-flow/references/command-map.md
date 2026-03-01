# Command Map

Use these commands from repository root (`C:\projects\AgentFramework`).

## Environment Setup

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
```

## Preferred End-To-End Workflow

```powershell
python -m orchestrator.workflow --root . start --metadata-json metadata.json --dev-spec-file dev_spec.md
python -m orchestrator.workflow --root . status
python -m orchestrator.workflow --root . stop
```

## Manual Task And Agent Control

```powershell
python -m orchestrator.cli --root . create_task --metadata-json metadata.json --dev-spec-file dev_spec.md
python workers/worker_codex.py --root . --agent-id worker-codex-1
python workers/qa_agent.py --root . --agent-id qa-1
python -m orchestrator.cli --root . get_task --task-id <TASK_ID>
python -m orchestrator.cli --root . pause_task --task-id <TASK_ID> --owner <owner> --reason "<reason>"
python -m orchestrator.cli --root . resume_task --task-id <TASK_ID> --owner <owner>
```

## Useful Paths

- Runtime registry: `.runtime/processes.json`
- Logs: `logs/orchestrator.log`, `logs/worker.log`, `logs/qa.log`
- Task files: `tasks/<task_id>.json`

