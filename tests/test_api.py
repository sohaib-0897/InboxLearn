"""Tests for the InboxLearn FastAPI REST interface."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from inboxlearn.api import create_app
from inboxlearn.config import Settings
from inboxlearn.service import InboxLearnService


@pytest.fixture
def test_client(tmp_path: Path):
    db_path = tmp_path / "test_api.sqlite3"
    svc = InboxLearnService(Settings(db_path=db_path, category_threshold=0.65, priority_threshold=0.60))
    app = create_app(svc)
    with TestClient(app) as client:
        yield client, svc


def test_api_health(test_client):
    client, _ = test_client
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_status(test_client):
    client, _ = test_client
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_version" in data
    assert data["active_version"]["label"] == "v1"
    assert "metrics" in data
    assert "thresholds" in data
    assert len(data["categories"]) == 5
    assert len(data["priorities"]) == 3


def test_api_predict(test_client):
    client, _ = test_client
    payload = {
        "subject": "Interview schedule for Staff ML Engineer",
        "sender": "recruiting@techcompany.org",
        "body": "Hi there, we would love to schedule a follow-up interview next Monday at 2pm.",
    }
    resp = client.post("/api/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] in ["job opportunities", "university", "bills", "promotions", "spam"]
    assert data["priority"] in ["low", "normal", "high"]
    assert 0.0 <= data["category_confidence"] <= 1.0
    assert 0.0 <= data["priority_confidence"] <= 1.0
    assert "all_category_scores" in data
    assert "all_priority_scores" in data
    assert data["feature_dimensions"] == 4096
    assert data["latency_ms"] >= 0.0
    assert isinstance(data["extracted_entities"], list)


def test_api_candidate_and_eval_lifecycle(test_client):
    client, svc = test_client
    # Import demo emails to have review items
    import_resp = client.post("/api/inbox/demo-import")
    assert import_resp.status_code == 200
    assert import_resp.json()["imported"] > 0

    # Save human feedback
    inbox_resp = client.get("/api/inbox")
    emails = inbox_resp.json()["rows"]
    assert len(emails) > 0
    first_id = emails[0]["id"]
    
    fb_resp = client.post("/api/feedback", json={
        "email_id": first_id,
        "category": "bills",
        "priority": "high",
    })
    assert fb_resp.status_code == 200
    assert fb_resp.json()["status"] == "success"

    # Prepare candidate
    prep_resp = client.post("/api/models/prepare")
    assert prep_resp.status_code == 200
    prep_data = prep_resp.json()
    assert prep_data["status"] == "success"
    cand_id = prep_data["version_id"]

    # Pre-activation Diff
    diff_resp = client.post("/api/models/diff", json={"before_id": 1, "after_id": cand_id})
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    assert "rows" in diff_data
    assert "changed" in diff_data

    # Attempt activation before evaluation -> MUST fail evaluation gate!
    act_fail_resp = client.post("/api/models/activate", json={"version_id": cand_id})
    assert act_fail_resp.status_code == 400
    assert "held-out dataset before activation" in act_fail_resp.json()["detail"]

    # Run evaluation gate
    eval_resp = client.post("/api/models/evaluate", json={"version_id": cand_id, "dataset_name": "demo_eval.csv"})
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert "category_accuracy" in eval_data["baseline"]
    assert "category_accuracy" in eval_data["updated"]

    # Now activate -> MUST succeed!
    act_ok_resp = client.post("/api/models/activate", json={"version_id": cand_id})
    assert act_ok_resp.status_code == 200
    assert act_ok_resp.json()["status"] == "success"

    # Roll back to v1
    rb_resp = client.post("/api/models/rollback", json={"version_id": 1})
    assert rb_resp.status_code == 200
    assert rb_resp.json()["rolled_back_to"]["id"] == 1
