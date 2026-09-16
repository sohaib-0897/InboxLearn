import csv
from concurrent.futures import ThreadPoolExecutor
import io
import json

import pytest

from inboxlearn.config import Settings
from inboxlearn.demo import load_demo_rows
from inboxlearn.evaluation import assert_split_isolated
from inboxlearn.service import InboxLearnService
from inboxlearn.validation import CSVValidationError, parse_csv_bytes


def payload(subject="Test subject", body="A useful test message", sender="sender@example.test"):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["subject", "body", "sender"], lineterminator="\n")
    writer.writeheader()
    writer.writerow({"subject": subject, "body": body, "sender": sender})
    return output.getvalue().encode()


@pytest.fixture
def service(tmp_path):
    return InboxLearnService(Settings(db_path=tmp_path / "test.sqlite3"))


def email_id(service, subject="Test subject"):
    row = service.repo.inbox_rows(include_confident=True)[0]
    assert row["subject"] == subject
    return int(row["id"])


def test_baseline_and_prediction_persist(service):
    baseline = service.active_version()
    assert baseline["kind"] == "baseline"
    result = service.classify_upload(payload(subject="Persist this"))
    assert result == {"rows": 1, "new": 1, "duplicates": 0, "version_id": baseline["id"]}
    row = service.repo.inbox_rows(include_confident=True)[0]
    assert row["model_version_id"] == baseline["id"]
    assert 0 <= row["category_confidence"] <= 1
    assert service.classify_upload(payload(subject="Persist this"))["duplicates"] == 1


def test_real_incremental_model_update_and_deduplication(service):
    service.classify_upload(payload(subject="Incremental message"))
    correction_id, created = service.save_feedback(email_id(service, "Incremental message"), "bills", "high")
    assert created
    first = service.train()
    assert first["mode"] == "incremental_feedback"
    trained = service.repo.version(first["version_id"])
    assert trained["parent_id"] == first["parent_id"]
    assert trained["model_blob"] != service.repo.version(trained["parent_id"])["model_blob"]
    same_id, same_created = service.save_feedback(email_id(service, "Incremental message"), "bills", "high")
    assert (same_id, same_created) == (correction_id, False)
    assert service.train()["version_id"] == first["version_id"]
    service.compare_versions(first["version_id"])
    service.activate(first["version_id"])
    assert service.train() is None


def test_feedback_revision_rebuilds_from_seed_and_latest(service):
    service.classify_upload(payload(subject="Revision message"))
    target = email_id(service, "Revision message")
    service.save_feedback(target, "university", "normal")
    first = service.train()
    service.compare_versions(first["version_id"])
    service.activate(first["version_id"])
    service.save_feedback(target, "spam", "high")
    revised = service.train()
    assert revised["mode"] == "rebuild_from_seed_plus_latest_feedback"
    metadata = service.version_metadata(revised["version_id"])
    assert metadata["feedback_count"] == 1
    assert service.train()["version_id"] == revised["version_id"]
    members = service.repo.feedback_membership(revised["version_id"])
    assert members[target]["category"] == "spam"


def test_rollback_then_further_training_creates_child_of_rolled_back_version(service):
    service.classify_upload(payload(subject="Rollback message"))
    target = email_id(service, "Rollback message")
    service.save_feedback(target, "promotions", "low")
    updated = service.train()
    service.compare_versions(updated["version_id"])
    service.activate(updated["version_id"])
    baseline_id = updated["parent_id"]
    service.rollback(baseline_id)
    assert service.active_version()["id"] == baseline_id
    service.save_feedback(target, "spam", "high")
    retrained = service.train()
    assert retrained["parent_id"] == baseline_id
    assert service.active_version()["id"] == baseline_id


def test_concurrent_training_commits_one_lineage_update(service, tmp_path):
    service.classify_upload(payload(subject="Concurrent message"))
    target = email_id(service, "Concurrent message")
    service.save_feedback(target, "university", "normal")
    second_service = InboxLearnService(Settings(db_path=tmp_path / "test.sqlite3"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in [pool.submit(service.train), pool.submit(second_service.train)]]
    assert results[0]["version_id"] == results[1]["version_id"]
    assert sorted(result["reused"] for result in results) == [False, True]
    assert len(service.repo.versions()) == 2


def test_split_isolation_detects_normalized_overlap():
    seed = load_demo_rows("demo_seed.csv")
    evaluation = load_demo_rows("demo_eval.csv")
    assert_split_isolated(seed, evaluation)
    duplicate = dict(evaluation[0])
    duplicate["subject"] = "  " + duplicate["subject"].upper() + "  "
    duplicate["body"] = "\n" + duplicate["body"] + "\n"
    with pytest.raises(ValueError, match="overlap"):
        assert_split_isolated(seed + [duplicate], evaluation)


def test_csv_validation_covers_encoding_empty_duplicate_size_and_rows():
    with pytest.raises(CSVValidationError, match="required"):
        parse_csv_bytes(b"subject,sender\nHello,x")
    with pytest.raises(CSVValidationError, match="UTF-8"):
        parse_csv_bytes(b"subject,body\n\xff,body")
    with pytest.raises(CSVValidationError, match="non-empty"):
        parse_csv_bytes(b"subject,body\n,body")
    duplicate = b"subject,body\nSame,Body\nsame,  body  "
    with pytest.raises(CSVValidationError, match="Duplicate"):
        parse_csv_bytes(duplicate)
    with pytest.raises(CSVValidationError, match="byte"):
        parse_csv_bytes(b"subject,body\na,b", max_bytes=3)
    with pytest.raises(CSVValidationError, match="row"):
        parse_csv_bytes(b"subject,body\na,b\nc,d", max_rows=1)


def test_export_protects_spreadsheet_formulas(service):
    service.classify_upload(payload(subject="=SUM(A1:A2)", body="+unsafe"))
    exported = service.export_csv().decode()
    assert "'=SUM(A1:A2)" in exported
    assert "'+unsafe" in exported


def test_complete_workflow_and_evaluation_persistence(service):
    service.classify_upload(payload(subject="Workflow message"))
    target = email_id(service, "Workflow message")
    rows = service.review_rows(include_confident=True)
    assert rows[0]["suggested_action"]
    tuning = service.validation_tuning()
    assert tuning["dataset"] == "demo_validation.csv"
    assert 0.5 <= tuning["category"]["threshold"] <= 0.95
    service.save_feedback(target, "job opportunities", "normal")
    updated = service.train()
    result = service.compare_versions(updated["version_id"])
    assert result["baseline"]["rows"] == result["updated"]["rows"] == len(load_demo_rows("demo_eval.csv"))
    assert len(result["baseline"]["category_confusion_matrix"]) == 5
    assert len(service.repo.evaluations()) == 1
    stored = json.loads(service.repo.evaluations()[0]["results_json"])
    assert stored["heldout_hash"] == result["heldout_hash"]
