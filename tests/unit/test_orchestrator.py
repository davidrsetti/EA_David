"""Unit tests for agents/orchestrator.py — no Claude API calls required."""
import time
import pytest
from nexus.agents.orchestrator import (
    OrchestratorTask, submit_task, get_task, list_tasks, _TASKS,
)


# ── OrchestratorTask dataclass ────────────────────────────────────────────────

def test_orchestrator_task_default_status():
    t = OrchestratorTask(
        task_id="task_abc", user_id="user1", user_role="analyst",
        description="Run a portfolio health check.",
    )
    assert t.status == "pending"
    assert t.result == ""
    assert t.error == ""
    assert isinstance(t.sub_tasks, list)


def test_orchestrator_task_created_at_is_iso_string():
    t = OrchestratorTask(
        task_id="task_xyz", user_id="u", user_role="analyst",
        description="Test task.",
    )
    assert "T" in t.created_at or "-" in t.created_at   # ISO 8601 format


# ── submit_task() ─────────────────────────────────────────────────────────────

def test_submit_task_returns_task_id():
    tid = submit_task("Run a full portfolio analysis report.", "user-test", "analyst")
    assert tid.startswith("task_")


def test_submit_task_creates_entry_in_tasks():
    tid = submit_task("Check all AI agents for missing risk tiers.", "user-test", "analyst")
    task = get_task(tid)
    assert task is not None
    assert task["task_id"] == tid


def test_submit_task_stores_user_id():
    tid = submit_task("Analyse capability gaps in Finance.", "user-alice", "analyst")
    task = get_task(tid)
    assert task["user_id"] == "user-alice"


def test_submit_task_stores_user_role():
    tid = submit_task("Describe the impact of decommissioning SAP.", "user-bob", "admin")
    task = get_task(tid)
    assert task["user_role"] == "admin"


def test_submit_task_initial_status_pending_or_running():
    tid = submit_task("Quick task.", "user-carol", "analyst")
    task = get_task(tid)
    assert task["status"] in ("pending", "running", "completed", "failed")


# ── get_task() ────────────────────────────────────────────────────────────────

def test_get_task_unknown_id_returns_none():
    result = get_task("task_does_not_exist_xyz_000")
    assert result is None


def test_get_task_returns_dict():
    tid = submit_task("Portfolio check.", "u", "analyst")
    task = get_task(tid)
    assert isinstance(task, dict)


# ── list_tasks() ─────────────────────────────────────────────────────────────

def test_list_tasks_returns_list():
    tasks = list_tasks()
    assert isinstance(tasks, list)


def test_list_tasks_respects_limit():
    for i in range(5):
        submit_task(f"Task number {i} for limit test.", "limit-user", "analyst")
    tasks = list_tasks(user_id="limit-user", limit=3)
    assert len(tasks) <= 3


def test_list_tasks_filters_by_user_id():
    uid = "filter-user-unique-xyz"
    submit_task("Filter test task one.", uid, "analyst")
    submit_task("Filter test task two.", uid, "analyst")
    tasks = list_tasks(user_id=uid)
    assert all(t["user_id"] == uid for t in tasks)


def test_list_tasks_empty_user_returns_all():
    """Passing user_id='' should return all tasks (no filter)."""
    before = len(list_tasks(user_id=""))
    submit_task("One more task for count test.", "new-user-abc", "analyst")
    after = len(list_tasks(user_id=""))
    assert after >= before


def test_list_tasks_sorted_newest_first():
    uid = "sort-test-user"
    t1 = submit_task("First sort task.", uid, "analyst")
    time.sleep(0.01)  # ensure different timestamps
    t2 = submit_task("Second sort task.", uid, "analyst")
    tasks = list_tasks(user_id=uid)
    ids = [t["task_id"] for t in tasks]
    assert ids.index(t2) < ids.index(t1)   # newer task comes first
