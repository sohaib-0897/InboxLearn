import csv
import io

import numpy as np
import pytest

from inboxlearn.classifier import deserialize_bundle, train_bundle
from inboxlearn.config import Settings
from inboxlearn.demo import load_demo_rows
from inboxlearn.service import InboxLearnService
from inboxlearn.evaluation import assert_split_isolated


def import_label(service, row):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["subject", "body", "sender"])
    writer.writeheader()
    writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    service.classify_upload(stream.getvalue().encode())
    email = service.repo.inbox_rows()[0]
    service.save_feedback(email["id"], row["category"], row["priority"])


def test_feedback_updates_use_the_confirmed_email_content(tmp_path):
    service = InboxLearnService(Settings(db_path=tmp_path / "learning.sqlite3"))
    row = load_demo_rows("demo_feedback.csv")[0]
    baseline = deserialize_bundle(service.active_version()["model_blob"])
    import_label(service, row)
    # Independent direct update with the actual email must match the service update.
    expected = train_bundle([row], base=baseline, incremental=True)
    candidate = service.train()
    actual = deserialize_bundle(service.repo.version(candidate["version_id"])["model_blob"])
    np.testing.assert_array_equal(actual.category_model.coef_, expected.category_model.coef_)
    np.testing.assert_array_equal(actual.priority_model.coef_, expected.priority_model.coef_)
    assert not np.array_equal(actual.category_model.coef_, baseline.category_model.coef_)
    service.compare_versions(candidate["version_id"])
    service.activate(candidate["version_id"])
    # A revision must rebuild using that same content and only the latest labels.
    revised = dict(row, category="university", priority="low")
    service.save_feedback(service.repo.inbox_rows()[0]["id"], revised["category"], revised["priority"])
    candidate = service.train()
    expected = train_bundle(load_demo_rows("demo_seed.csv") + [revised])
    actual = deserialize_bundle(service.repo.version(candidate["version_id"])["model_blob"])
    np.testing.assert_array_equal(actual.category_model.coef_, expected.category_model.coef_)
    np.testing.assert_array_equal(actual.priority_model.coef_, expected.priority_model.coef_)


@pytest.mark.parametrize("dataset", ["demo_eval.csv", "demo_validation.csv"])
def test_reserved_split_cannot_enter_training_even_with_changed_sender(tmp_path, dataset):
    service = InboxLearnService(Settings(db_path=tmp_path / "isolation.sqlite3"))
    row = dict(load_demo_rows(dataset)[0], sender="changed@example.test")
    row["body"] = "  " + row["body"].upper() + "  "
    import_label(service, row)
    original = service.active_version()["model_blob"]
    with pytest.raises(ValueError, match="overlap"):
        service.train()
    assert len(service.repo.versions()) == 1
    assert service.active_version()["model_blob"] == original
    assert service.repo.pending_feedback_count() == 1


def test_training_rejects_label_only_rows():
    with pytest.raises(ValueError, match="subject and body"):
        train_bundle([{"category": "spam", "priority": "low"}])


def test_overlap_check_cannot_silently_accept_missing_content():
    with pytest.raises(ValueError, match="subject and body"):
        assert_split_isolated([{"category": "spam"}], load_demo_rows("demo_eval.csv"))
