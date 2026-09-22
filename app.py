"""Native Streamlit presentation over the existing InboxLearn service."""
import json
from datetime import date, datetime
from math import ceil
from pathlib import Path

import pandas as pd
import streamlit as st

from inboxlearn.config import CATEGORIES, PRIORITIES, Settings
from inboxlearn.calendar_export import create_event, event_to_ics_bytes, download_filename
from inboxlearn.demo import demo_data_path, load_demo_rows
from inboxlearn.entities import ExtractedEntity
from inboxlearn.service import InboxLearnService
from inboxlearn.presentation import (
    apply_newsprint, masthead, status_strip, section, show_email,
    original_prediction, comparison, metric_rows, flash, show_flash, STATUS_LABELS,
)

st.set_page_config(page_title="InboxLearn", page_icon="✉", layout="wide", initial_sidebar_state="collapsed")


@st.cache_resource
def get_service(db_path: str, category_threshold: float, priority_threshold: float,
                max_upload_bytes: int = 5 * 1024 * 1024, max_rows: int = 1000,
                random_state: int = 42) -> InboxLearnService:
    return InboxLearnService(Settings(
        db_path=Path(db_path), category_threshold=category_threshold,
        priority_threshold=priority_threshold, max_upload_bytes=max_upload_bytes,
        max_rows=max_rows, random_state=random_state,
    ))


def classify(service, payload: bytes, source="upload") -> None:
    try:
        with st.spinner("Validating and classifying messages…"):
            result = service.classify_email_file(payload, source=source)
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


