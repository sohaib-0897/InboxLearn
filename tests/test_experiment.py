from pathlib import Path

from inboxlearn.config import Settings
from inboxlearn.service import InboxLearnService
from scripts.experiment import run_experiment


def test_experiment_reproduces_and_never_touches_caller_database(tmp_path, monkeypatch):
    user_database = tmp_path / "user.sqlite3"
    user = InboxLearnService(Settings(db_path=user_database))
    user.classify_upload(b"subject,body\nUser email,Private content stays out of the report")
    user.save_feedback(user.repo.inbox_rows()[0]["id"], "university", "normal")
    user.train()
    before = user_database.read_bytes()
    active = user.active_version()["id"]
    monkeypatch.setenv("INBOXLEARN_DB", str(user_database))
    first = run_experiment(tmp_path / "runs")
    second = run_experiment(tmp_path / "runs")
    assert first == second  # Full precision metrics, predictions, hashes and memberships.
    assert user_database.read_bytes() == before
    assert user.active_version()["id"] == active
    assert first["temporary_database_removed"]
    assert not list((tmp_path / "runs").iterdir())
    assert first["rollback"]["predictions_and_confidences_identical"]
    assert first["training"]["repeat_training_was_noop"]
    assert first["training"]["feedback_rows"] == 5
    assert first["baseline"]["rows"] == first["updated"]["rows"] == 10
    assert all(n == 0 for n in first["overlap"]["pair_counts"].values())
    assert "Private content" not in str(first)
    assert str(user_database) not in str(first)
    assert set(first["absolute_changes"]) == {"category_accuracy", "category_macro_f1", "priority_accuracy", "priority_macro_f1"}
