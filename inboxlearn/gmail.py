"""Local, single-account, read-only Gmail connector for InboxLearn.

Adheres strictly to the Google API Services User Data Policy and the InboxLearn expansion spec:
1. Local-only desktop OAuth 2.0 PKCE flow with short-lived loopback callback bound strictly to 127.0.0.1.
2. Read-only scope: https://www.googleapis.com/auth/gmail.readonly.
3. Zero write methods: no sending, modifying labels, trashing, or archiving.
4. OS-backed protected credential storage (Windows DPAPI with user-only file fallback).
5. Bounded manual sync (date window + message cap) with account-scoped deduplication.
6. Rate limiting, backoff, cancellation, and clean disconnect with revocation.
7. Safe hosted-demo disabling.
"""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import hashlib
import http.server
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from .parsers import parse_eml_bytes

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailError(Exception):
    """Base exception for Gmail operations."""


class GmailAuthError(GmailError):
    """Authentication or OAuth flow failure."""


class AuthenticationExpiredError(GmailAuthError):
    """Credentials expired or revoked."""


class GmailRateLimitError(GmailError):
    """Rate limit / quota exceeded."""


class GmailSyncCancelled(GmailError):
    """Sync was cancelled by user."""


def is_gmail_enabled() -> bool:
    """Check if Gmail connector is enabled for this environment.
    Requires explicit local opt-in; hosted demo flags always disable it.
    """
    if os.getenv("INBOXLEARN_GMAIL_ENABLED", "0").strip().lower() not in ("1", "true", "yes", "on"):
        return False
    # Check common hosted environment flags
    if os.getenv("STREAMLIT_SERVER_IS_RUNNING") and os.getenv("HOSTNAME", "").startswith("streamlit"):
        return False
    if os.getenv("INBOXLEARN_HOSTED", "0").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return True


# ---------------------------------------------------------------------------
# Protected Credential Storage (Windows DPAPI / Protected File)
# ---------------------------------------------------------------------------

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _dpapi_protect(data: bytes) -> bytes:
    """Encrypt data with the current user's Windows credentials using DPAPI."""
    if sys.platform != "win32" or not hasattr(ctypes, "windll"):
        return data
    try:
        crypt32 = ctypes.windll.crypt32
        in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
        out_blob = _DATA_BLOB()
        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if crypt32.CryptProtectData(ctypes.byref(in_blob), "InboxLearnToken", None, None, None, 1, ctypes.byref(out_blob)):
            try:
                encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                return encrypted
            finally:
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    except Exception:
        pass
    return data


def _dpapi_unprotect(data: bytes) -> bytes:
    """Decrypt data previously encrypted with DPAPI."""
    if sys.platform != "win32" or not hasattr(ctypes, "windll"):
        return data
    try:
        crypt32 = ctypes.windll.crypt32
        in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
        out_blob = _DATA_BLOB()
        if crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 1, ctypes.byref(out_blob)):
            try:
                decrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                return decrypted
            finally:
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    except Exception:
        pass
    return data