def render_upload(service: InboxLearnService) -> None:
    section("01", "Inbox & intake", "Upload a batch. Inspect its predictions. Decide what needs a second look.")
    with st.expander("Import emails", expanded=not service.repo.inbox_rows()):
        upload, guidance = st.columns([3, 2], gap="large")
        with upload:
            uploaded = st.file_uploader("Email file", type=["csv", "eml", "mbox"], key="email_upload",
                                        max_upload_size=max(1, ceil(service.settings.max_upload_bytes / 1024**2)))
            if st.button("Classify file", type="primary", disabled=uploaded is None, key="classify_csv"):
                classify(service, uploaded.getvalue())
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

    rows = service.review_rows(include_confident=True)
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
            category = st.selectbox("Predicted category", ["All categories", *CATEGORIES], key="inbox_category")
        with status_col:
            status = st.selectbox("Review status", ["All statuses", *STATUS_LABELS.values()], key="inbox_status")
    if batch_options:
        batch_filter = st.selectbox("Import batch", batch_options, key="inbox_batch")
    else:
        batch_filter = "All batches"
    filtered = [r for r in rows if (not query or query in " ".join([r['subject'], r['body'], r['sender']]).casefold())
                and (category == "All categories" or r["category"] == category)
                and (status == "All statuses" or STATUS_LABELS[r["status"]] == status)
                and (batch_filter == "All batches" or r.get("import_batch", "") == batch_filter)]
    listing, detail = st.columns([7, 4], gap="large")
    with listing:
        st.caption(f"{len(filtered)} of {len(rows)} messages · original predictions")
        if filtered:
            st.dataframe(pd.DataFrame([{
                "ID": r["id"], "Subject": r["subject"], "Category": r["category"],
                "Priority": r["priority"], "Category estimate": r["category_confidence"],
                "Priority estimate": r["priority_confidence"], "Status": STATUS_LABELS[r["status"]],
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
            original_prediction(row)
            # Extracted entities display
            entities = service.entities_for_email(int(row["id"]))
            if entities:
                with st.expander(f"Extracted entities ({len(entities)})", expanded=False):
                    for entity in entities:
                        icon = {"deadline": "📅", "date_mention": "📆", "amount": "💰",
                                "action_item": "✅", "contact_email": "📧", "url": "🔗"}.get(entity["entity_type"], "📌")
                        st.write(f"{icon} **{entity['entity_type']}**: {entity['entity_value'] or '(unresolved)'}")
                        if entity["source_phrase"]:
                            st.caption(f"From: \"{entity['source_phrase']}\"")
                    # Calendar export for deadline entities
                    deadline_entities = [e for e in entities if e["entity_type"] in ("deadline", "date_mention") and e["entity_value"]]
                    if deadline_entities:
                        st.markdown("---")
                        st.markdown("**Calendar export**")
                        for i, entity in enumerate(deadline_entities):
                            try:
                                parsed_date = date.fromisoformat(entity["entity_value"])
                                event = create_event(
                                    summary=f"{row['category'].title()}: {row['subject'][:60]}",
                                    dtstart=parsed_date,
                                    description=f"InboxLearn email #{row['id']}: {row['subject']}\n\nSource: {entity['source_phrase']}",
                                    email_id=int(row["id"]),
                                    source_phrase=entity["source_phrase"],
                                )
                                st.download_button(
                                    f"📅 Download .ics ({entity['entity_value']})",
                                    event_to_ics_bytes(event),
                                    download_filename(event),
                                    "text/calendar",
                                    key=f"ics_{row['id']}_{i}",
                                )
                            except (ValueError, TypeError):
                                pass
            st.caption("Open Review queue to confirm or revise these labels.")


def render_review(service: InboxLearnService) -> None:
    section("02", "The review desk", "Save the labels you confirm. Training is a separate step.")
    include_confident = st.checkbox("Include confident predictions", value=False, key="include_confident")
    st.caption("Unchecked: unresolved uncertain predictions only. Checked: all messages, including saved corrections that you can revise.")
    order = st.selectbox("Review order", ["Lowest confidence first", "Newest first"], key="review_order")
    rows = service.review_rows(include_confident=include_confident, order=order)
    st.caption("Lowest confidence uses the smaller category or priority estimate; ties use message ID.")
    if st.session_state.pop("review_complete", False):
        st.success("Review complete: no unresolved messages remain in this queue.")
    if not rows:
        st.info("The review queue is empty. Include confident predictions to review other messages.")
        return
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
        st.caption("Suggestion based on the original category. No action is executed.")
        # Entities in review pane
        entities = service.entities_for_email(int(row["id"]))
        if entities:
            with st.expander(f"Extracted entities ({len(entities)})"):
                for entity in entities:
                    icon = {"deadline": "📅", "date_mention": "📆", "amount": "💰",
                            "action_item": "✅", "contact_email": "📧", "url": "🔗"}.get(entity["entity_type"], "📌")
                    st.write(f"{icon} **{entity['entity_type']}**: {entity['entity_value'] or '(unresolved)'}")
                    if entity["source_phrase"]:
                        st.caption(f"From: \"{entity['source_phrase']}\"")
                deadline_entities = [e for e in entities if e["entity_type"] in ("deadline", "date_mention") and e["entity_value"]]
                for i, entity in enumerate(deadline_entities):
                    try:
                        parsed_date = date.fromisoformat(entity["entity_value"])
                        event = create_event(
                            summary=f"{row['category'].title()}: {row['subject'][:60]}",
                            dtstart=parsed_date,
                            description=f"InboxLearn email #{row['id']}: {row['subject']}\n\nSource: {entity['source_phrase']}",
                            email_id=int(row["id"]),
                            source_phrase=entity["source_phrase"],
                        )
                        st.download_button(
                            f"📅 Download .ics ({entity['entity_value']})",
                            event_to_ics_bytes(event),
                            download_filename(event),
                            "text/calendar",
                            key=f"review_ics_{row['id']}_{i}",
                        )
                    except (ValueError, TypeError):
                        pass
    with editing, st.container(key="correction_panel"):
        st.subheader("Human confirmation")
        history = row["feedback_history"]
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
                        unresolved = [r for r in service.review_rows(include_confident=include_confident, order=order)
                                      if r["status"] != "corrected"]
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
                              settings.max_upload_bytes, settings.max_rows, settings.random_state)
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
    upload_tab, review_tab, version_tab, evaluation_tab = st.tabs(
        ["Upload / Inbox", "Review queue", "Train / Versions", "Evaluation"],
        key="workspace_tabs", on_change="rerun",
    )
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
