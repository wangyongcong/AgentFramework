from orchestrator.broker import Broker


def test_happy_path(tmp_path):
    broker = Broker(root=tmp_path, max_failures=3)
    created = broker.create_task(
        metadata={"tool_preference": "codex-cli", "qa_command": "echo ok"},
        dev_spec="Implement feature.",
    )
    task_id = created["task_id"]

    worker_claim = broker.claim_task(agent_id="worker-1", role="worker", tool="codex-cli")
    assert worker_claim["ok"]
    assert worker_claim["task"]["task_id"] == task_id

    submit = broker.submit_worker_output(
        task_id=task_id,
        agent_id="worker-1",
        content="done",
        artifacts=[],
        reasoning="first implementation",
    )
    assert submit["ok"]
    assert submit["status"] == "WAITING_FOR_QA"
    assert submit["submission_version"] == 1

    qa_claim = broker.claim_task(agent_id="qa-1", role="qa", tool="qa-agent")
    assert qa_claim["ok"]
    assert qa_claim["task"]["status"] == "UNDER_TEST"

    qa_pass = broker.submit_qa_report(
        task_id=task_id,
        agent_id="qa-1",
        passed=True,
        summary="all good",
        logs="",
        tested_submission_version=1,
    )
    assert qa_pass["ok"]
    assert qa_pass["status"] == "COMPLETED"


def test_fail_then_terminal(tmp_path):
    broker = Broker(root=tmp_path, max_failures=3)
    created = broker.create_task(
        metadata={"tool_preference": "codex-cli"},
        dev_spec="Implement feature.",
    )
    task_id = created["task_id"]

    broker.claim_task(agent_id="worker-1", role="worker", tool="codex-cli")
    for version in (1, 2, 3):
        broker.submit_worker_output(
            task_id=task_id,
            agent_id="worker-1",
            content=f"attempt-{version}",
            artifacts=[],
            reasoning="retry",
        )
        broker.claim_task(agent_id="qa-1", role="qa", tool="qa-agent")
        result = broker.submit_qa_report(
            task_id=task_id,
            agent_id="qa-1",
            passed=False,
            summary="failed",
            logs="stacktrace",
            tested_submission_version=version,
        )
        assert result["ok"]

    final_task = broker.get_task(task_id)["task"]
    assert final_task["status"] == "MANUAL_TAKEOVER"
    assert final_task["attempt_count"] == 3
    assert final_task["terminal_reason"]

