"""Small Newsprint presentation helpers. No persistence or learning logic."""
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

STATUS_LABELS = {"needs_review": "Needs review", "classified": "Auto-classified", "corrected": "Feedback saved"}


def apply_newsprint() -> None:
    st.html(Path(__file__).resolve().parent.parent / "assets" / "newsprint.css")


def masthead(active, datasets: dict) -> None:
    # Only static copy and escaped system metadata enter decorative markup.
    st.html(f'''<header class="np-masthead">
        <div><p class="np-kicker">THE EMAIL TRIAGE WORKSPACE / LOCAL &amp; HUMAN-GUIDED</p>
        <h1>InboxLearn</h1><p class="np-subtitle">An adaptive email triage workspace.</p></div>
        <div class="np-edition"><p>ACTIVE MODEL / <strong>{escape(active['label'])}</strong></p>
        <p>{escape(active['kind'].upper())} · PARENT {escape(str(active['parent_id'] or 'NONE'))}</p>
        <p>DEMONSTRATION DATA<br>{datasets['seed']} SEED · {datasets['validation']} VALIDATION · {datasets['eval']} HELD-OUT</p></div>
        </header>''')


def status_strip(emails: int, reviews: int, feedback: int, active: str) -> None:
    with st.container(key="status_strip"):
        for column, label, value, help_text in zip(st.columns(4),
                ["Emails stored", "Pending reviews", "Available feedback", "Active version"],
                [emails, reviews, feedback, active],
                ["All unique stored emails.", "Unresolved emails originally routed for review.",
                 "Latest human corrections absent from the active model; one per email. They may already be included in a prepared candidate.",
                 "Model used for the next import and as parent for further training."]):
            with column:
                st.metric(label, value, help=help_text)


def section(number: str, title: str, description: str) -> None:
    st.html(f'<div class="np-section"><span>{escape(number)}</span><h2>{escape(title)}</h2></div>')
    st.write(description)


def _field(row, key, default=""):
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, IndexError, TypeError):
        return default


def show_email(row: dict) -> None:
    status_label = STATUS_LABELS.get(_field(row, "status"), str(_field(row, "status"))).upper()
    source_type = (_field(row, "source_type") or "csv").upper()
    date_header = _field(row, "date_header")
    
    meta_line = f"MESSAGE #{row['id']} / {status_label} · SOURCE: {source_type}"
    if date_header:
        meta_line += f" · DATE: {date_header}"
    st.caption(meta_line)

    msg_id = _field(row, "message_id")
    in_reply = _field(row, "in_reply_to")
    if msg_id or in_reply:
        with st.expander("Technical headers", expanded=False):
            if msg_id:
                st.caption(f"Message-ID: {msg_id}")
            if in_reply:
                st.caption(f"In-Reply-To: {in_reply}")

    warnings_json = _field(row, "parser_warnings_json")
    if warnings_json:
        import json
        try:
            warnings = json.loads(warnings_json)
            if warnings:
                with st.expander(f"⚠️ Parser warnings ({len(warnings)})", expanded=False):
                    for w in warnings:
                        st.caption(f"• {w}")
        except Exception:
            pass

    # Never interpret email subjects, senders or bodies as Markdown/HTML.
    st.text("Subject: " + row["subject"])
    st.text("From: " + (row["sender"] or "Not supplied"))
    st.text(row["body"])


def original_prediction(row: dict) -> None:
    st.caption(f"ORIGINAL PREDICTION / MODEL v{row['model_version_id']}")
    st.write(f"**{row['category']}** / {row['priority']} priority")
    st.caption(f"Category {row['category_confidence']:.1%} · Priority {row['priority_confidence']:.1%} · Uncalibrated estimates")


def metric_rows(result: dict) -> list[dict]:
    rows = []
    for key, title in [("category_accuracy", "Category accuracy"), ("category_macro_f1", "Category macro-F1"),
                       ("priority_accuracy", "Priority accuracy"), ("priority_macro_f1", "Priority macro-F1")]:
        baseline, updated = result["baseline"][key], result["updated"][key]
        change = updated - baseline
        rows.append({"Metric": title, "Baseline": f"{baseline:.3f}", "Selected": f"{updated:.3f}",
                     "Change": f"{change:+.3f}", "Result": "Regression" if change < 0 else "Increase" if change > 0 else "Unchanged"})
    return rows


def matrix(metrics: dict, target: str, version: str) -> None:
    labels = metrics[f"{target}_labels"]
    counts = metrics[f"{target}_confusion_matrix"]
    largest = max((int(n) for row in counts for n in row), default=0)
    headers = ''.join(f'<th scope="col">{escape(label)}</th>' for label in labels)
    body = ''
    for label, row in zip(labels, counts):
        cells = ''.join(f'<td class="np-tone-{min(3, int(int(n) / largest * 3)) if largest else 0}">{int(n)}</td>' for n in row)
        body += f'<tr><th scope="row">{escape(label)}</th>{cells}</tr>'
    st.html(f'<div class="np-matrix" tabindex="0" role="region" aria-label="{escape(version)} {target} confusion matrix"><table><caption>{escape(version)} / {target.title()}</caption><thead><tr><th scope="col">Actual ↓ / Predicted →</th>{headers}</tr></thead><tbody>{body}</tbody></table></div>')


def comparison(result: dict, baseline_label: str, selected_label: str) -> None:
    st.subheader(f"{baseline_label} baseline / {selected_label} selected")
    rows = metric_rows(result)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", key="comparison_metrics")
    regressions = [r["Metric"] for r in rows if r["Result"] == "Regression"]
    if regressions:
        st.warning("Regression recorded: " + ", ".join(regressions) + ".")
    st.caption("Scores range from 0 to 1. Change = selected minus baseline. Negative values are regressions.")
    st.subheader("Confusion matrices")
    st.caption("Rows = actual labels. Columns = predicted labels. Each cell is an example count; darker cells contain more examples.")
    for target in ["category", "priority"]:
        left, right = st.columns(2, gap="large")
        with left:
            matrix(result["baseline"], target, baseline_label + " baseline")
        with right:
            matrix(result["updated"], target, selected_label + " selected")


def flash(message: str, level: str = "success") -> None:
    st.session_state["workspace_notice"] = (level, message)
    st.rerun()


def show_flash() -> None:
    notice = st.session_state.pop("workspace_notice", None)
    # Keep subsequent widget/container positions stable when notices appear/disappear.
    with st.container(key="workspace_notice_region"):
        if notice:
            level, message = notice
            (st.info if level == "info" else st.success)(message)
