"""Real service-backed AppTest checks. Only the unsupported file uploader is adapted."""
import io
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from inboxlearn.config import Settings
from inboxlearn.service import InboxLearnService
from inboxlearn.presentation import metric_rows

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    db = tmp_path / "ui.sqlite3"
    monkeypatch.setenv("INBOXLEARN_DB", str(db))
    return InboxLearnService(Settings(db_path=db))


def assert_clean(app):
    assert not app.exception, [e.message for e in app.exception]
    return app


def click(app, label):
    next(b for b in app.button if b.label == label).click().run()
    assert_clean(app)


def test_empty_states_and_classification_failure(workspace, monkeypatch):
    app = assert_clean(AppTest.from_file(str(APP), default_timeout=20).run())
    assert len(app.tabs) == 4
    assert app.button(key="train_model").disabled
    assert any("Not evaluated" in i.value for i in app.info)
    assert app.button(key="classify_csv").disabled
    monkeypatch.setattr("streamlit.file_uploader", lambda *a, **kw: io.BytesIO(b"subject\nmissing body"))
    app.run()
    app.button(key="classify_csv").click().run()
    assert_clean(app)
    assert any("Missing required field" in e.value for e in app.error)
    assert not workspace.repo.inbox_rows()


def test_ui_workflow_and_version_specific_results(workspace, monkeypatch):
    # AppTest doesn't implement file upload. Feed its boundary actual CSV bytes;
    # browser QA separately exercises the native uploader.
    payload = b'subject,body,sender\n<script>alert(1)</script>,"Review this <b>inert</b> message",test@example.test\n'
    monkeypatch.setattr("streamlit.file_uploader", lambda *a, **kw: io.BytesIO(payload))
    app = assert_clean(AppTest.from_file(str(APP), default_timeout=20).run())
    app.button(key="classify_csv").click().run()
    assert_clean(app)
    assert len(workspace.repo.inbox_rows()) == 1
    assert not workspace.repo.latest_feedback()
    assert any("<script>alert(1)</script>" in t.value for t in app.text)
    app.checkbox[0].check().run()
    app.selectbox(key="category-1").select("university")
    app.selectbox(key="priority-1").select("high")
    click(app, "Save human correction")
    assert workspace.repo.pending_feedback_count() == 1
    assert workspace.active_version()["label"] == "v1"
    assert next(m for m in app.metric if m.label == "Available feedback").value == "1"
    app.button(key="train_model").click().run()
    assert_clean(app)
    assert workspace.active_version()["label"] == "v1"
    assert not app.button(key="train_model").disabled
    assert app.button(key="activate-2").disabled
    assert app.selectbox(key="preview_before").value == 1
    assert app.selectbox(key="preview_after").value == 2
    app.button(key="train_model").click().run()
    assert len(workspace.repo.versions()) == 2
    app.selectbox(key="evaluation_version").select("v2").run()
    assert any("Not evaluated" in i.value for i in app.info)
    app.button(key="evaluate").click().run()
    assert_clean(app)
    assert len(workspace.repo.evaluations()) == 1
    assert app.session_state["last_evaluation"]["updated_version"] == "v2"
    assert len(next(d.value for d in app.dataframe if "Metric" in d.value.columns)) == 4
    assert not app.button(key="activate-2").disabled
    app.button(key="preview_compute").click().run()
    assert app.session_state["prediction_preview"]["result"]["total"] == 1
    app.button(key="activate-2").click().run()
    assert workspace.active_version()["label"] == "v2"
    assert app.button(key="train_model").disabled
    app.selectbox(key="evaluation_version").select("v1").run()
    assert any("Not evaluated — v1" in i.value for i in app.info)
    # Revision form stays available for confident and already confirmed messages.
    app.selectbox(key="category-1").select("spam")
    click(app, "Save human correction")
    assert "prediction_preview" not in app.session_state
    app.button(key="train_model").click().run()
    assert_clean(app)
    assert workspace.version_metadata(3)["training_mode"] == "rebuild_from_seed_plus_latest_feedback"
    assert app.button(key="activate-3").disabled
    app.selectbox(key="evaluation_version").select("v3").run()
    app.button(key="evaluate").click().run()
    app.button(key="activate-1").click().run()
    assert_clean(app)
    assert workspace.active_version()["id"] == 1
    assert next(m for m in app.metric if m.label == "Active version").value == "v1"
    app.button(key="activate-3").click().run()
    assert workspace.active_version()["id"] == 3
    app.button(key="activate-1").click().run()
    app.button(key="train_model").click().run()
    assert_clean(app)
    assert workspace.repo.versions()[0]["parent_id"] == 1
    assert workspace.active_version()["id"] == 1
    app.selectbox(key="evaluation_version").select("v2").run()
    assert len(next(d.value for d in app.dataframe if "Metric" in d.value.columns)) == 4
    assert any(h.value == "v1 baseline / v2 selected" for h in app.subheader)
    assert b"corrected_category" in workspace.export_csv()


