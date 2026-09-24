"""Native Streamlit presentation over the existing InboxLearn service."""
import importlib
import inspect
import json
import sys
import uuid
from datetime import date, datetime, time as dt_time
from math import ceil
from pathlib import Path


import pandas as pd
import streamlit as st

from inboxlearn.config import CATEGORIES, PRIORITIES, Settings
from inboxlearn.calendar_export import (
    create_event, event_to_ics_bytes, download_filename, SUPPORTED_TIMEZONES
)
from inboxlearn.demo import demo_data_path, load_demo_rows
from inboxlearn.entities import ExtractedEntity
from inboxlearn.service import InboxLearnService
from inboxlearn.presentation import (
    apply_newsprint, masthead, status_strip, section, show_email,
    original_prediction, comparison, metric_rows, flash, show_flash, STATUS_LABELS,
)

st.set_page_config(page_title="InboxLearn", page_icon="✉", layout="wide", initial_sidebar_state="collapsed")

APP_VERSION = "2.3.3"


def _safe_review_rows(service: InboxLearnService, **kwargs) -> list[dict]:
    """Call service.review_rows safely, adapting to any cached or legacy signature."""
    try:
        sig = inspect.signature(service.review_rows)
        has_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        accepted = {k: v for k, v in kwargs.items() if has_var_kwargs or k in sig.parameters}
        rows = service.review_rows(**accepted)
    except TypeError:
        fallback_kwargs = {k: v for k, v in kwargs.items() if k in ("include_confident", "order")}
        rows = service.review_rows(**fallback_kwargs)
        accepted = fallback_kwargs

    if "category" not in accepted and "category" in kwargs and kwargs["category"] != "All categories":
        rows = [r for r in rows if r.get("effective_category", r.get("category")) == kwargs["category"]]
    if "priority" not in accepted and "priority" in kwargs and kwargs["priority"] != "All priorities":
        rows = [r for r in rows if r.get("effective_priority", r.get("priority")) == kwargs["priority"]]
    if "import_batch" not in accepted and "import_batch" in kwargs and kwargs["import_batch"] != "All batches":
        rows = [r for r in rows if r.get("import_batch") == kwargs["import_batch"]]
    if "unresolved" not in accepted and kwargs.get("unresolved"):
        rows = [r for r in rows if r.get("feedback_id") is None]
    return rows


if "category" not in inspect.signature(InboxLearnService.review_rows).parameters:
    InboxLearnService.review_rows = _safe_review_rows

if not hasattr(InboxLearnService, "stage_action"):
    InboxLearnService.stage_action = lambda self, email_id, action_type, payload=None, due_date=None: self.repo.save_action(email_id, action_type, payload or {}, str(due_date) if due_date else None)
    InboxLearnService.execute_action = lambda self, action_id: self.repo.execute_action(action_id)
    InboxLearnService.revert_action = lambda self, action_id: self.repo.revert_action(action_id)
    InboxLearnService.email_actions = lambda self, email_id: [dict(r) for r in self.repo.actions_for_email(email_id)]

if not hasattr(InboxLearnService, "follow_ups"):
    def _fallback_follow_ups(self, *, today=None):
        today_str = (today or date.today()).isoformat()
        try:
            rows = [dict(r) for r in self.repo._all("""SELECT a.*, e.subject, e.sender FROM action_journal a
                JOIN emails e ON e.id=a.email_id ORDER BY a.due_date IS NULL, a.due_date, a.id""")]
            for row in rows:
                due = row.get('due_date')
                row['group'] = ('History' if row.get('status') != 'staged' else 'No due date' if not due
                                else 'Overdue' if due < today_str else 'Today' if due == today_str else 'Upcoming')
            return rows
        except Exception:
            return []
    InboxLearnService.follow_ups = _fallback_follow_ups

if not hasattr(InboxLearnService, "reopen_action"):
    def _fallback_reopen(self, action_id: int):
        with self.repo.training_transaction() as conn:
            conn.execute("UPDATE action_journal SET status='staged', executed_at=NULL WHERE id=?", (action_id,))
    InboxLearnService.reopen_action = _fallback_reopen

if not hasattr(InboxLearnService, "edit_action_due_date"):
    def _fallback_edit_due(self, action_id: int, due_date=None):
        val = date.fromisoformat(str(due_date)).isoformat() if due_date is not None else None
        with self.repo.training_transaction() as conn:
            conn.execute("UPDATE action_journal SET due_date=? WHERE id=?", (val, action_id))
    InboxLearnService.edit_action_due_date = _fallback_edit_due


@st.cache_resource
def get_service(db_path: str, category_threshold: float, priority_threshold: float,
                max_upload_bytes: int = 5 * 1024 * 1024, max_rows: int = 1000,
                random_state: int = 42, version: str = APP_VERSION) -> InboxLearnService:
    return InboxLearnService(Settings(
        db_path=Path(db_path), category_threshold=category_threshold,
        priority_threshold=priority_threshold, max_upload_bytes=max_upload_bytes,
        max_rows=max_rows, random_state=random_state,
    ))


def _row_val(row, key, default=""):
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, IndexError, TypeError):
        return default


def classify(service, payload: bytes, filename: str = "", source="upload") -> None:
    try:
        with st.spinner("Validating and classifying messages…"):
            result = service.classify_email_file(payload, filename=filename, source=source)
        fmt_label = result.get("format", "csv").upper()
        msg = f"Classified {result['new']} new email(s) from {fmt_label}; {result['duplicates']} duplicate(s) skipped."
        if result.get("warnings"):
            msg += f" {result['warnings']} parser warning(s)."
        msg += f" Original predictions saved with model v{result['version_id']}."
        flash(msg)
    except Exception as exc:
        st.error(f"Could not classify: {exc}")


