"""Candidate lifecycle and read-only prediction comparisons against actual models."""
from contextlib import closing
import pytest

from inboxlearn.classifier import deserialize_bundle
from inboxlearn.config import Settings
from inboxlearn.demo import demo_data_path, load_demo_rows
from inboxlearn.service import InboxLearnService
from inboxlearn.validation import content_hash


@pytest.fixture
def service(tmp_path):
    service = InboxLearnService(Settings(db_path=tmp_path / "candidate.sqlite3"))
    service.classify_upload(demo_data_path("demo_feedback.csv").read_bytes())
    emails = {row["content_hash"]: row for row in service.repo.inbox_rows()}
    for row in load_demo_rows("demo_feedback.csv"):
        service.save_feedback(emails[content_hash(row)]["id"], row["category"], row["priority"])
    return service


def snapshot(service):
    with closing(service.repo._connect()) as conn:
        return list(conn.iterdump())


def test_candidate_persistence_activation_and_retraining_after_rollback(service):
    original = [dict(row) for row in service.repo.inbox_rows()]
    baseline = dict(service.active_version())
    candidate = service.train()
    reopened = InboxLearnService(service.settings)
    assert reopened.active_version()["model_blob"] == baseline["model_blob"]
    assert reopened.active_version()["id"] == baseline["id"]
    assert reopened.repo.version(candidate["version_id"])["is_active"] == 0
    assert reopened.repo.pending_feedback_count() == 5
    assert reopened.feedback_status(candidate["version_id"]) == {"included": 5, "omitted": 0, "total": 5}
    assert reopened.train()["version_id"] == candidate["version_id"]
    result = reopened.classify_upload(b"subject,body\nAnother email,A completely new inbox message")
    assert result["version_id"] == baseline["id"]
    reopened.compare_versions(candidate["version_id"])
    reopened.activate(candidate["version_id"])
    assert reopened.active_version()["id"] == candidate["version_id"]
    assert not reopened.repo.candidates()
    assert reopened.train() is None
    assert reopened.repo.pending_feedback_count() == 0
    result = reopened.classify_upload(b"subject,body\nYet another email,Future classification after activation")
    assert result["version_id"] == candidate["version_id"]
    reopened.rollback(baseline["id"])
    child = reopened.train()
    assert child["version_id"] != candidate["version_id"]
    assert child["parent_id"] == baseline["id"]
    assert reopened.repo.version(child["version_id"])["model_blob"] == reopened.repo.version(candidate["version_id"])["model_blob"]
    assert [dict(row) for row in reopened.repo.inbox_rows() if row["id"] <= 5] == original


def test_activation_requires_current_heldout_evaluation_including_label_hash(service, monkeypatch):
    candidate = service.train()["version_id"]
    for activate in (service.activate, service.rollback):
        with pytest.raises(ValueError, match="Evaluate this candidate"):
            activate(candidate)
    service.compare_versions(candidate, "demo_validation.csv")
    with pytest.raises(ValueError, match="Evaluate this candidate"):
        service.activate(candidate)
    service.compare_versions(candidate)
    assert service.current_evaluation(candidate)
    def changed_dataset(name):
        rows = load_demo_rows(name)
        if name == "demo_eval.csv":
            rows[0] = dict(rows[0], priority="low" if rows[0]["priority"] != "low" else "high")
        return rows
    monkeypatch.setattr("inboxlearn.service.load_demo_rows", changed_dataset)
    assert service.current_evaluation(candidate) is None
    with pytest.raises(ValueError, match="Evaluate this candidate"):
        service.activate(candidate)
    service.compare_versions(candidate)
    service.activate(candidate)
    service.rollback(1)  # Baseline never required evaluation.
    monkeypatch.setattr("inboxlearn.service.load_demo_rows", load_demo_rows)
    service.activate(candidate)  # Previously activated versions remain available.
    assert service.active_version()["id"] == candidate


def test_revisions_leave_prepared_snapshot_immutable(service):
    first = service.train()["version_id"]
    version = dict(service.repo.version(first))
    membership = {key: dict(row) for key, row in service.repo.feedback_membership(first).items()}
    service.save_feedback(1, "spam", "high")
    assert service.feedback_status(first)["omitted"] == 1
    second = service.train()["version_id"]
    assert second != first
    assert service.repo.feedback_membership(second)[1]["category"] == "spam"
    assert dict(service.repo.version(first)) == version
    assert {key: dict(row) for key, row in service.repo.feedback_membership(first).items()} == membership
    service.compare_versions(first)
    service.activate(first)  # Newer corrections warn but don't rewrite or block an evaluated snapshot.
    assert service.repo.pending_feedback_count() == 1
    rebuilt = service.train()
    assert rebuilt["mode"] == "rebuild_from_seed_plus_latest_feedback"


