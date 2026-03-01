## Updated Specification: Generic Multi-Agent Orchestrator (MAS-GDM)

This specification defines a language-agnostic, engine-agnostic framework for autonomous software development. It uses a **Centralized Broker** pattern to ensure data integrity and clear task transitions.

---

### 1. System Philosophy

A decentralized execution framework where a central **Orchestrator** manages tasks via a file-based queue. Agents (Workers/QA) are stateless and receive only the necessary context for their specific assignment. This ensures high reliability and a clear audit trail.

---

### 2. Role Definitions & Responsibilities

#### 2.1 The Manager (The Architect)

* **Role:** High-level strategy and technical decomposition.
* **Primary Input:** Human-provided goals (e.g., "Implement a Soul-like parry system").
* **Primary Output:** A **Technical Spec** (Markdown/JSON) defining class structures, logic rules, and success criteria.
* **Collaboration:** Drops the task into the `/backlog`. It defines the *boundaries* for the code without writing it.

#### 2.2 The Orchestrator / Watcher (The Broker)

* **Role:** The non-LLM "Source of Truth" (Python Service).
* **Primary Input:** File system events in the task directories.
* **Primary Output:** Filtered data payloads for polling agents.
* **Collaboration:** Traffic control. It assigns `AGENT_ID`s, handles **Atomic Writes**, and ensures no two agents claim the same task. It filters the Task JSON so agents only see what they need.

#### 2.3 The Worker (The Coder)

* **Role:** Specialized execution (e.g., Gemini CLI, Claude Code).
* **Primary Input:** The `dev_spec` provided by the Orchestrator.
* **Primary Output:** Source code files and local implementation logs.
* **Collaboration:** Polls for work and enters a **Blocking Wait** state upon submission. It cannot take a new task until the QA agent passes its current work.

#### 2.4 The QA Agent (The Gatekeeper)

* **Role:** Verification agent with **Local Tool Execution** capabilities.
* **Primary Input:** Worker’s code + Manager’s original spec.
* **Primary Output:** A `PASS` signal or a `FAILED_QA` report (including stacktraces).
* **Collaboration:** Triggers external build systems (Unity, Unreal, Web compilers). It generates the `bug_spec` that triggers the Worker's fix loop.

---

### 3. Data Structures

#### 3.1 The Task JSON

This structure is designed to be fully portable across different tech stacks.

```json
{
  "task_id": "UUID",
  "status": "UNASSIGNED",
  "metadata": {
    "language": "C# | C++ | Python | TypeScript",
    "engine": "Unity | Unreal | React | None",
    "framework_version": "2022.3.x | 5.3 | 18.x",
    "target_platform": "Windows | Android | Web",
    "tool_preference": "gemini-cli | claud-code | aider"
  },
  "dev_spec": "Markdown string of the goal/plan",
  "current_assignment": {
    "agent_id": null,
    "role": null,
    "started_at": null
  },
  "latest_output": {
    "content": "Source code or diff",
    "qa_report": {
      "passed": null, 
      "summary": "Reason for failure", 
      "logs": "Compiler output / Stacktrace"
    }
  },
  "history": []
}

```

#### 3.2 The History Ledger (`history` array)

```json
{
  "timestamp": "ISO-8601",
  "event_id": "UUID",
  "agent": {
    "id": "worker-gem-4f2a",
    "role": "worker",
    "tool": "gemini-cli"
  },
  "action": "CODE_SUBMISSION | PLAN_GENERATION | TEST_FAILURE",
  "reasoning": "Agent logic explanation",
  "artifacts": ["path/to/script.py", "path/to/log.txt"],
  "status_change": "TO_WAITING_FOR_QA | TO_FAILED_QA | TO_COMPLETED"
}

```

---

### 4. The Collaboration Lifecycle

1. **Generation:** **Manager** creates a task file → Status: `READY_FOR_WORK`.
2. **Assignment:** **Orchestrator** assigns a polling **Worker** → Status: `IN_PROGRESS`.
3. **Submission:** **Worker** submits code → Status: `WAITING_FOR_QA`. Worker starts "Wait for Signal."
4. **Verification:** **QA** polls and runs tests (Compiler/Build Tool) → Status: `UNDER_TEST`.
5. **The Loop:**
* **IF FAIL:** QA reports bugs → Status: `FAILED_QA`. **Worker** is re-activated with the bug report.
* **IF PASS:** QA reports success → Status: `COMPLETED`. **Worker** is released to poll for a new task.



---

### 5. Implementation Requirements

* **Orchestrator:** Python `watchdog` + `FileLock`. Ensures "Atomic Writes" and thread safety.
* **Agent Bridge:** CLI wrapper setting `AGENT_ID` and `TASK_ID` as Environment Variables.
* **New Chat Protocol:** Every assignment must trigger a "New Chat" session to prevent context contamination between tasks.

---