def message_label(row: dict) -> str:
    subject = " ".join(row["subject"].split())
    return f"#{row['id']} · {subject[:72]}{'…' if len(subject) > 72 else ''}"


def render_calendar_editor(row: dict, entities: list[dict], key_prefix: str, service: InboxLearnService | None = None) -> None:
    """Render extracted entities and an interactive form to confirm/edit dates and timezone before .ics export."""
    if not entities:
        return
    with st.expander(f"Extracted entities ({len(entities)})", expanded=False):
        for entity in entities:
            icon = {"deadline": "📅", "date_mention": "📆", "amount": "💰",
                    "action_item": "✅", "contact_email": "📧", "url": "🔗"}.get(entity["entity_type"], "📌")
            val_display = entity["entity_value"] or "(ambiguous/unresolved)"
            st.write(f"{icon} **{entity['entity_type']}**: {val_display}")
            if entity.get("source_phrase"):
                st.caption(f"From: \"{entity['source_phrase']}\"")

        # Calendar event confirmation/editing section
        date_entities = [e for e in entities if e["entity_type"] in ("deadline", "date_mention")]
        if date_entities:
            st.markdown("---")
            st.markdown("**Confirm & export calendar event (.ics)**")
            selected_phrase_idx = st.selectbox(
                "Source mention to schedule",
                range(len(date_entities)),
                format_func=lambda i: f"#{i+1}: {date_entities[i].get('source_phrase', '')[:50] or date_entities[i].get('entity_value', 'date')}",
                key=f"{key_prefix}_cal_select",
            )
            target_entity = date_entities[selected_phrase_idx]
            val = target_entity.get("entity_value", "")
            is_ambiguous = not val

            default_d = date.today()
            if val:
                try:
                    default_d = date.fromisoformat(val)
                except (ValueError, TypeError):
                    pass

            if is_ambiguous:
                st.info(f"The date phrase \"{target_entity.get('source_phrase', '')}\" is ambiguous. Please confirm the exact date below.")

            c1, c2 = st.columns(2)
            with c1:
                ev_title = st.text_input("Event title", value=f"{row['category'].title()}: {row['subject'][:55]}", key=f"{key_prefix}_ev_title")
                ev_date = st.date_input("Event date", value=default_d, key=f"{key_prefix}_ev_date")
                all_day = st.checkbox("All-day event", value=True, key=f"{key_prefix}_ev_allday")
            with c2:
                ev_time = st.time_input("Start time", value=dt_time(9, 0), disabled=all_day, key=f"{key_prefix}_ev_time")
                ev_tz = st.selectbox("Timezone", SUPPORTED_TIMEZONES, index=0, key=f"{key_prefix}_ev_tz")
                ev_loc = st.text_input("Location (optional)", value="", key=f"{key_prefix}_ev_loc")

            ev_desc = st.text_area(
                "Event description",
                value=f"InboxLearn email #{row['id']}: {row['subject']}\nFrom: {row.get('sender', '')}\n\nExtracted phrase: {target_entity.get('source_phrase', '')}",
                key=f"{key_prefix}_ev_desc",
            )

            try:
                if all_day:
                    dtstart = ev_date
                else:
                    from zoneinfo import ZoneInfo
                    dtstart = datetime.combine(ev_date, ev_time, tzinfo=ZoneInfo(ev_tz))

                event = create_event(
                    summary=ev_title or row["subject"],
                    dtstart=dtstart,
                    description=ev_desc,
                    location=ev_loc,
                    email_id=int(row["id"]),
                    source_phrase=target_entity.get("source_phrase", ""),
                    timezone_name=ev_tz,
                )
                ics_data = event_to_ics_bytes(event)
                c_dl, c_log = st.columns([2, 1])
                with c_dl:
                    st.download_button(
                        label=f"📅 Download confirmed .ics file",
                        data=ics_data,
                        file_name=download_filename(event),
                        mime="text/calendar",
                        key=f"{key_prefix}_btn_ics_dl",
                    )
                with c_log:
                    if service and st.button("Log to journal", key=f"{key_prefix}_btn_log_cal"):
                        service.stage_action(int(row["id"]), "calendar_event", {
                            "description": f"Schedule calendar event: {event.summary} on {event.dtstart}",
                            "summary": event.summary,
                            "dtstart": str(event.dtstart),
                        })
                        flash(f"Logged calendar event '{event.summary}' in Action Journal.")
            except Exception as exc:
                st.error(f"Cannot generate .ics: {exc}")


def open_message(email_id: int, tab: str) -> None:
    st.session_state["workspace_tabs"] = tab
    if tab == "Review queue":
        st.session_state.update(include_confident=True, review_cat_filter="All categories",
                                review_pri_filter="All priorities", review_batch_filter="All batches",
                                next_review_email=email_id)
    else:
        st.session_state.update(inbox_search="", inbox_category="All categories", inbox_priority="All priorities",
                                inbox_status="All statuses", inbox_batch="All batches", read_email=email_id)


def action_controls(service, act, key):
    try:
        if act["status"] == "staged":
            done, cancel = st.columns(2)
            if done.button("Mark done", key=f"{key}_done"):
                service.execute_action(act["id"])
                flash("Follow-up marked done.")
            if cancel.button("Cancel", key=f"{key}_cancel"):
                service.revert_action(act["id"])
                flash("Follow-up cancelled.")
        elif st.button("Reopen", key=f"{key}_reopen"):
            service.reopen_action(act["id"])
            flash("Follow-up reopened.")
    except Exception as exc:
        st.error(f"Could not update follow-up: {exc}")