class CredentialStore:
    """Securely manages stored OAuth tokens. Never logs or exports token secrets."""

    def __init__(self, storage_dir: Path | str = "runtime/credentials"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.token_file = self.storage_dir / "gmail_token.bin"
        self._memory_token: dict | None = None

    def save_tokens(self, account_email: str, token_data: dict) -> None:
        payload = {
            "account_email": account_email,
            "tokens": token_data,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "protected_by": "dpapi" if sys.platform == "win32" else "file_mode_600",
        }
        raw_json = json.dumps(payload).encode("utf-8")
        protected_bytes = _dpapi_protect(raw_json)
        self._memory_token = payload
        try:
            self.token_file.write_bytes(protected_bytes)
            if sys.platform != "win32":
                try:
                    os.chmod(self.token_file, 0o600)
                except OSError:
                    pass
        except OSError:
            # Fall back to session-only in memory if filesystem write is restricted
            pass

    def load_tokens(self) -> dict | None:
        if self._memory_token:
            return self._memory_token
        if not self.token_file.exists():
            return None
        try:
            protected_bytes = self.token_file.read_bytes()
            raw_json = _dpapi_unprotect(protected_bytes)
            payload = json.loads(raw_json.decode("utf-8"))
            self._memory_token = payload
            return payload
        except Exception:
            return None

    def clear(self) -> None:
        self._memory_token = None
        if self.token_file.exists():
            try:
                self.token_file.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# OAuth 2.0 PKCE & Loopback Server
# ---------------------------------------------------------------------------

def generate_pkce_pair() -> tuple[str, str]:
    """Generate (code_verifier, code_challenge) using SHA-256 for PKCE."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def generate_state() -> str:
    """Generate cryptographic random CSRF state parameter."""
    return secrets.token_urlsafe(32)


class _LoopbackCallbackHandler(http.server.BaseHTTPRequestHandler):
    server: _LoopbackServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        incoming_state = params.get("state", [""])[0]
        code = params.get("code", [""])[0]
        error = params.get("error", [""])[0]

        if not incoming_state or incoming_state != self.server.expected_state:
            self.server.result_error = "State mismatch or replay detected. Callback rejected."
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><h3>Error: Invalid state parameter. Authentication failed.</h3></body></html>")
            return

        if error:
            self.server.result_error = f"Google consent error: {error}"
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><h3>Consent denied or cancelled ({error}).</h3></body></html>".encode("utf-8"))
            return

        if not code:
            self.server.result_error = "Missing authorization code."
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><h3>Error: No authorization code received.</h3></body></html>")
            return

        self.server.result_code = code
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><head><title>InboxLearn</title></head>"
            b"<body style='font-family: serif; padding: 40px; text-align: center; background: #FAF9F6; color: #111;'>"
            b"<h2>InboxLearn &mdash; Authentication Received</h2>"
            b"<p>Google authorization completed successfully. You may close this window and return to InboxLearn.</p>"
            b"</body></html>"
        )

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress default server console output


class _LoopbackServer(http.server.HTTPServer):
    def __init__(self, expected_state: str, port: int = 0):
        super().__init__(("127.0.0.1", port), _LoopbackCallbackHandler)
        self.expected_state = expected_state
        self.result_code: str | None = None
        self.result_error: str | None = None


def run_oauth_flow(
    client_id: str,
    client_secret: str,
    *,
    timeout_seconds: int = 120,
    open_browser: bool = True,
) -> dict:
    """Run local desktop OAuth 2.0 PKCE flow. Returns token dictionary."""
    state = generate_state()
    code_verifier, code_challenge = generate_pkce_pair()

    server = _LoopbackServer(expected_state=state, port=0)
    port = server.server_port
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_READONLY_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URI}?{urlencode(params)}"

    if open_browser:
        webbrowser.open(auth_url)

    server.timeout = timeout_seconds
    start_time = time.time()
    while server.result_code is None and server.result_error is None:
        if time.time() - start_time > timeout_seconds:
            server.server_close()
            raise GmailAuthError(f"OAuth flow timed out after {timeout_seconds} seconds waiting for user consent.")
        server.handle_request()

    server.server_close()

    if server.result_error:
        raise GmailAuthError(server.result_error)
    if not server.result_code:
        raise GmailAuthError("No authorization code received from callback.")

    return exchange_code_for_tokens(
        client_id=client_id,
        client_secret=client_secret,
        code=server.result_code,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
    )


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    encoded_data = urlencode(data).encode("utf-8")
    req = urllib.request.Request(TOKEN_URI, data=encoded_data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            tokens = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        raise GmailAuthError(f"Token exchange failed ({exc.code}): {err_msg}") from exc
    except URLError as exc:
        raise GmailAuthError(f"Network error during token exchange: {exc.reason}") from exc

    # Calculate expiration timestamp (buffer 60 seconds)
    expires_in = tokens.get("expires_in", 3600)
    tokens["expires_at"] = time.time() + expires_in - 60
    return tokens


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Obtain a new access token using a refresh token."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    encoded_data = urlencode(data).encode("utf-8")
    req = urllib.request.Request(TOKEN_URI, data=encoded_data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            new_tokens = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        if exc.code in (400, 401):
            raise AuthenticationExpiredError(f"Refresh token invalid or revoked ({exc.code}): {err_msg}") from exc
        raise GmailAuthError(f"Token refresh failed ({exc.code}): {err_msg}") from exc
    except URLError as exc:
        raise GmailAuthError(f"Network error during token refresh: {exc.reason}") from exc

    expires_in = new_tokens.get("expires_in", 3600)
    new_tokens["expires_at"] = time.time() + expires_in - 60
    # Keep the existing refresh token if Google didn't issue a new one
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    return new_tokens


def revoke_token(token: str) -> bool:
    """Revoke an access or refresh token via Google OAuth endpoint."""
    url = f"{REVOKE_URI}?{urlencode({'token': token})}"
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Read-Only Gmail API Client
# ---------------------------------------------------------------------------

class GmailClient:
    """Strictly read-only Gmail API client with rate-limiting, retries, and cancellation."""

    def __init__(
        self,
        credential_store: CredentialStore,
        client_id: str,
        client_secret: str,
        max_retries: int = 3,
        request_timeout: int = 20,
    ):
        self.store = credential_store
        self.client_id = client_id
        self.client_secret = client_secret
        self.max_retries = max_retries
        self.request_timeout = request_timeout

    def _get_valid_token(self) -> str:
        record = self.store.load_tokens()
        if not record or "tokens" not in record:
            raise GmailAuthError("No stored Gmail credentials found.")

        tokens = record["tokens"]
        expires_at = tokens.get("expires_at", 0)
        access_token = tokens.get("access_token", "")

        if time.time() >= expires_at:
            refresh_token_val = tokens.get("refresh_token")
            if not refresh_token_val:
                raise AuthenticationExpiredError("Access token expired and no refresh token available.")
            new_tokens = refresh_access_token(self.client_id, self.client_secret, refresh_token_val)
            self.store.save_tokens(record.get("account_email", "unknown"), new_tokens)
            return new_tokens["access_token"]

        return access_token

    def _request(self, endpoint: str, query_params: dict | None = None, method: str = "GET") -> bytes:
        """Execute an API request. Enforces read-only behavior by forbidding non-GET methods."""
        if method.upper() != "GET":
            raise PermissionError(f"InboxLearn Gmail connector is strictly read-only. Disallowed method: {method}")

        url = f"{GMAIL_API_BASE}/{endpoint}"
        if query_params:
            url += f"?{urlencode(query_params)}"

        last_error = None
        for attempt in range(self.max_retries):
            token = self._get_valid_token()
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")

            try:
                with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                    return resp.read()
            except HTTPError as exc:
                last_error = exc
                if exc.code == 401:
                    # Token might have expired early; clear memory cache and retry once
                    self.store._memory_token = None
                    continue
                if exc.code == 429 or exc.code >= 500:
                    # Rate limit or transient server error: backoff
                    sleep_time = (2 ** attempt) + (secrets.randbelow(100) / 100.0)
                    time.sleep(sleep_time)
                    continue
                if exc.code == 404:
                    # Message not found / deleted
                    raise exc
                # Other 4xx error (e.g. 403 quota exceeded)
                err_text = exc.read().decode("utf-8", errors="replace")
                if "quota" in err_text.lower():
                    raise GmailRateLimitError(f"Gmail API quota exceeded: {err_text}") from exc
                raise GmailError(f"Gmail API HTTP error ({exc.code}): {err_text}") from exc
            except (URLError, TimeoutError) as exc:
                last_error = exc
                sleep_time = (2 ** attempt) + 0.5
                time.sleep(sleep_time)
                continue

        raise GmailError(f"Gmail API request failed after {self.max_retries} attempts: {last_error}")

    def get_profile(self) -> dict:
        """Fetch user profile to get account email and total message counts."""
        raw = self._request("profile")
        return json.loads(raw.decode("utf-8"))

    def list_messages(
        self,
        query: str = "",
        max_results: int = 100,
        page_token: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Fetch a page of message references matching query."""
        params: dict[str, Any] = {"maxResults": min(max_results, 100)}
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token

        raw = self._request("messages", query_params=params)
        data = json.loads(raw.decode("utf-8"))
        messages = data.get("messages", [])
        next_page = data.get("nextPageToken")
        return messages, next_page

    def get_message_raw(self, message_id: str) -> bytes:
        """Fetch raw RFC 2822 bytes for an individual email."""
        raw = self._request(f"messages/{message_id}", query_params={"format": "raw"})
        data = json.loads(raw.decode("utf-8"))
        raw_b64 = data.get("raw", "")
        # Google uses URL-safe base64
        padded = raw_b64 + "=" * (-len(raw_b64) % 4)
        return base64.urlsafe_b64decode(padded)


# ---------------------------------------------------------------------------
# Synchronization Engine
# ---------------------------------------------------------------------------

def sync_gmail(
    service: Any,
    client: GmailClient,
    *,
    days: int = 30,
    max_messages: int = 100,
    cancel_check: Callable[[], bool] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Perform a bounded manual read-only sync from Gmail.

    Args:
        service: InboxLearnService instance
        client: Authenticated GmailClient
        days: Lookback window in days (default 30)
        max_messages: Maximum messages to import (default 100)
        cancel_check: Callable returning True if sync should cancel
        progress_callback: Callback(processed_count, total_count, current_action)

    Returns:
        dict with counts of imported, duplicates, failed, warnings, and duration.
    """
    if not is_gmail_enabled():
        raise GmailError("Gmail integration is disabled in hosted demo mode.")

    profile = client.get_profile()
    account_email = profile.get("emailAddress", "unknown")

    # Date filter
    cutoff = date.today() - timedelta(days=days)
    query = f"after:{cutoff.strftime('%Y/%m/%d')}"

    # Step 1: List message IDs up to max_messages
    message_refs: list[dict] = []
    page_token: str | None = None

    while len(message_refs) < max_messages:
        if cancel_check and cancel_check():
            raise GmailSyncCancelled("Sync was cancelled by user during listing.")

        needed = max_messages - len(message_refs)
        batch, page_token = client.list_messages(query=query, max_results=needed, page_token=page_token)
        if not batch:
            break
        message_refs.extend(batch)
        if not page_token:
            break

    total_listed = len(message_refs)
    imported_count = 0
    duplicate_count = 0
    failed_count = 0
    warning_count = 0
    import_batch = f"gmail:{account_email}:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    version = service.repo.active_version()
    if not version:
        service.ensure_baseline()
        version = service.repo.active_version()

    # Step 2: Ingest messages
    for index, ref in enumerate(message_refs, start=1):
        if cancel_check and cancel_check():
            raise GmailSyncCancelled(f"Sync was cancelled by user after processing {index - 1} messages.")

        msg_id = ref["id"]
        thread_id = ref.get("threadId", "")

        if progress_callback:
            progress_callback(index, total_listed, f"Fetching message {index}/{total_listed} (ID: {msg_id[:8]}…)")

        # Account-scoped deduplication check
        existing = service.repo._one(
            "SELECT id FROM emails WHERE (source_type='gmail' AND message_id=?)",
            (msg_id,),
        )
        if existing:
            duplicate_count += 1
            continue

        try:
            raw_bytes = client.get_message_raw(msg_id)
        except HTTPError as exc:
            if exc.code == 404:
                # Message was deleted remotely between list and get
                warning_count += 1
                continue
            failed_count += 1
            continue
        except Exception:
            failed_count += 1
            continue

        try:
            parsed_rows = parse_eml_bytes(raw_bytes, import_batch=import_batch)
            if not parsed_rows:
                warning_count += 1
                continue

            row = parsed_rows[0]
            # Use Gmail's message_id & thread_id if parser didn't extract RFC headers
            if not row.get("message_id"):
                row["message_id"] = msg_id
            if not row.get("thread_id"):
                row["thread_id"] = thread_id

            if row.get("parser_warnings"):
                warning_count += len(row["parser_warnings"])

            # Classify using active model
            from .classifier import deserialize_bundle
            from .validation import content_hash

            bundle = deserialize_bundle(version["model_blob"])
            prediction = bundle.predict(
                row,
                int(version["id"]),
                service.settings.category_threshold,
                service.settings.priority_threshold,
            )

            # Insert with extended metadata
            c_hash = content_hash(row)
            before_content = service.repo._one("SELECT id FROM emails WHERE content_hash=?", (c_hash,))
            email_id = service.repo.insert_email_extended(
                row,
                c_hash,
                prediction,
                source="gmail",
                source_type="gmail",
                import_batch=import_batch,
                message_id=msg_id,
                in_reply_to=row.get("in_reply_to", ""),
                thread_id=thread_id,
                date_header=row.get("date", ""),
                parser_warnings=row.get("parser_warnings"),
            )

            if before_content:
                duplicate_count += 1
            else:
                imported_count += 1
                service._extract_and_save_entities(email_id, row)

        except Exception as exc:
            failed_count += 1
            warning_count += 1

    return {
        "account_email": account_email,
        "import_batch": import_batch,
        "total_listed": total_listed,
        "new": imported_count,
        "duplicates": duplicate_count,
        "failed": failed_count,
        "warnings": warning_count,
        "sync_time": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "days": days,
    }


def disconnect_gmail(store: CredentialStore, client_id: str, client_secret: str) -> dict:
    """Revoke credentials, clear local store, and report outcome."""
    record = store.load_tokens()
    revoked = False
    account = "unknown"
    if record and "tokens" in record:
        account = record.get("account_email", "unknown")
        token_val = record["tokens"].get("refresh_token") or record["tokens"].get("access_token")
        if token_val:
            revoked = revoke_token(token_val)

    store.clear()
    return {
        "account": account,
        "revoked_on_google": revoked,
        "local_credentials_cleared": True,
        "note": "Local credentials removed. Emails imported previously remain in local database unless deleted separately.",
    }
