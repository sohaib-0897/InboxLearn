from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from inboxlearn.service import InboxLearnService


APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.parametrize("view", [None, "landing", "unknown"])
def test_landing_renders_before_opening_a_workspace(tmp_path, monkeypatch, view):
    database = tmp_path / "untouched.sqlite3"
    monkeypatch.setenv("INBOXLEARN_DB", str(database))

    def forbidden_workspace(*args, **kwargs):
        pytest.fail("Viewing the landing page must not initialize the workspace")

    monkeypatch.setattr(InboxLearnService, "__init__", forbidden_workspace)
    app = AppTest.from_file(str(APP), default_timeout=20)
    if view is not None:
        app.query_params["view"] = view
    app.run()
    assert not app.exception
    assert not app.tabs
    document = app.get("html")[0].proto.body
    assert "Your inbox gets smarter with every correction." in document
    assert 'href="?view=workspace" target="_self"' in document
    assert "http://localhost:8501" not in document
    assert 'href="../' not in document
    assert "PREVIEW ONLY" in document
    assert not database.exists()


def test_workspace_can_return_to_landing_and_reopen(tmp_path, monkeypatch):
    database = tmp_path / "workspace.sqlite3"
    monkeypatch.setenv("INBOXLEARN_DB", str(database))
    app = AppTest.from_file(str(APP), default_timeout=20)
    app.query_params["view"] = "workspace"
    app.run()
    assert not app.exception
    assert "Upload / Inbox" in [tab.label for tab in app.tabs]
    app.button(key="demo_classify").click().run()
    assert not app.exception
    app.button(key="back_to_landing").click().run()
    assert not app.exception
    assert app.query_params["view"] == ["landing"]
    assert not app.tabs
    app.query_params["view"] = "workspace"
    app.run()
    assert not app.exception
    assert "Upload / Inbox" in [tab.label for tab in app.tabs]
    assert len(app.selectbox(key="read_email").options) == 5