def render_today(service):
    section("00", "Today", "Your reviews and follow-ups, in one place.")
    if not service.repo.inbox_rows():
        st.info("Start by importing a CSV, .eml, or .mbox file in Upload / Inbox, or try the demonstration sample.")
        if st.button("Classify demonstration sample", key="today_demo"):
            classify(service, demo_data_path("demo_feedback.csv").read_bytes(), "demonstration")
        return
    pending = _safe_review_rows(service)
    st.subheader(f"Pending reviews ({len(pending)})")
    if not pending:
        st.caption("No uncertain messages await review.")
    for row in pending:
        st.button(message_label(row), key=f"today_review_{row['id']}", on_click=open_message,
                  args=(row["id"], "Review queue"))
    actions = service.follow_ups()
    for group in ("Overdue", "Today", "Upcoming", "No due date", "History"):
        items = [a for a in actions if a['group'] == group]
        with st.expander(f"{group} ({len(items)})", expanded=group != "History"):
            if not items:
                st.caption("Nothing here.")
            for act in items:
                payload = json.loads(act['payload_json'])
                st.write(payload.get('description') or payload.get('summary') or act['action_type'])
                st.caption(f"{act['sender']} | {act['subject']} | Due: {act['due_date'] or 'No due date'} | "
                           + {"staged": "Pending", "executed": "Done", "reverted": "Cancelled"}[act['status']])
                st.button("Open email", key=f"today_open_{act['id']}", on_click=open_message,
                          args=(act['email_id'], "Upload / Inbox"))
                action_controls(service, act, f"today_{act['id']}")


def render_action_journal(service: InboxLearnService, row: dict, key_prefix: str) -> None:
    email_id = int(row["id"])
    actions = service.email_actions(email_id)
    with st.expander(f"Action journal ({len(actions)})", expanded=bool(actions)):
        st.caption("Follow-ups are local records. Reminders appear when this workspace is open.")
        for act in actions:
            payload = json.loads(act['payload_json'])
            st.write(payload.get('description') or payload.get('summary') or act['action_type'])
            st.caption({"staged": "Pending", "executed": "Done", "reverted": "Cancelled"}[act['status']])
            action_controls(service, act, f"{key_prefix}_{act['id']}")
            with st.form(f"{key_prefix}_date_form_{act['id']}"):
                due = st.date_input("Due date (optional)", value=date.fromisoformat(act['due_date']) if act['due_date'] else None,
                                    key=f"{key_prefix}_date_{act['id']}")
                if st.form_submit_button("Save due date"):
                    try:
                        service.edit_action_due_date(act['id'], due)
                        flash("Due date saved.")
                    except Exception as exc:
                        st.error(f"Could not save due date: {exc}")
        # Key the default suggestion to the effective category so a correction updates it.
        action_desc = st.text_input("Action description", value=row.get('suggested_action', 'Review email content'),
                                   key=f"{key_prefix}_new_action_desc_{row.get('effective_category', '')}")
        action_type = st.selectbox("Action type", ["follow_up", "suggested_next", "archive", "calendar_event", "custom"], key=f"{key_prefix}_new_action_type")
        due = st.date_input("Due date (optional)", value=None, key=f"{key_prefix}_new_due")
        st.caption("Choose a date to confirm a deadline, or leave it empty. Extracted dates never create follow-ups automatically.")
        if st.button("Stage action", key=f"{key_prefix}_btn_stage_action"):
            try:
                if not action_desc.strip():
                    raise ValueError("Please provide an action description.")
                aid = service.stage_action(email_id, action_type, {"description": action_desc.strip()}, due_date=due)
                flash(f"Action #{aid} staged in Action Journal.")
            except Exception as exc:
                st.error(f"Could not save follow-up: {exc}")



