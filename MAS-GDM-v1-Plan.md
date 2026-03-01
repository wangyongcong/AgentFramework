# MAS-GDM v1 Implementation Plan

## Summary
This repository implements a local-first multi-agent orchestrator using file-backed task state, atomic writes, and CLI RPC commands. The system is engine-agnostic, keeps a worker bound to a task through QA loops, and moves to manual takeover after repeated QA failure.

## Core Behavior
- Source of truth: `tasks/<task_id>.json`
- State transitions:
  - `READY_FOR_WORK -> IN_PROGRESS -> WAITING_FOR_QA -> UNDER_TEST`
  - QA pass: `UNDER_TEST -> COMPLETED`
  - QA fail: `UNDER_TEST -> FAILED_QA -> IN_PROGRESS`
  - Terminal fail after max attempts (default 3): `UNDER_TEST -> TERMINAL_FAILED -> MANUAL_TAKEOVER`
- QA re-test trigger: only on newer `submission_version`

## Components
- `orchestrator/`:
  - `schemas.py`: task and history models
  - `state_machine.py`: status transition guards
  - `state_store.py`: atomic read/write and locking
  - `events.py`: history and signal events
  - `broker.py`: orchestration logic and RPC operations
  - `cli.py`: command-line RPC interface
- `workers/`:
  - `worker_codex.py`: Codex worker loop with broker polling
  - `qa_agent.py`: QA loop and command execution
- `tests/`:
  - `test_state_machine.py`
  - `test_broker_flow.py`

## Assumptions
- Single-machine local deployment.
- Trusted local environment.
- File locking using `filelock`.
- Worker identity remains on same task until completion/terminal fail.
