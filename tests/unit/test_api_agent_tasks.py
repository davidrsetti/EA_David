"""Unit tests for /v1/tasks* endpoints in api/main.py.

Uses FastAPI TestClient in dev mode (no token = default analyst user).
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Import inside fixture to avoid app startup side-effects at collection time
    from nexus.api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── POST /v1/tasks ───────────────────────────────────────────────────────

def test_submit_task_returns_200(client):
    resp = client.post("/v1/tasks", json={"description": "Run a full portfolio health check now."})
    assert resp.status_code == 200


def test_submit_task_response_has_task_id(client):
    resp = client.post("/v1/tasks", json={"description": "Analyse all AI governance findings."})
    data = resp.json()
    assert "task_id" in data
    assert data["task_id"].startswith("task_")


def test_submit_task_response_has_status(client):
    resp = client.post("/v1/tasks", json={"description": "Check capability gaps in Finance domain."})
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("pending", "running", "completed", "failed")


def test_submit_task_response_has_created_at(client):
    resp = client.post("/v1/tasks", json={"description": "Run a portfolio analysis for the HR domain."})
    data = resp.json()
    assert "created_at" in data
    assert len(data["created_at"]) > 0


def test_submit_task_too_short_description_rejected(client):
    resp = client.post("/v1/tasks", json={"description": "short"})
    assert resp.status_code == 422


def test_submit_task_empty_description_rejected(client):
    resp = client.post("/v1/tasks", json={"description": ""})
    assert resp.status_code == 422


def test_submit_task_missing_description_rejected(client):
    resp = client.post("/v1/tasks", json={})
    assert resp.status_code == 422


# ── GET /v1/tasks/{task_id} ─────────────────────────────────────────────

def test_get_task_unknown_id_returns_404(client):
    resp = client.get("/v1/tasks/task_does_not_exist_000xyz")
    assert resp.status_code == 404


def test_get_task_known_id_returns_200(client):
    post = client.post("/v1/tasks", json={"description": "Describe the impact of retiring SAP ERP."})
    task_id = post.json()["task_id"]
    resp = client.get(f"/v1/tasks/{task_id}")
    assert resp.status_code == 200


def test_get_task_response_shape(client):
    post = client.post("/v1/tasks", json={"description": "List all orphaned applications in the portfolio."})
    task_id = post.json()["task_id"]
    data = client.get(f"/v1/tasks/{task_id}").json()
    assert "task_id" in data
    assert "status" in data
    assert "description" in data


# ── GET /v1/tasks ───────────────────────────────────────────────────────

def test_list_tasks_returns_200(client):
    resp = client.get("/v1/tasks")
    assert resp.status_code == 200


def test_list_tasks_response_shape(client):
    data = client.get("/v1/tasks").json()
    assert "tasks" in data
    assert "count" in data
    assert isinstance(data["tasks"], list)


def test_list_tasks_limit_param(client):
    # Submit several tasks first
    for i in range(3):
        client.post("/v1/tasks", json={"description": f"Limit-test task number {i} for the portfolio."})
    data = client.get("/v1/tasks?limit=2").json()
    assert len(data["tasks"]) <= 2


# ── DELETE /v1/tasks/{task_id} ──────────────────────────────────────────

def test_cancel_unknown_task_returns_404(client):
    resp = client.delete("/v1/tasks/task_nonexistent_cancel_xyz")
    assert resp.status_code == 404


def test_cancel_pending_task_returns_200(client):
    post = client.post("/v1/tasks", json={"description": "Cancel-test task: run portfolio scan."})
    task_id = post.json()["task_id"]

    # Force the task to pending so it can be cancelled
    from nexus.agents.orchestrator import _TASKS
    if task_id in _TASKS and _TASKS[task_id]["status"] not in ("completed", "failed"):
        _TASKS[task_id]["status"] = "pending"
        resp = client.delete(f"/v1/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
    else:
        pytest.skip("Task completed too fast to cancel — timing-dependent test skipped")


def test_cancel_completed_task_returns_409(client):
    from nexus.agents.orchestrator import _TASKS
    post = client.post("/v1/tasks", json={"description": "Conflict test task for completed state."})
    task_id = post.json()["task_id"]
    # Force completed
    _TASKS[task_id]["status"] = "completed"
    resp = client.delete(f"/v1/tasks/{task_id}")
    assert resp.status_code == 409