def render_upload(service: InboxLearnService) -> None:
    section("01", "Inbox & intake", "Upload a batch. Inspect its predictions. Decide what needs a second look.")
    with st.expander("Import emails", expanded=not service.repo.inbox_rows()):
        upload, guidance = st.columns([3, 2], gap="large")
        with upload:
            uploaded = st.file_uploader("Email file", type=["csv", "eml", "mbox"], key="email_upload",
                                        max_upload_size=max(1, ceil(service.settings.max_upload_bytes / 1024**2)))
            fname = getattr(uploaded, "name", "")
            btn_label = "Classify email file" if (fname.lower().endswith((".eml", ".mbox"))) else "Classify CSV"
            if st.button(btn_label, type="primary", disabled=uploaded is None, key="classify_csv"):
                classify(service, uploaded.getvalue(), filename=fname)
        with guidance:
            st.markdown("**SUPPORTED FORMATS**")
            st.write("**CSV** · UTF-8, subject and body required, sender optional.")
            st.write("**EML** · Single RFC 822 email file (.eml).")
            st.write("**MBOX** · Mailbox archive with multiple messages (.mbox).")
            st.caption(f"Limit: {service.settings.max_upload_bytes / 1024**2:g} MiB / {service.settings.max_rows:,} rows. Supplied label columns are not used for training.")
            st.download_button("Download demo feedback CSV", demo_data_path("demo_feedback.csv").read_bytes(), "demo_feedback.csv", "text/csv", key="demo_download")
            if st.button("Classify demonstration sample", key="demo_classify"):
                classify(service, demo_data_path("demo_feedback.csv").read_bytes(), "demonstration")
            st.caption("Five synthetic messages. Classification does not save feedback. Review each label yourself.")

    gmail_info = service.gmail_status()
    with st.expander("Gmail connection (Read-only)", expanded=False):
        if not gmail_info["enabled"]:
            st.info(gmail_info["message"])
            st.button("Connect Gmail account", disabled=True, key="btn_connect_gmail")
        elif not gmail_info["connected"]:
            st.markdown("**CONNECT GMAIL (READ-ONLY)**")
            st.caption("Local desktop OAuth 2.0 PKCE flow. Opens your system browser to grant read-only access. No emails will be sent, modified, or deleted.")
            c_id_col, c_sec_col = st.columns(2)
            with c_id_col:
                g_client_id = st.text_input("OAuth Client ID", value=st.session_state.get("gmail_client_id", ""), key="input_gmail_client_id")
            with c_sec_col:
                g_client_secret = st.text_input("OAuth Client Secret", value=st.session_state.get("gmail_client_secret", ""), type="password", key="input_gmail_client_secret")
            if st.button("Connect Gmail account", disabled=not g_client_id or not g_client_secret, key="btn_connect_gmail"):
                try:
                    from inboxlearn.gmail import run_oauth_flow, CredentialStore, GmailClient
                    with st.spinner("Opening system browser for Google consent…"):
                        tokens = run_oauth_flow(g_client_id.strip(), g_client_secret.strip())
                    store = CredentialStore()
                    temp_client = GmailClient(store, g_client_id.strip(), g_client_secret.strip())
                    store._memory_token = {"tokens": tokens}
                    prof = temp_client.get_profile()
                    store.save_tokens(prof.get("emailAddress", "unknown"), tokens)
                    st.session_state["gmail_client_id"] = g_client_id.strip()
                    st.session_state["gmail_client_secret"] = g_client_secret.strip()
                    flash(f"Connected to Gmail account: {prof.get('emailAddress')}. Credentials protected locally.")
                except Exception as exc:
                    st.error(f"Gmail connection failed: {exc}")
        else:
            st.success(f"Stored Gmail account: **{gmail_info['email']}** (Read-only access)")
            st.caption(gmail_info["message"])
            st.caption(f"Credentials protected by {gmail_info.get('protected_by')}. Read-only scope: no remote state is modified.")
            w_col, c_col = st.columns(2)
            with w_col:
                sync_days = st.slider("Sync lookback window (days)", min_value=1, max_value=90, value=30, key="g_sync_days")
            with c_col:
                sync_cap = st.slider("Max messages cap", min_value=10, max_value=250, value=100, step=10, key="g_sync_cap")

            btn_col1, btn_col2 = st.columns([2, 1])
            with btn_col1:
                if st.button("Sync recent Gmail messages", type="primary", key="btn_run_gmail_sync"):
                    try:
                        cid = st.session_state.get("gmail_client_id", "")
                        csec = st.session_state.get("gmail_client_secret", "")
                        with st.spinner(f"Fetching recent messages from {gmail_info['email']}…"):
                            res = service.sync_gmail(cid, csec, days=sync_days, max_messages=sync_cap)
                        flash(f"Gmail sync complete: {res['new']} imported, {res['duplicates']} duplicates skipped, {res['warnings']} warnings.")
                    except Exception as exc:
                        st.error(f"Gmail sync failed: {exc}")
            with btn_col2:
                if st.button("Disconnect", key="btn_disconnect_gmail_account"):
                    try:
                        cid = st.session_state.get("gmail_client_id", "")
                        csec = st.session_state.get("gmail_client_secret", "")
                        dc_res = service.disconnect_gmail(cid, csec)
                        flash(f"Disconnected {dc_res.get('account')}. Tokens revoked on Google and cleared locally.")
                    except Exception as exc:
                        st.error(f"Disconnect failed: {exc}")

    rows = _safe_review_rows(service, include_confident=True)
    if not rows:
        st.info("Your inbox is empty. Upload a CSV, .eml, or .mbox file, or classify the demonstration sample above.")
        return
    batches = service.import_batches()
    batch_options = ["All batches"] + [b["import_batch"] for b in batches] if batches else []
    with st.container(key="inbox_filters"):
        query_col, category_col, status_col = st.columns([2, 1, 1])
        with query_col:
            query = st.text_input("Search subject, sender or body", key="inbox_search").casefold()
        with category_col:
            category = st.selectbox("Category", ["All categories", *CATEGORIES], key="inbox_category")
        with status_col:
            status = st.selectbox("Review status", ["All statuses", *STATUS_LABELS.values()], key="inbox_status")
    priority_filter = st.selectbox("Priority", ["All priorities", *PRIORITIES], key="inbox_priority")
    if batch_options:
        batch_filter = st.selectbox("Import batch", batch_options, key="inbox_batch")
    else:
        batch_filter = "All batches"
    filtered = [r for r in rows if (not query or query in " ".join([r['subject'], r['body'], r['sender']]).casefold())
                and (category == "All categories" or r["effective_category"] == category)
                and (priority_filter == "All priorities" or r["effective_priority"] == priority_filter)
                and (status == "All statuses" or STATUS_LABELS[r["status"]] == status)
                and (batch_filter == "All batches" or r.get("import_batch", "") == batch_filter)]
    listing, detail = st.columns([7, 4], gap="large")
    with listing:
        st.caption(f"{len(filtered)} of {len(rows)} messages · original predictions")
        if filtered:
            st.dataframe(pd.DataFrame([{
                "ID": r["id"],
                "Date": _row_val(r, "date_header") or "—",
                "Source": (_row_val(r, "source_type") or "csv").upper(),
                "Subject": r["subject"],
                "Category": r["effective_category"],
                "Priority": r["effective_priority"],
                "Label source": r["label_source"],
                "Category estimate": r["category_confidence"],
                "Priority estimate": r["priority_confidence"],
                "Status": STATUS_LABELS.get(_row_val(r, "status"), str(_row_val(r, "status"))),
            } for r in filtered]), hide_index=True, width="stretch", height=360,
                column_config={name: st.column_config.NumberColumn(format="percent") for name in ["Category estimate", "Priority estimate"]}, key="inbox_table")
        else:
            st.info("No messages match these filters. Clear search or choose All categories / All statuses.")
        st.download_button("Export full inbox CSV", service.export_csv(), "inboxlearn-export.csv", "text/csv", key="inbox_export")
        st.caption("Export includes all messages and latest corrections, with spreadsheet-formula protection.")
    with detail, st.container(key="inbox_detail"):
        st.subheader("Reading pane")
        if not filtered:
            st.caption("Select a matching message to read it here.")
        else:
            labels = {r["id"]: message_label(r) for r in filtered}
            selected_id = st.selectbox("Read message ID", list(labels), format_func=labels.get, key="read_email")
            row = next(r for r in filtered if r["id"] == selected_id)
            show_email(row)
            st.caption(f"{row['label_source']}: {row['effective_category']} / {row['effective_priority']}")
            st.button("Review this message", key="review_from_inbox", on_click=open_message, args=(row["id"], "Review queue"))
            original_prediction(row)
            # Extracted entities and interactive calendar editor
            entities = service.entities_for_email(int(row["id"]))
            render_calendar_editor(row, entities, f"inbox_{row['id']}", service=service)
            render_action_journal(service, row, f"inbox_act_{row['id']}")
            st.caption("Open Review queue to confirm or revise these labels.")