def test_preview_matches_direct_predictions_and_never_writes(service):
    candidate = service.train()["version_id"]
    before = snapshot(service)
    preview = service.prediction_preview(1, candidate)
    assert snapshot(service) == before
    rows = {row["id"]: dict(row) for row in service.repo.inbox_rows()}
    models = [deserialize_bundle(service.repo.version(version)["model_blob"]) for version in (1, candidate)]
    for row in preview["rows"]:
        for model, prefix, version in zip(models, ("before", "after"), (1, candidate)):
            direct = model.predict(rows[row["id"]], version, 0.7, 0.7)
            for field in ("category", "priority", "category_confidence", "priority_confidence"):
                assert row[f"{prefix}_{field}"] == direct[field]
        assert not row["before_training_member"]
        assert row["after_training_member"]
        assert row["human_category"] == service.repo.feedback_membership(candidate)[row["id"]]["category"]
    assert preview["changed"] == sum(row["before_category"] != row["after_category"] or
                                     row["before_priority"] != row["after_priority"] for row in preview["rows"])
    assert preview["changed"] > 0
    assert service.prediction_preview(1, 1)["changed"] == 0
    key = service.preview_key(1, candidate)
    assert service.preview_key(candidate, 1) != key
    service.save_feedback(1, "spam", "high")
    assert service.preview_key(1, candidate) != key
    key = service.preview_key(1, candidate)
    service.classify_upload(b"subject,body\nNew preview email,Body text for additional preview")
    assert service.preview_key(1, candidate) != key


def test_seed_membership_and_legacy_additive_migration(service):
    service.classify_upload(demo_data_path("demo_seed.csv").read_bytes())
    preview = service.prediction_preview(1, 1)
    assert sum(row["after_training_member"] for row in preview["rows"]) == len(load_demo_rows("demo_seed.csv"))
    old_trained_version = service.train()["version_id"]
    # Simulate an existing database from before the candidate registry was introduced.
    with service.repo.training_transaction() as conn:
        conn.execute("DROP TABLE candidate_registry")
    versions = [dict(row) for row in service.repo.versions()]
    predictions = [dict(row) for row in service.repo.inbox_rows()]
    reopened = InboxLearnService(service.settings)
    assert not reopened.repo.candidates()
    assert [dict(row) for row in reopened.repo.versions()] == versions
    assert [dict(row) for row in reopened.repo.inbox_rows()] == predictions
    reopened.activate(old_trained_version)  # Historical trained versions also need no retroactive evaluation.
    assert reopened.active_version()["id"] == old_trained_version


def test_candidate_key_tracks_seed_and_recipe(service, monkeypatch):
    first = service.train()["version_id"]
    monkeypatch.setattr("inboxlearn.service.TRAINING_RECIPE_VERSION", "future-recipe")
    second = service.train()["version_id"]
    assert second != first
    def changed_seed(name):
        rows = load_demo_rows(name)
        if name == "demo_seed.csv":
            rows[0] = dict(rows[0], body=rows[0]["body"] + " Additional seed context.")
        return rows
    monkeypatch.setattr("inboxlearn.service.load_demo_rows", changed_seed)
    third = service.train()["version_id"]
    assert third != second
    assert len(service.repo.candidates()) == 3


def test_review_order_uses_minimum_estimate_and_id_tiebreak(service):
    with service.repo.training_transaction() as conn:
        conn.execute("UPDATE predictions SET category_confidence=0.8, priority_confidence=0.8")
        conn.execute("UPDATE predictions SET priority_confidence=0.1 WHERE email_id IN (2,4)")
        conn.execute("UPDATE predictions SET category_confidence=0.05 WHERE email_id=3")
    assert [row["id"] for row in service.review_rows(include_confident=True)] == [3, 2, 4, 1, 5]
    assert [row["id"] for row in service.review_rows(include_confident=True, order="Newest first")] == [5, 4, 3, 2, 1]
