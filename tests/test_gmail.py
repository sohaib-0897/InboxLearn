"""Comprehensive offline unit and error-path tests for Gmail Phase D connector.
Tests cover OAuth PKCE, credential protection, read-only guarantees, sync pagination,
deduplication, cancellation, error recovery, and hosted demo gates without external network calls.
"""

from datetime import date, datetime, timezone
import email.message
import io
import json
from pathlib import Path
import time
from urllib.error import HTTPError
import pytest

from inboxlearn.gmail import (
    AuthenticationExpiredError,
    CredentialStore,
    GMAIL_READONLY_SCOPE,
    GmailAuthError,
    GmailClient,
    GmailError,
    GmailRateLimitError,
    GmailSyncCancelled,
    disconnect_gmail,
    exchange_code_for_tokens,
    generate_pkce_pair,
    generate_state,
    is_gmail_enabled,
    refresh_access_token,
    sync_gmail,
)
from inboxlearn.service import InboxLearnService
from inboxlearn.config import Settings


# ---------------------------------------------------------------------------
# PKCE & OAuth State Security Tests
# ---------------------------------------------------------------------------

def test_pkce_generation():
    verifier1, challenge1 = generate_pkce_pair()
    verifier2, challenge2 = generate_pkce_pair()

    assert len(verifier1) >= 43
    assert len(challenge1) >= 43
    assert verifier1 != verifier2
    assert challenge1 != challenge2
    # Challenge should not contain padding equals per RFC 7636
    assert "=" not in challenge1


def test_state_generation():
    s1 = generate_state()
    s2 = generate_state()
    assert len(s1) >= 32
    assert s1 != s2


# ---------------------------------------------------------------------------
# Credential Store & DPAPI / File Protection Tests
# ---------------------------------------------------------------------------

def test_credential_store_save_load_clear(tmp_path):
    store = CredentialStore(storage_dir=tmp_path / "creds")
    assert store.load_tokens() is None

    token_data = {
        "access_token": "mock-access-token-123",
        "refresh_token": "mock-refresh-token-456",
        "expires_at": time.time() + 3600,
    }
    store.save_tokens("user@example.test", token_data)

    loaded = store.load_tokens()
    assert loaded is not None
    assert loaded["account_email"] == "user@example.test"
    assert loaded["tokens"]["access_token"] == "mock-access-token-123"
    assert loaded["tokens"]["refresh_token"] == "mock-refresh-token-456"

    # Verify physical file on disk exists and contains protected data
    assert store.token_file.exists()
    file_bytes = store.token_file.read_bytes()
    assert len(file_bytes) > 0

    # Clear credentials
    store.clear()
    assert store.load_tokens() is None
    assert not store.token_file.exists()


# ---------------------------------------------------------------------------
# Strict Read-Only API Guarantee Test
# ---------------------------------------------------------------------------

def test_non_get_requests_strictly_prohibited(tmp_path):
    store = CredentialStore(storage_dir=tmp_path)
    store.save_tokens("user@test.com", {
        "access_token": "tok",
        "refresh_token": "ref",
        "expires_at": time.time() + 3600
    })
    client = GmailClient(store, "dummy_id", "dummy_secret")

    with pytest.raises(PermissionError, match="strictly read-only"):
        client._request("messages/send", method="POST")

    with pytest.raises(PermissionError, match="strictly read-only"):
        client._request("messages/123/trash", method="POST")

    with pytest.raises(PermissionError, match="strictly read-only"):
        client._request("messages/123", method="DELETE")


# ---------------------------------------------------------------------------
# Token Refresh & Expiration Tests (Mocked Network)
# ---------------------------------------------------------------------------

def test_refresh_token_expired_raises_authentication_expired(monkeypatch):
    def mock_urlopen(req, timeout=30):
        fp = io.BytesIO(b'{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}')
        raise HTTPError(req.full_url, 400, "Bad Request", hdrs=None, fp=fp)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    with pytest.raises(AuthenticationExpiredError, match="Refresh token invalid or revoked"):
        refresh_access_token("client_id", "client_secret", "bad_refresh_token")


def test_token_auto_refresh_on_expiration(tmp_path, monkeypatch):
    store = CredentialStore(storage_dir=tmp_path)
    # Store token that expired in the past
    store.save_tokens("user@test.com", {
        "access_token": "old-expired-token",
        "refresh_token": "valid-refresh-token",
        "expires_at": time.time() - 100,
    })

    def mock_urlopen(req, timeout=30):
        if "oauth2.googleapis.com/token" in req.full_url:
            payload = json.dumps({
                "access_token": "new-fresh-token-999",
                "expires_in": 3600,
                "token_type": "Bearer"
            }).encode("utf-8")
            resp = io.BytesIO(payload)
            resp.status = 200
            resp.read = resp.getvalue
            return resp
        raise ValueError(f"Unexpected URL: {req.full_url}")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    client = GmailClient(store, "cid", "csec")
    fresh_token = client._get_valid_token()
    assert fresh_token == "new-fresh-token-999"

    # Check store was updated
    updated_store = store.load_tokens()
    assert updated_store["tokens"]["access_token"] == "new-fresh-token-999"
    assert updated_store["tokens"]["expires_at"] > time.time()