def render_review(service: InboxLearnService) -> None:
    section("02", "The review desk", "Save the labels you confirm. Training is a separate step.")
    include_confident = st.checkbox("Include confident predictions", value=False, key="include_confident")
    st.caption("Unchecked: unresolved uncertain predictions only. Checked: all messages, including saved corrections that you can revise.")

    batches = service.import_batches()
    batch_options = ["All batches"] + [b["import_batch"] for b in batches] if batches else []

    with st.container(key="review_filters_container"):
        col_ord, col_c, col_p, col_b = st.columns(4)
        with col_ord:
            order = st.selectbox("Review order", ["Lowest confidence first", "Newest first"], key="review_order")
        with col_c:
            review_cat = st.selectbox("Category filter", ["All categories", *CATEGORIES], key="review_cat_filter")
        with col_p:
            review_pri = st.selectbox("Priority filter", ["All priorities", *PRIORITIES], key="review_pri_filter")
        with col_b:
            review_batch = st.selectbox("Batch filter", batch_options if batch_options else ["All batches"], key="review_batch_filter")

    queue_options = dict(include_confident=include_confident, order=order, category=review_cat, priority=review_pri, import_batch=review_batch)
    st.caption("Lowest confidence uses the smaller category or priority estimate; ties use message ID.")
    if st.session_state.pop("review_complete", False):
        st.success("Review complete: no unresolved messages remain in this queue.")

    rows = _safe_review_rows(service, **queue_options)

    if not rows:
        st.info("The review queue is empty for these filters. Clear filters or check 'Include confident predictions' to review other messages.")
        return

    # Batch label confirmation tool
    with st.expander("Batch label confirmation", expanded=False):
        st.markdown("**BATCH CONFIRMATION**")
        st.caption("Apply confirmed category and priority to multiple selected emails at once.")
        selectable = {r["id"]: message_label(r) for r in rows}
        selected_batch_ids = st.multiselect("Select messages to batch-confirm", list(selectable), format_func=selectable.get, key="batch_confirm_selection")

        if selected_batch_ids:
            b_cat_col, b_pri_col = st.columns(2)
            with b_cat_col:
                batch_target_cat = st.selectbox("Batch confirmed category", CATEGORIES, key="batch_target_cat")
            with b_pri_col:
                batch_target_pri = st.selectbox("Batch confirmed priority", PRIORITIES, key="batch_target_pri")

            selected_items = [r for r in rows if r["id"] in selected_batch_ids]
            preview_records = [{
                "ID": r["id"],
                "Subject": r["subject"][:65],
                "Displayed labels": f"{r['effective_category']} / {r['effective_priority']}",
                "Confirmed Category": batch_target_cat,
                "Confirmed Priority": batch_target_pri,
            } for r in selected_items]
            st.markdown(f"**Previewing {len(selected_items)} message(s) to confirm:**")
            st.dataframe(pd.DataFrame(preview_records), hide_index=True, width="stretch")

            snapshot = {"rows": [{"id": r["id"], "feedback_id": r["feedback_id"]} for r in selected_items],
                        "category": batch_target_cat, "priority": batch_target_pri, "filters": queue_options}
            confirming = st.button(f"Confirm {len(selected_items)} selected message(s)", type="primary", key="btn_execute_batch_confirm")
            prior = st.session_state.get("batch_preview")
            if confirming:
                try:
                    if not prior or prior["snapshot"] != snapshot:
                        raise ValueError("Selection or feedback changed. Refresh the preview before confirming.")
                    count_saved = service.confirm_batch(snapshot["rows"], batch_target_cat, batch_target_pri, prior["token"])
                    flash(f"Batch confirmed {count_saved} message(s). Model unchanged.")
                except Exception as exc:
                    st.error(f"Could not save batch: {exc}")
            if not confirming or st.button("Refresh preview", key="refresh_batch"):
                st.session_state["batch_preview"] = {"snapshot": snapshot, "token": str(uuid.uuid4())}

    labels = {r["id"]: message_label(r) for r in rows}
    next_id = st.session_state.pop("next_review_email", None)
    if next_id in labels:
        st.session_state["review_email"] = next_id
    elif st.session_state.get("review_email") not in labels:
        st.session_state["review_email"] = rows[0]["id"]
    selected = st.selectbox("Message to review", list(labels), format_func=labels.get, key="review_email")
    row = next(r for r in rows if r["id"] == selected)
    reading, editing = st.columns([3, 2], gap="large")
    with reading:
        show_email(row)
        st.caption(f"{row['label_source']}: {row['effective_category']} / {row['effective_priority']}")
        original_prediction(row)
        st.markdown("**ROUTING RECORD**")
        if row["status"] == "needs_review":
            st.write("Queued at classification because category OR priority confidence was below its threshold. Sidebar changes apply to future imports.")
        elif row["status"] == "corrected":
            st.write("Human feedback is saved. The original prediction is retained.")
        else:
            st.write("Automatically classified: both confidence estimates met their thresholds at import.")
        st.caption("Confidence is an uncalibrated model estimate.")
        st.write("Suggested next action: " + row["suggested_action"])
        st.caption("Suggestion based on the displayed category. No action is executed.")
        # Extracted entities and interactive calendar editor
        entities = service.entities_for_email(int(row["id"]))
        render_calendar_editor(row, entities, f"review_{row['id']}", service=service)
        render_action_journal(service, row, f"review_act_{row['id']}")
    with editing, st.container(key="correction_panel"):
        st.subheader("Human confirmation")
        history = [dict(h) for h in service.repo.feedback_for_email(int(row["id"]))]
        current = history[-1] if history else row
        if history:
            st.caption(f"Latest correction #{current['id']} · {current['category']} / {current['priority']}")
        with st.form(f"feedback-{row['id']}"):
            category = st.selectbox("Confirmed category", CATEGORIES, index=CATEGORIES.index(current["category"]), key=f"category-{row['id']}")
            priority = st.selectbox("Confirmed priority", PRIORITIES, index=PRIORITIES.index(current["priority"]), key=f"priority-{row['id']}")
            st.caption("Saving records human feedback only. Prepare a candidate separately in Train / Versions.")
            save = st.form_submit_button("Save human correction")
            save_next = st.form_submit_button("Save and next", type="primary")
            if save or save_next:
                try:
                    correction_id, created = service.save_feedback(int(row["id"]), category, priority)
                    if save_next:
                        unresolved = [r for r in _safe_review_rows(service, **queue_options, unresolved=True)]
                        if unresolved:
                            st.session_state["next_review_email"] = unresolved[0]["id"]
                        else:
                            st.session_state["review_complete"] = True
                    flash(f"Correction #{correction_id} {'saved' if created else 'already recorded'}. Model unchanged; prepare a candidate when ready.")
                except Exception as exc:
                    st.error(f"Could not save feedback: {exc}")
        if history:
            with st.expander("Correction history"):
                st.dataframe([{"Correction": h["id"], "Category": h["category"], "Priority": h["priority"], "Replaces": h["replaces_feedback_id"]} for h in history], hide_index=True, width="stretch")


