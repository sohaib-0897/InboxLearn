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


def workspace_app():
    app = AppTest.from_file(str(APP), default_timeout=20)
    app.query_params["view"] = "workspace"
    return assert_clean(app.run())


def click(app, label):
    next(b for b in app.button if b.label == label).click().run()
    assert_clean(app)


def test_empty_states_and_classification_failure(workspace, monkeypatch):
    app = workspace_app()
    assert len(app.tabs) == 5
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
    app = workspace_app()
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
    app = workspace_app()
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
    app = workspace_app()
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
    app = workspace_app()
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
    app = workspace_app()
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
    app = workspace_app()
    assert app.button(key=f"activate-{candidate}").disabled
    app.button(key="evaluate").click().run()
    assert_clean(app)
    assert any("Regression recorded" in warning.value for warning in app.warning)
    assert not app.button(key=f"activate-{candidate}").disabled
    app.button(key=f"activate-{candidate}").click().run()
    assert workspace.active_version()["id"] == candidate


def test_batch_confirmation_ui(workspace):
    from inboxlearn.demo import demo_data_path
    workspace.classify_upload(demo_data_path("demo_feedback.csv").read_bytes())
    
    app = workspace_app()
    app.checkbox(key="include_confident").check().run()
    assert_clean(app)

    # Multi-select 2 messages for batch confirmation
    inbox = workspace.repo.inbox_rows()
    id0 = inbox[0]["id"]
    id1 = inbox[1]["id"]
    app.multiselect(key="batch_confirm_selection").select(id0).select(id1).run()
    assert_clean(app)

    # Change batch target labels
    app.selectbox(key="batch_target_cat").select("promotions").run()
    app.selectbox(key="batch_target_pri").select("low").run()

    # Click batch confirm button
    app.button(key="btn_execute_batch_confirm").click().run()
    assert_clean(app)

    # Verify both feedbacks were committed to repo
    f0 = workspace.repo.feedback_for_email(id0)
    f1 = workspace.repo.feedback_for_email(id1)
    assert len(f0) == 1 and f0[0]["category"] == "promotions" and f0[0]["priority"] == "low"
    assert len(f1) == 1 and f1[0]["category"] == "promotions" and f1[0]["priority"] == "low"


def test_review_filters_ui(workspace):
    from inboxlearn.demo import demo_data_path
    workspace.classify_upload(demo_data_path("demo_feedback.csv").read_bytes())

    app = workspace_app()
    app.checkbox(key="include_confident").check().run()

    inbox = workspace.repo.inbox_rows()
    target_cat = inbox[0]["category"]

    # Filter by target category
    app.selectbox(key="review_cat_filter").select(target_cat).run()
    assert_clean(app)
    
    # Selected review email should have target category
    selected_id = app.selectbox(key="review_email").value
    email_row = next(r for r in workspace.repo.inbox_rows() if r["id"] == selected_id)
    assert email_row["category"] == target_cat