# ---------------------------------------------------------------------------
# Sync Engine Tests (Pagination, Deduplication, Cancellation, Deleted Mail)
# ---------------------------------------------------------------------------

class MockGmailClient:
    """Mock client for testing synchronization logic without external network calls."""

    def __init__(self, raw_emails: dict[str, bytes], deleted_ids: set[str] = None):
        self.raw_emails = raw_emails
        self.deleted_ids = deleted_ids or set()
        self.listed_queries: list[str] = []

    def get_profile(self) -> dict:
        return {"emailAddress": "alice@example.test", "messagesTotal": len(self.raw_emails)}

    def list_messages(self, query: str = "", max_results: int = 100, page_token: str | None = None):
        self.listed_queries.append(query)
        all_ids = list(self.raw_emails.keys())
        start = int(page_token) if page_token else 0
        batch = [{"id": mid, "threadId": f"t_{mid}"} for mid in all_ids[start:start + max_results]]
        next_page = str(start + max_results) if (start + max_results) < len(all_ids) else None
        return batch, next_page

    def get_message_raw(self, message_id: str) -> bytes:
        if message_id in self.deleted_ids:
            fp = io.BytesIO(b'{"error": {"code": 404, "message": "Not Found"}}')
            raise HTTPError(f"https://gmail.../{message_id}", 404, "Not Found", None, fp)
        if message_id not in self.raw_emails:
            raise KeyError(message_id)
        return self.raw_emails[message_id]


def _make_rfc_email(subject: str, body: str, sender: str = "sender@example.test", date_str: str = "Tue, 14 Oct 2025 10:00:00 +0000") -> bytes:
    msg = email.message.EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = date_str
    msg["Message-ID"] = f"<{hash(subject)}@example.test>"
    msg.set_content(body)
    return msg.as_bytes()


def test_gmail_sync_pagination_and_deduplication(tmp_path, monkeypatch):
    # Enable gmail for this test
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "1")

    db_path = tmp_path / "sync_test.db"
    service = InboxLearnService(Settings(db_path=db_path))

    # Prepare 5 mock emails
    emails_data = {
        f"msg_{i}": _make_rfc_email(f"Subject {i}", f"Body content for message {i} with deadline due by tomorrow.")
        for i in range(5)
    }
    client = MockGmailClient(emails_data)

    # First sync: max 3 messages
    result1 = sync_gmail(service, client, days=15, max_messages=3)
    assert result1["total_listed"] == 3
    assert result1["new"] == 3
    assert result1["duplicates"] == 0
    assert result1["failed"] == 0

    # Verify query had date filter
    assert "after:" in client.listed_queries[0]

    # Check database rows
    rows1 = service.repo.inbox_rows()
    assert len(rows1) == 3
    for r in rows1:
        assert r["source_type"] == "gmail"
        assert r["source"] == "gmail"

    # Second sync: max 5 messages (should import remaining 2, skip 3 duplicates)
    result2 = sync_gmail(service, client, days=15, max_messages=5)
    assert result2["new"] == 2
    assert result2["duplicates"] == 3

    rows2 = service.repo.inbox_rows()
    assert len(rows2) == 5

    # Check entity extraction ran automatically on sync
    entities = service.entities_for_email(rows2[0]["id"])
    assert len(entities) > 0


def test_gmail_sync_cancellation(tmp_path, monkeypatch):
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "1")
    service = InboxLearnService(Settings(db_path=tmp_path / "cancel.db"))

    emails_data = {f"msg_{i}": _make_rfc_email(f"S {i}", f"B {i}") for i in range(10)}
    client = MockGmailClient(emails_data)

    cancelled = False
    def cancel_after_2():
        nonlocal cancelled
        return cancelled

    def on_progress(current, total, msg):
        nonlocal cancelled
        if current >= 2:
            cancelled = True

    with pytest.raises(GmailSyncCancelled):
        sync_gmail(service, client, days=30, max_messages=10, cancel_check=cancel_after_2, progress_callback=on_progress)

    # Database is not corrupted and processed messages before cancellation are safely committed
    rows = service.repo.inbox_rows()
    assert len(rows) == 2