def render_versions(service: InboxLearnService) -> None:
    section("03", "Learning & lineage", "Prepare a candidate, inspect its changes, evaluate it, then choose whether to activate it.")
    active = service.active_version()
    pending = service.repo.pending_feedback_count()
    controls, ledger = st.columns([2, 3], gap="large")
    with controls:
        st.metric("Feedback absent from active model", pending)
        st.caption("Latest human corrections absent from, or revised since, the active version's membership. Preparing a candidate does not reduce this count.")
        st.write(f"Parent for the next run: **{active['label']}**")
        if st.button("Prepare candidate", type="primary", disabled=pending == 0, key="train_model"):
            try:
                with st.spinner("Building and saving an inactive candidate…"):
                    result = service.train()
                if result is None:
                    flash("No new or revised feedback remains for this lineage.", "info")
                else:
                    st.session_state["evaluation_version"] = f"v{result['version_id']}"
                    st.session_state["preview_after"] = result["version_id"]
                    st.session_state["preview_before"] = result["parent_id"]
                    flash(f"{'Reused' if result['reused'] else 'Prepared'} candidate v{result['version_id']} from v{result['parent_id']}. {active['label']} remains active. Inspect prediction changes and evaluate before activation.")
            except Exception as exc:
                st.error(f"Training failed; no partial version committed: {exc}")
        if not pending:
            st.info("No eligible feedback. Save a correction on the review desk to continue.")
        st.caption("Revised corrections already learned by the active model trigger a rebuild from seed plus latest labels. Improvements are not guaranteed.")
    versions = service.repo.versions()
    candidate_ids = {row["version_id"] for row in service.repo.candidates()}
    with ledger, st.container(key="version_ledger"):
        st.subheader("Version ledger")
        for version in versions:
            metadata = service.version_metadata(int(version["id"]))
            is_candidate = version["id"] in candidate_ids
            with st.container(border=True, key=f"version-{version['id']}"):
                state = "ACTIVE" if version["is_active"] else "CANDIDATE" if is_candidate else "AVAILABLE"
                st.markdown(f"**{version['label']} / {state}**")
                st.caption(f"{version['kind']} · parent {metadata.get('parent_version', 'none')} · {metadata.get('feedback_count', 0)} feedback labels · {version['created_at']}")
                with st.expander(f"Metadata & membership · {version['label']}"):
                    st.json(metadata)
                    membership = service.repo.feedback_membership(int(version["id"]))
                    if membership:
                        st.dataframe([dict(m) for m in membership.values()], hide_index=True, width="stretch")
                    else:
                        st.caption("Seed only; no human feedback membership.")
                if not version["is_active"]:
                    evaluation = service.current_evaluation(int(version["id"])) if is_candidate else None
                    if is_candidate:
                        feedback = service.feedback_status(int(version["id"]))
                        st.write(f"{feedback['included']} latest correction(s) included in this prepared candidate.")
                        if feedback["omitted"]:
                            st.warning(f"This candidate omits {feedback['omitted']} newer correction(s). Its snapshot stays unchanged; prepare another candidate to include them.")
                        if version["parent_id"] != active["id"]:
                            st.caption(f"Prepared from v{version['parent_id']}; the current active model is {active['label']}.")
                        if evaluation is None:
                            st.info("Evaluation required on the current held-out dataset. Open Evaluation before activation.")
                        else:
                            result = json.loads(evaluation["results_json"])
                            scores = metric_rows(result)
                            st.caption("Evaluated on the current held-out dataset. Changes below are relative to baseline.")
                            st.dataframe(scores, hide_index=True, width="stretch")
                            regressions = [r["Metric"] for r in scores if r["Result"] == "Regression"]
                            parent_scores = metric_rows({"baseline": result.get("parent", result["baseline"]), "updated": result["updated"]})
                            parent_regressions = [r["Metric"] for r in parent_scores if r["Result"] == "Regression"]
                            if regressions or parent_regressions:
                                st.warning("Regression recorded. Baseline: " + (", ".join(regressions) or "none") +
                                           "; parent: " + (", ".join(parent_regressions) or "none") + ". Activation is your decision.")
                    verb = "Roll back to" if not is_candidate and version["version_number"] < active["version_number"] else "Activate"
                    if st.button(f"{verb} {version['label']}", key=f"activate-{version['id']}",
                                 disabled=is_candidate and evaluation is None):
                        try:
                            service.activate(int(version["id"]))
                            flash(f"Activated {version['label']}. New imports use this model; further training creates a child of this version.")
                        except Exception as exc:
                            st.error(f"Could not activate version: {exc}")


