---
name: agent-flow
description: Operate the AgentFramework MAS-GDM toolchain safely and consistently. Use when an agent needs to create tasks, run or control the orchestrator workflow, execute worker/QA loops, inspect task state, diagnose stuck transitions, or map failures to logs and task JSON fields.
---

# Agent Flow

## Overview

Run the local MAS-GDM pipeline with the correct commands and lifecycle expectations. Prefer workflow commands first, then fall back to direct CLI/worker/QA commands for debugging.

## Quick Start

Use these commands from repository root:

```powershell
python -m orchestrator.workflow --root . start --metadata-json metadata.json --dev-spec-file dev_spec.md
python -m orchestrator.workflow --root . status
python -m orchestrator.workflow --root . stop
```

If the combined launcher is not appropriate, use direct components:

```powershell
python -m orchestrator.cli --root . create_task --metadata-json metadata.json --dev-spec-file dev_spec.md
python workers/worker_codex.py --root . --agent-id worker-codex-1
python workers/qa_agent.py --root . --agent-id qa-1
```

## Core Files To Read

Read only what is needed:

- `README.md`: operational command surface.
- `orchestrator/workflow.py`: process lifecycle wrapper.
- `orchestrator/cli.py`: manual control and task inspection.
- `orchestrator/broker.py`: assignment, transitions, and QA loop behavior.
- `orchestrator/schemas.py`: canonical task JSON shape.
- `workers/worker_codex.py`: worker polling/submission behavior.
- `workers/qa_agent.py`: test execution and pass/fail reporting.

## State-Aware Execution Rules

Apply this lifecycle model:

- `READY_FOR_WORK -> IN_PROGRESS -> WAITING_FOR_QA -> UNDER_TEST`
- QA pass: `UNDER_TEST -> COMPLETED`
- QA fail: `UNDER_TEST -> FAILED_QA -> IN_PROGRESS`
- Retry cap exceeded: `UNDER_TEST -> TERMINAL_FAILED -> MANUAL_TAKEOVER`

When inspecting issues, always verify `submission_version`, `current_assignment`, and latest QA report/logs before changing code.

## Task JSON And History Discipline

Treat `tasks/<task_id>.json` as source of truth. Preserve:

- `metadata` for platform/tool context.
- `dev_spec` as authoritative implementation scope.
- `latest_output.qa_report` for QA status and logs.
- `history` as append-only event ledger with reasons and artifacts.

Do not invent ad hoc status values. Use orchestrator-defined states only.

## Troubleshooting Flow

Follow this order:

1. Check launcher health: `python -m orchestrator.workflow --root . status`.
2. Inspect logs: `logs/orchestrator.log`, `logs/worker.log`, `logs/qa.log`.
3. Inspect task: `python -m orchestrator.cli --root . get_task --task-id <TASK_ID>`.
4. If blocked, use pause/resume:
   - `python -m orchestrator.cli --root . pause_task --task-id <TASK_ID> --owner <owner> --reason "<reason>"`
   - `python -m orchestrator.cli --root . resume_task --task-id <TASK_ID> --owner <owner>`

## New-Chat Assignment Protocol

For each new assignment, start with a fresh chat context. Do not carry plan or bug context from prior tasks unless explicitly restated in the current task data.

## References

Load command details from `references/command-map.md` when you need exact CLI syntax quickly.