@pytest.mark.parametrize("environment", [
    {},
    {"INBOXLEARN_GMAIL_ENABLED": "0"},
    {"INBOXLEARN_GMAIL_ENABLED": "1", "INBOXLEARN_HOSTED": "1"},
    {"INBOXLEARN_GMAIL_ENABLED": "1", "STREAMLIT_SERVER_IS_RUNNING": "1", "HOSTNAME": "streamlit-demo"},
])
def test_upload_renders_with_gmail_disabled(workspace, monkeypatch, environment):
    for name in ("INBOXLEARN_GMAIL_ENABLED", "INBOXLEARN_HOSTED", "STREAMLIT_SERVER_IS_RUNNING", "HOSTNAME"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    def forbidden_gmail_access(*args, **kwargs):
        pytest.fail("Disabled Gmail must not access credentials or start OAuth")

    monkeypatch.setattr("inboxlearn.gmail.CredentialStore", forbidden_gmail_access)
    monkeypatch.setattr("inboxlearn.gmail.run_oauth_flow", forbidden_gmail_access)
    app = workspace_app()
    assert "Upload / Inbox" in [tab.label for tab in app.tabs]
    assert any("Gmail integration is disabled in hosted demo mode." == info.value for info in app.info)
    assert app.button(key="btn_connect_gmail").disabled
    assert not any(field.key in ("input_gmail_client_id", "input_gmail_client_secret") for field in app.text_input)
    assert not any(button.key in ("btn_run_gmail_sync", "btn_disconnect_gmail_account") for button in app.button)
    assert not app.button(key="demo_classify").disabled
    app.button(key="demo_classify").click().run()
    assert_clean(app)
    assert len(workspace.repo.inbox_rows()) == 5
    assert app.button(key="btn_connect_gmail").disabled


@pytest.mark.parametrize("filename", ["messages.csv", "message.eml", "messages.mbox"])
def test_file_upload_works_with_gmail_disabled(workspace, monkeypatch, filename):
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "0")
    email_bytes = b"From: sender@example.test\nSubject: Invoice due tomorrow\n\nPlease review this invoice.\n"
    payloads = {
        "messages.csv": b"subject,body,sender\nInvoice due tomorrow,Please review this invoice.,sender@example.test\n",
        "message.eml": email_bytes,
        "messages.mbox": b"From sender@example.test Wed Sep 23 08:00:00 2026\n" + email_bytes,
    }
    upload = io.BytesIO(payloads[filename])
    upload.name = filename
    monkeypatch.setattr("streamlit.file_uploader", lambda *args, **kwargs: upload)
    app = workspace_app()
    app.button(key="classify_csv").click().run()
    assert_clean(app)
    assert len(workspace.repo.inbox_rows()) == 1
    assert app.button(key="btn_connect_gmail").disabled


def test_gmail_controls_follow_hosted_setting_on_rerun(workspace, monkeypatch):
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "1")
    monkeypatch.delenv("INBOXLEARN_HOSTED", raising=False)
    monkeypatch.delenv("STREAMLIT_SERVER_IS_RUNNING", raising=False)
    monkeypatch.setattr("inboxlearn.gmail.CredentialStore.load_tokens", lambda self: None)
    app = workspace_app()
    assert any("CONNECT GMAIL" in markdown.value for markdown in app.markdown)
    monkeypatch.setenv("INBOXLEARN_HOSTED", "1")
    assert_clean(app.run())
    assert app.button(key="btn_connect_gmail").disabled
    assert not any(field.key in ("input_gmail_client_id", "input_gmail_client_secret") for field in app.text_input)


def test_show_email_extended_metadata(monkeypatch):
    from inboxlearn.presentation import show_email
    captions = []
    texts = []
    expanders = []
    
    class DummyStreamlit:
        @staticmethod
        def caption(text):
            captions.append(text)
        @staticmethod
        def text(text):
            texts.append(text)
        @staticmethod
        def expander(label, expanded=False):
            expanders.append(label)
            class Ctx:
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return Ctx()

    monkeypatch.setattr("inboxlearn.presentation.st", DummyStreamlit)
    
    mock_row = {
        "id": 42,
        "status": "needs_review",
        "source_type": "eml",
        "date_header": "2026-09-23T08:00:00Z",
        "message_id": "<msg42@example.com>",
        "in_reply_to": "<prev@example.com>",
        "parser_warnings_json": '["Suspicious header", "Attachment skipped"]',
        "subject": "Invoice for services",
        "sender": "billing@corp.com",
        "body": "Please find attached the invoice."
    }
    show_email(mock_row)
    assert any("SOURCE: EML" in c for c in captions)
    assert any("DATE: 2026-09-23T08:00:00Z" in c for c in captions)
    assert any("Parser warnings (2)" in e for e in expanders)
    assert any("Technical headers" in e for e in expanders)
    assert any("Subject: Invoice for services" in t for t in texts)