def render_evaluation(service: InboxLearnService) -> None:
    section("04", "Results, on the record", "Baseline and selected version. Identical held-out examples. Actual results, including regressions.")
    versions = service.repo.versions()
    labels = {row["label"]: int(row["id"]) for row in versions}
    selected = st.selectbox("Version to compare with baseline", list(labels), key="evaluation_version")
    if st.button("Evaluate comparison", type="primary", key="evaluate"):
        try:
            with st.spinner("Scoring both models on the same held-out dataset…"):
                result = service.compare_versions(labels[selected])
            st.session_state["last_evaluation"] = result
            st.rerun()
        except Exception as exc:
            st.error(f"Evaluation failed: {exc}")
    # Select by persisted version ID, never relabel another version's stale result.
    stored = service.current_evaluation(labels[selected])
    if stored is None:
        st.info(f"Not evaluated — {selected}. Run a comparison to see measured results.")
    else:
        result = json.loads(stored["results_json"])
        baseline_label = service.repo.version(stored["baseline_version_id"])["label"]
        st.caption(f"Recorded {stored['created_at']} · {result['updated']['rows']} held-out demonstration examples · {stored['dataset_name']}")
        comparison(result, baseline_label, selected)
        with st.expander("Dataset identity & interpretation"):
            st.text("Dataset SHA-256: " + stored["heldout_hash"])
            st.write(result["note"])
    st.caption("Synthetic demonstration data. Repeatedly inspected test scores are not an unbiased final benchmark. No improvement is promised.")
    render_prediction_changes(service, versions)
    with st.expander("Validation-only threshold tuning"):
        st.write("Use the separate validation set for tuning; keep held-out scores for comparison.")
        if st.button("Suggest thresholds from validation data"):
            try:
                st.session_state["threshold_tuning"] = service.validation_tuning()
            except Exception as exc:
                st.error(f"Could not tune thresholds: {exc}")
        tuning = st.session_state.get("threshold_tuning")
        if tuning and tuning["active_version"] == service.active_version()["label"]:
            st.caption(f"Validation tuning for {tuning['active_version']} · {tuning['rows']} examples")
            st.dataframe([{"Target": target, **tuning[target]} for target in ["category", "priority"]], hide_index=True, width="stretch")
            st.write("Suggestions only. Review precision and coverage, then adjust sidebar thresholds for future imports if desired.")
        elif tuning:
            st.info("The active version changed. Run validation tuning again for this model.")