def test_filters_and_confident_review(workspace):
    app = assert_clean(AppTest.from_file(str(APP), default_timeout=20).run())
    app.slider[0].set_value(0.0)
    app.slider[1].set_value(0.0).run()
    app.button(key="demo_classify").click().run()
    assert_clean(app)
    assert len(workspace.repo.inbox_rows()) == 5
    assert all(r["status"] == "classified" for r in workspace.repo.inbox_rows())
    assert not any(s.key == "review_email" for s in app.selectbox)
    app.checkbox[0].check().run()
    assert app.selectbox(key="review_email")
    app.text_input(key="inbox_search").input("no-such-message").run()
    assert any("No messages match" in i.value for i in app.info)
    app.text_input(key="inbox_search").input("Rent invoice").run()
    assert len(next(d.value for d in app.dataframe if "Subject" in d.value.columns)) == 1


def test_regressions_are_labelled_without_fabricating_scores():
    keys = ["category_accuracy", "category_macro_f1", "priority_accuracy", "priority_macro_f1"]
    rows = metric_rows({"baseline": dict.fromkeys(keys, 0.75), "updated": dict.fromkeys(keys, 0.5)})
    assert all(r["Result"] == "Regression" and r["Change"] == "-0.250" for r in rows)


def test_save_next_order_exhaustion_and_history(workspace):
    app = assert_clean(AppTest.from_file(str(APP), default_timeout=20).run())
    app.button(key="demo_classify").click().run()
    app.checkbox(key="include_confident").check().run()
    expected = [r["id"] for r in workspace.review_rows(include_confident=True)]
    assert app.selectbox(key="review_email").value == expected[0]
    assert all(" · " in option for option in app.selectbox(key="review_email").options)
    app.selectbox(key="review_order").select("Newest first").run()
    assert app.selectbox(key="review_email").options[0].startswith("#5 · ")
    app.selectbox(key="review_order").select("Lowest confidence first").run()
    for index, email_id in enumerate(expected):
        assert app.selectbox(key="review_email").value == email_id
        click(app, "Save and next")
        assert len(workspace.repo.latest_feedback()) == index + 1
    assert any("Review complete" in notice.value for notice in app.success)
    assert len(app.selectbox(key="review_email").options) == 5
    assert any(exp.label == "Correction history" for exp in app.expander)
    app.checkbox(key="include_confident").uncheck().run()
    assert not any(s.key == "review_email" for s in app.selectbox)
    assert workspace.active_version()["id"] == 1


def test_failed_save_keeps_message_and_form(workspace, monkeypatch):
    app = assert_clean(AppTest.from_file(str(APP), default_timeout=20).run())
    app.button(key="demo_classify").click().run()
    app.checkbox(key="include_confident").check().run()
    selected = app.selectbox(key="review_email").value
    app.selectbox(key=f"category-{selected}").select("spam")
    app.selectbox(key=f"priority-{selected}").select("high")
    def fail(*args, **kwargs):
        raise RuntimeError("Simulated save failure")
    monkeypatch.setattr(InboxLearnService, "save_feedback", fail)
    click(app, "Save and next")
    assert any("Simulated save failure" in e.value for e in app.error)
    assert app.selectbox(key="review_email").value == selected
    assert app.selectbox(key=f"category-{selected}").value == "spam"
    assert app.selectbox(key=f"priority-{selected}").value == "high"
    assert not workspace.repo.latest_feedback()


def test_stale_candidate_warning_and_preview_invalidation(workspace):
    app = assert_clean(AppTest.from_file(str(APP), default_timeout=20).run())
    app.button(key="demo_classify").click().run()
    app.checkbox(key="include_confident").check().run()
    click(app, "Save human correction")
    app.button(key="train_model").click().run()
    app.button(key="preview_compute").click().run()
    assert "prediction_preview" in app.session_state
    app.selectbox(key="preview_before").select(2).run()
    assert "prediction_preview" not in app.session_state
    app.button(key="preview_compute").click().run()
    assert any("No changed messages" in i.value for i in app.info)
    app.checkbox(key="preview_changed_only").uncheck().run()
    assert len(next(d.value for d in app.dataframe if "Before category" in d.value.columns)) == 5
    selected = app.selectbox(key="review_email").value
    current = app.selectbox(key=f"category-{selected}").value
    app.selectbox(key=f"category-{selected}").select("spam" if current != "spam" else "bills")
    click(app, "Save human correction")
    assert "prediction_preview" not in app.session_state
    assert any("omits 1 newer correction" in w.value for w in app.warning)
    app.button(key="preview_compute").click().run()
    workspace.classify_upload(b"subject,body\nAnother inbox entry,Additional message to invalidate preview")
    app.run()
    assert "prediction_preview" not in app.session_state


def test_measured_regressions_remain_eligible_for_user_activation(workspace):
    from inboxlearn.demo import demo_data_path
    workspace.classify_upload(demo_data_path("demo_feedback.csv").read_bytes())
    for row in workspace.repo.inbox_rows():
        workspace.save_feedback(row["id"], "spam", "low")
    candidate = workspace.train()["version_id"]
    app = assert_clean(AppTest.from_file(str(APP), default_timeout=20).run())
    assert app.button(key=f"activate-{candidate}").disabled
    app.button(key="evaluate").click().run()
    assert_clean(app)
    assert any("Regression recorded" in warning.value for warning in app.warning)
    assert not app.button(key=f"activate-{candidate}").disabled
    app.button(key=f"activate-{candidate}").click().run()
    assert workspace.active_version()["id"] == candidate