def test_action_journal_service_and_ui_flow(workspace):
    from inboxlearn.demo import demo_data_path
    workspace.classify_upload(demo_data_path("demo_feedback.csv").read_bytes())
    inbox = workspace.repo.inbox_rows()
    email_id = inbox[0]["id"]

    # 1. Stage an action
    action_id = workspace.stage_action(email_id, "follow_up", {"description": "Follow up with sender"})
    actions = workspace.email_actions(email_id)
    assert len(actions) == 1
    assert actions[0]["status"] == "staged"
    assert actions[0]["action_type"] == "follow_up"

    # 2. Execute the action
    workspace.execute_action(action_id)
    actions = workspace.email_actions(email_id)
    assert actions[0]["status"] == "executed"
    assert actions[0]["executed_at"] is not None

    # 3. Revert the action
    workspace.revert_action(action_id)
    actions = workspace.email_actions(email_id)
    assert actions[0]["status"] == "reverted"

    # 4. Verify UI renders without errors when action journal is populated
    app = workspace_app()
    assert any("Action journal" in e.label for e in app.expander)


def test_inbox_table_source_and_date_columns(workspace):
    from inboxlearn.demo import demo_data_path
    workspace.classify_upload(demo_data_path("demo_feedback.csv").read_bytes())
    app = workspace_app()
    df = next(d.value for d in app.dataframe if "Subject" in d.value.columns)
    assert "Source" in df.columns
    assert "Date" in df.columns
    assert "CSV" in df["Source"].values



def test_daily_navigation_due_date_and_reopen(workspace):
    from datetime import date
    app = workspace_app()
    assert app.session_state['workspace_tabs'] == 'Today'
    app.button(key='today_demo').click().run()
    mid = workspace.review_rows(include_confident=True)[0]['id']
    aid = workspace.stage_action(mid, 'follow_up', {'description': 'Call sender'}, date.today())
    app.run()
    app.button(key=f'today_open_{aid}').click().run()
    assert_clean(app)
    assert app.session_state['workspace_tabs'] == 'Upload / Inbox'
    assert app.selectbox(key='read_email').value == mid
    app.button(key='review_from_inbox').click().run()
    assert app.session_state['workspace_tabs'] == 'Review queue'
    assert app.selectbox(key='review_email').value == mid
    app.button(key=f'today_{aid}_done').click().run()
    assert workspace.email_actions(mid)[0]['status'] == 'executed'
    app.button(key=f'today_{aid}_reopen').click().run()
    assert workspace.email_actions(mid)[0]['status'] == 'staged'


def test_save_next_respects_all_filters(workspace):
    from inboxlearn.demo import demo_data_path
    workspace.classify_upload(demo_data_path('demo_feedback.csv').read_bytes())
    with workspace.repo.training_transaction() as conn:
        conn.execute("UPDATE predictions SET category='bills', priority='high', status='needs_review'")
        conn.execute("UPDATE emails SET import_batch=CASE WHEN id IN (1,2) THEN 'selected' ELSE 'other' END")
    app = workspace_app()
    app.selectbox(key='review_cat_filter').select('bills').run()
    app.selectbox(key='review_pri_filter').select('high').run()
    app.selectbox(key='review_batch_filter').select('selected').run()
    expected = workspace.review_rows(category='bills', priority='high', import_batch='selected')
    for row in expected:
        assert app.selectbox(key='review_email').value == row['id']
        click(app, 'Save and next')
    assert any('Review complete' in x.value for x in app.success)
    assert len(workspace.repo.latest_feedback()) == 2
    assert not any(s.key == 'review_email' for s in app.selectbox)


def test_stale_batch_requires_refresh(workspace):
    from inboxlearn.demo import demo_data_path
    workspace.classify_upload(demo_data_path('demo_feedback.csv').read_bytes())
    app = workspace_app()
    app.checkbox(key='include_confident').check().run()
    app.multiselect(key='batch_confirm_selection').select(1).select(2).run()
    workspace.save_feedback(1, 'spam', 'high')
    app.button(key='btn_execute_batch_confirm').click().run()
    assert_clean(app)
    assert any('Refresh the preview' in e.value for e in app.error)
    assert len(workspace.repo.latest_feedback()) == 1
    app.button(key='refresh_batch').click().run()
    app.button(key='btn_execute_batch_confirm').click().run()
    assert_clean(app)
    assert len(workspace.repo.latest_feedback()) == 2