def render_prediction_changes(service, versions) -> None:
    st.subheader("Inbox prediction changes")
    labels = {int(row["id"]): row["label"] for row in versions}
    candidates = service.repo.candidates()
    default_after = candidates[0]["version_id"] if candidates else service.active_version()["id"]
    default_before = service.repo.version(default_after)["parent_id"] or default_after
    for key, default in (("preview_after", default_after), ("preview_before", default_before)):
        if st.session_state.get(key) not in labels:
            st.session_state[key] = default
    left, right = st.columns(2)
    with left:
        before_id = st.selectbox("Before version", list(labels), format_func=labels.get, key="preview_before")
    with right:
        after_id = st.selectbox("After version", list(labels), format_func=labels.get, key="preview_after")
    if after_id in {row["version_id"] for row in candidates}:
        omitted = service.feedback_status(after_id)["omitted"]
        if omitted:
            st.warning(f"{labels[after_id]} omits {omitted} newer correction(s). Preview uses its immutable training snapshot.")
    st.caption("On-demand predictions from saved models. Inbox predictions and routing records stay as originally recorded. Confidence estimates are uncalibrated.")
    key = service.preview_key(before_id, after_id)
    cached = st.session_state.get("prediction_preview")
    if cached and cached["key"] != key:
        del st.session_state["prediction_preview"]
        cached = None
        st.info("Preview inputs changed. Compute prediction changes again.")
    if st.button("Compute prediction changes", key="preview_compute"):
        try:
            with st.spinner("Comparing inbox predictions…"):
                cached = {"key": key, "result": service.prediction_preview(before_id, after_id)}
            st.session_state["prediction_preview"] = cached
        except Exception as exc:
            st.error(f"Could not compute preview: {exc}")
    changed_only = st.checkbox("Show changed messages only", value=True, key="preview_changed_only")
    st.caption("Changed means category or priority label changed. Training members are marked for each version; agreement on them is not held-out accuracy.")
    if cached:
        result = cached["result"]
        st.write(f"{result['changed']} of {result['total']} messages changed · {result['category_changed']} category · {result['priority_changed']} priority")
        rows = [row for row in result["rows"] if row["changed"] or not changed_only]
        if rows:
            messages = {row["id"]: message_label(row) for row in rows}
            selected = st.selectbox("Inspect preview message", list(messages), format_func=messages.get, key="preview_message")
            detail = next(row for row in rows if row["id"] == selected)
            for column, prefix, version_id in zip(st.columns(2), ("before", "after"), (before_id, after_id)):
                with column:
                    st.markdown(f"**{prefix.title()} / {labels[version_id]}**")
                    st.write(f"{detail[f'{prefix}_category']} / {detail[f'{prefix}_priority']} priority")
                    st.caption(f"Category estimate {detail[f'{prefix}_category_confidence']:.1%} · Priority estimate {detail[f'{prefix}_priority_confidence']:.1%}")
                    st.caption("Included in training" if detail[f"{prefix}_training_member"] else "Not a training member")
            st.write(f"Latest human labels: {detail['human_category'] or 'not confirmed'} / {detail['human_priority'] or 'not confirmed'}")
            titles = {"id": "ID", "subject": "Subject"}
            for field, title in (("category", "category"), ("priority", "priority"),
                                 ("category_confidence", "category estimate"), ("priority_confidence", "priority estimate"),
                                 ("training_member", "training member")):
                for prefix in ("before", "after"):
                    titles[f"{prefix}_{field}"] = f"{prefix.title()} {title}"
            titles.update({"human_category": "Latest human category", "human_priority": "Latest human priority"})
            st.dataframe(pd.DataFrame([{title: row[field] for field, title in titles.items()} for row in rows]),
                         hide_index=True, width="stretch", key="prediction_changes",
                         column_config={title: st.column_config.NumberColumn(format="percent")
                                        for field, title in titles.items() if field.endswith("confidence")})
            st.caption("Scroll the table horizontally for all estimates, training membership and latest human labels.")
        else:
            st.info("No changed messages." if result["total"] else "Import messages to preview prediction changes.")


def main() -> None:
    apply_newsprint()
    settings = Settings.from_environment()
    with st.sidebar:
        st.header("Routing controls")
        st.caption("Applies to future imports. Existing routing records stay as originally classified.")
        category_threshold = st.slider("Category review threshold", 0.0, 1.0, min(1.0, max(0.0, settings.category_threshold)), 0.01)
        priority_threshold = st.slider("Priority review threshold", 0.0, 1.0, min(1.0, max(0.0, settings.priority_threshold)), 0.01)
        st.caption("Review when category OR priority falls below its threshold. Confidence is an uncalibrated estimate.")
    try:
        service = get_service(str(settings.db_path.resolve()), category_threshold, priority_threshold,
                              settings.max_upload_bytes, settings.max_rows, settings.random_state,
                              version=APP_VERSION)
        rows = service.repo.inbox_rows()
        active = service.active_version()
        pending = service.repo.pending_feedback_count()
        dataset_counts = {name: len(load_demo_rows(f"demo_{name}.csv")) for name in ["seed", "validation", "eval"]}
    except Exception as exc:
        st.title("InboxLearn")
        st.error(f"Workspace could not be opened: {exc}")
        st.stop()
    masthead(active, dataset_counts)
    status_strip(len(rows), sum(r["status"] == "needs_review" for r in rows), pending, active["label"])
    show_flash()
    with st.sidebar:
        st.metric("Active model", active["label"])
        st.metric("Pending feedback", pending)
        with st.expander("About this workspace"):
            st.write("Seed, validation, feedback examples and held-out evaluation files are synthetic demonstration data. Human confirmation is required before feedback training.")
            st.write("Actions are suggestions only. No sending, deletion, payments or external integrations.")
            st.text(f"Local database: {settings.db_path}")
    today_tab, upload_tab, review_tab, version_tab, evaluation_tab = st.tabs(
        ["Today", "Upload / Inbox", "Review queue", "Train / Versions", "Evaluation"],
        key="workspace_tabs", on_change="rerun",
    )
    with today_tab:
        render_today(service)
    with upload_tab:
        render_upload(service)
    with review_tab:
        render_review(service)
    with version_tab:
        render_versions(service)
    with evaluation_tab:
        render_evaluation(service)
    with st.container(key="workspace_footer"):
        st.caption("INBOXLEARN / LOCAL WORKSPACE · Human labels guide learning. All suggested actions remain yours to take.")


if __name__ == "__main__":
    main()