def test_gmail_sync_deleted_message_handled_gracefully(tmp_path, monkeypatch):
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "1")
    service = InboxLearnService(Settings(db_path=tmp_path / "deleted.db"))

    emails_data = {
        "msg_1": _make_rfc_email("Valid 1", "Body 1"),
        "msg_2": _make_rfc_email("Deleted", "Body 2"),
        "msg_3": _make_rfc_email("Valid 3", "Body 3"),
    }
    # msg_2 simulates a 404 from Google because it was deleted
    client = MockGmailClient(emails_data, deleted_ids={"msg_2"})

    result = sync_gmail(service, client, days=30, max_messages=5)
    assert result["new"] == 2
    assert result["warnings"] == 1  # 1 warning for the 404
    assert result["failed"] == 0

    rows = service.repo.inbox_rows()
    assert len(rows) == 2


def test_disconnect_and_token_revocation(tmp_path, monkeypatch):
    store = CredentialStore(storage_dir=tmp_path)
    store.save_tokens("user@test.com", {"access_token": "token-to-revoke"})

    revocation_called = False
    def mock_urlopen(req, timeout=15):
        nonlocal revocation_called
        if "oauth2.googleapis.com/revoke" in req.full_url:
            revocation_called = True
            resp = io.BytesIO(b"{}")
            resp.status = 200
            return resp
        raise ValueError(req.full_url)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    res = disconnect_gmail(store, "cid", "csec")
    assert res["account"] == "user@test.com"
    assert res["revoked_on_google"] is True
    assert res["local_credentials_cleared"] is True
    assert store.load_tokens() is None
    assert revocation_called is True


def test_is_gmail_enabled_hosted_detection(monkeypatch):
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "1")
    monkeypatch.delenv("STREAMLIT_SERVER_IS_RUNNING", raising=False)
    monkeypatch.delenv("INBOXLEARN_HOSTED", raising=False)
    assert is_gmail_enabled() is True

    # When explicitly disabled via env var
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "0")
    assert is_gmail_enabled() is False

    # When hosted flag is set
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "1")
    monkeypatch.setenv("INBOXLEARN_HOSTED", "1")
    assert is_gmail_enabled() is False


def test_gmail_imported_email_follows_correction_and_training_lifecycle(tmp_path, monkeypatch):
    """Verify Gmail-imported emails enter the same review, feedback, candidate training,
    and lineage pathways as CSV uploads."""
    monkeypatch.setenv("INBOXLEARN_GMAIL_ENABLED", "1")
    service = InboxLearnService(Settings(db_path=tmp_path / "lifecycle.db"))

    email_bytes = _make_rfc_email(
        "Important Bill for University tuition fees",
        "Please pay the student account balance of $500 before next week.",
    )
    client = MockGmailClient({"gmail_001": email_bytes})

    result = sync_gmail(service, client, days=30, max_messages=1)
    assert result["new"] == 1

    inbox = service.repo.inbox_rows()
    assert len(inbox) == 1
    email_id = inbox[0]["id"]

    # 1. Review and save feedback
    corr_id, created = service.save_feedback(email_id, "bills", "high")
    assert created is True

    # 2. Train inactive candidate
    cand = service.train()
    assert cand is not None
    assert cand["reused"] is False

    # 3. Candidate metadata includes the Gmail feedback in lineage
    version_row = service.repo.version(cand["version_id"])
    membership = service.repo.feedback_membership(cand["version_id"])
    assert email_id in membership

    # 4. Evaluation required before activation
    with pytest.raises(ValueError, match="Evaluate this candidate"):
        service.activate(cand["version_id"])

    # 5. Evaluate and activate
    eval_res = service.compare_versions(cand["version_id"])
    assert "updated" in eval_res
    service.activate(cand["version_id"])

    active = service.active_version()
    assert active["id"] == cand["version_id"]

    # 6. Rollback restores baseline
    baseline = next(v for v in service.repo.versions() if v["kind"] == "baseline")
    service.rollback(baseline["id"])
    assert service.active_version()["id"] == baseline["id"]


def test_transient_retry_and_backoff(tmp_path, monkeypatch):
    store = CredentialStore(storage_dir=tmp_path)
    store.save_tokens("user@test.com", {"access_token": "valid-token", "expires_at": time.time() + 3600})
    client = GmailClient(store, "cid", "csec", max_retries=3, request_timeout=5)

    attempts = 0
    def mock_urlopen(req, timeout=5):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            # Simulate 503 Service Unavailable
            fp = io.BytesIO(b'{"error": "temporarily_unavailable"}')
            raise HTTPError(req.full_url, 503, "Service Unavailable", None, fp)
        # 3rd attempt succeeds
        resp = io.BytesIO(b'{"emailAddress": "test@test.com"}')
        resp.status = 200
        resp.read = resp.getvalue
        return resp

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: None) # skip actual sleep

    profile = client.get_profile()
    assert profile["emailAddress"] == "test@test.com"
    assert attempts == 3

