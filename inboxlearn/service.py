import csv
from datetime import date, datetime
import hashlib
import importlib.metadata
import io
import json
import sys
from typing import Callable

from .classifier import deserialize_bundle, serialize_bundle, train_bundle
from .config import CATEGORIES, PRIORITIES, Settings
from .db import Repository, utc_now
from .demo import load_demo_rows
from .entities import extract_entities
from .evaluation import assert_split_isolated, comparison_payload, dataset_hash, evaluate_bundle, tune_review_thresholds
from .parsers import parse_eml_bytes, parse_mbox_bytes, detect_format
from .validation import content_hash, parse_csv_bytes, split_key


TRAINING_RECIPE_VERSION = "sgd-feedback-v1"


ACTION_SUGGESTIONS = {
    "job opportunities": "Review the role, deadline, and whether a follow-up reminder is useful.",
    "university": "Check for an academic deadline, event, or document that you may want to record.",
    "bills": "Check the amount and due date, then decide whether to pay it manually.",
    "promotions": "Review the offer and archive it if it is not relevant.",
    "spam": "Avoid links or attachments and review it manually as possible spam.",
}


def _dependency_versions() -> dict:
    names = {"python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"}
    for package in ("scikit-learn", "numpy", "streamlit"):
        try:
            names[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            names[package] = "unavailable"
    return names


def _row_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


class InboxLearnService:
    def __init__(self, settings: Settings | None = None, repository: Repository | None = None):
        self.settings = settings or Settings.from_environment()
        self.repo = repository or Repository(self.settings.db_path)
        self.ensure_baseline()

    def ensure_baseline(self) -> int:
        active = self.repo.active_version()
        if active:
            return int(active["id"])
        seed_rows = load_demo_rows("demo_seed.csv")
        assert_split_isolated(seed_rows, load_demo_rows("demo_eval.csv"))
        assert_split_isolated(seed_rows, load_demo_rows("demo_validation.csv"))
        bundle = train_bundle(seed_rows, random_state=self.settings.random_state)
        metadata = {
            "description": "Demonstration seed model. It is trained only on reproducible synthetic seed data.",
            "training_mode": "seed",
            "seed_count": len(seed_rows),
            "feedback_count": 0,
            "dependencies": _dependency_versions(),
            "random_state": self.settings.random_state,
            "seed_content_keys": [split_key(row) for row in seed_rows],
        }
        with self.repo.training_transaction() as conn:
            active = self.repo.active_version(conn)
            if active:
                return int(active["id"])
            return self.repo.create_version_conn(
                conn, blob=serialize_bundle(bundle), parent_id=None, kind="baseline", metadata=metadata,
                feedback_rows=[], seed_count=len(seed_rows), activate=True,
            )

    def active_version(self):
        return self.repo.active_version()

    def classify_upload(self, payload: bytes, *, source: str = "upload") -> dict:
        rows = parse_csv_bytes(
            payload,
            max_bytes=self.settings.max_upload_bytes,
            max_rows=self.settings.max_rows,
        )
        version = self.repo.active_version()
        if not version:
            self.ensure_baseline()
            version = self.repo.active_version()
        bundle = deserialize_bundle(version["model_blob"])
        new_count = 0
        duplicate_count = 0
        for row in rows:
            prediction = bundle.predict(
                row,
                int(version["id"]),
                self.settings.category_threshold,
                self.settings.priority_threshold,
            )
            before = self.repo._one("SELECT id FROM emails WHERE content_hash=?", (content_hash(row),))
            self.repo.insert_email_with_prediction(row, content_hash(row), prediction, source=source)
            if before:
                duplicate_count += 1
            else:
                new_count += 1
        return {"rows": len(rows), "new": new_count, "duplicates": duplicate_count, "version_id": int(version["id"])}

    def classify_email_file(self, payload: bytes, *, filename: str = "", source: str = "upload") -> dict:
        """Import and classify .eml or .mbox files using the new parsers."""
        fmt = detect_format(payload)
        if fmt == "csv":
            return self.classify_upload(payload, source=source)
        import_batch = f"{source}:{hashlib.sha256(payload[:1024]).hexdigest()[:12]}"
        if fmt == "eml":
            rows = parse_eml_bytes(payload, import_batch=import_batch)
        elif fmt == "mbox":
            rows = parse_mbox_bytes(payload, import_batch=import_batch)
        else:
            raise ValueError(f"Unsupported file format: {fmt}")

        version = self.repo.active_version()
        if not version:
            self.ensure_baseline()
            version = self.repo.active_version()
        bundle = deserialize_bundle(version["model_blob"])
        new_count = 0
        duplicate_count = 0
        warning_count = 0
        for row in rows:
            if row.get("parser_warnings"):
                warning_count += len(row["parser_warnings"])
            prediction = bundle.predict(
                row,
                int(version["id"]),
                self.settings.category_threshold,
                self.settings.priority_threshold,
            )
            before = self.repo._one("SELECT id FROM emails WHERE content_hash=?", (content_hash(row),))
            email_id = self.repo.insert_email_extended(
                row, content_hash(row), prediction,
                source=source,
                source_type=fmt,
                import_batch=import_batch,
                message_id=row.get("message_id", ""),
                in_reply_to=row.get("in_reply_to", ""),
                thread_id=row.get("thread_id", ""),
                date_header=row.get("date", ""),
                parser_warnings=row.get("parser_warnings"),
            )
            if before:
                duplicate_count += 1
            else:
                new_count += 1
                # Auto-extract entities for newly imported emails.
                self._extract_and_save_entities(email_id, row)
        return {
            "rows": len(rows), "new": new_count, "duplicates": duplicate_count,
            "warnings": warning_count, "version_id": int(version["id"]),
            "import_batch": import_batch, "format": fmt,
        }

    def _extract_and_save_entities(self, email_id: int, row: dict) -> None:
        """Extract entities from an email and persist them."""
        text = f"{row.get('subject', '')} {row.get('body', '')}"
        ref_date = None
        date_str = row.get("date") or row.get("date_header") or ""
        if date_str:
            try:
                # Support ISO 8601 strings (e.g. 2025-10-14 or 2025-10-14T15:30:00+00:00)
                ref_date = datetime.fromisoformat(date_str).date()
            except (ValueError, TypeError):
                pass
        entities = extract_entities(text, reference_date=ref_date)
        for entity in entities:
            self.repo.save_entity(
                email_id,
                entity.entity_type,
                entity.value,
                source_phrase=entity.raw_phrase,
                confidence=entity.confidence,
            )

    def entities_for_email(self, email_id: int) -> list[dict]:
        """Get extracted entities for an email as plain dicts."""
        return [dict(row) for row in self.repo.entities_for_email(email_id)]

    def import_batches(self) -> list[dict]:
        """Get import batch listing."""
        return self.repo.import_batches()

    def stage_action(self, email_id: int, action_type: str, payload: dict | None = None, due_date=None) -> int:
        """Stage an action in the journal."""
        return self.repo.save_action(email_id, action_type, payload or {}, self._due_date(due_date))

    @staticmethod
    def _due_date(value):
        return date.fromisoformat(str(value)).isoformat() if value is not None else None

    def edit_action_due_date(self, action_id: int, due_date=None) -> None:
        value = self._due_date(due_date)
        with self.repo.training_transaction() as conn:
            if not conn.execute("UPDATE action_journal SET due_date=? WHERE id=?", (value, action_id)).rowcount:
                raise ValueError("Action does not exist.")

    def reopen_action(self, action_id: int) -> None:
        with self.repo.training_transaction() as conn:
            if not conn.execute("UPDATE action_journal SET status='staged', executed_at=NULL WHERE id=?", (action_id,)).rowcount:
                raise ValueError("Action does not exist.")

    def follow_ups(self, *, today=None) -> list[dict]:
        today = (today or date.today()).isoformat()
        rows = [dict(r) for r in self.repo._all("""SELECT a.*, e.subject, e.sender FROM action_journal a
            JOIN emails e ON e.id=a.email_id ORDER BY a.due_date IS NULL, a.due_date, a.id""")]
        for row in rows:
            due = row['due_date']
            row['group'] = ('History' if row['status'] != 'staged' else 'No due date' if not due
                            else 'Overdue' if due < today else 'Today' if due == today else 'Upcoming')
        return rows

    def confirm_batch(self, preview: list[dict], category: str, priority: str, token: str) -> int:
        if category not in CATEGORIES or priority not in PRIORITIES or not preview:
            raise ValueError("Select messages and supported labels.")
        if len({r['id'] for r in preview}) != len(preview):
            raise ValueError("Duplicate messages in preview.")
        payload = json.dumps([preview, category, priority], sort_keys=True)
        with self.repo.training_transaction() as conn:
            prior = conn.execute("SELECT payload FROM batch_confirmations WHERE token=?", (token,)).fetchone()
            if prior:
                if prior['payload'] != payload:
                    raise ValueError("Selection changed. Refresh the preview.")
                return len(preview)
            for row in preview:
                latest = conn.execute("SELECT MAX(id) FROM feedback WHERE email_id=?", (row['id'],)).fetchone()[0]
                if latest != row['feedback_id'] or not conn.execute("SELECT 1 FROM emails WHERE id=?", (row['id'],)).fetchone():
                    raise ValueError("Feedback changed. Refresh the preview.")
            for row in preview:
                previous = conn.execute("SELECT * FROM feedback WHERE id=?", (row['feedback_id'],)).fetchone()
                if previous and previous['category'] == category and previous['priority'] == priority:
                    continue
                conn.execute("INSERT INTO feedback(email_id,category,priority,replaces_feedback_id,created_at) VALUES (?,?,?,?,?)",
                             (row['id'], category, priority, row['feedback_id'], utc_now()))
                conn.execute("UPDATE predictions SET status='corrected' WHERE email_id=? AND is_original=1", (row['id'],))
            conn.execute("INSERT INTO batch_confirmations VALUES (?,?)", (token, payload))
        return len(preview)

    def execute_action(self, action_id: int) -> None:
        """Mark a staged action as executed."""
        self.repo.execute_action(action_id)

    def revert_action(self, action_id: int) -> None:
        """Mark an action as reverted."""
        self.repo.revert_action(action_id)

    def email_actions(self, email_id: int) -> list[dict]:
        """Get action journal entries for an email as plain dicts."""
        return [dict(row) for row in self.repo.actions_for_email(email_id)]

    def gmail_status(self, storage_dir: str = "runtime/credentials") -> dict:
        """Check status of local Gmail connection."""
        from .gmail import CredentialStore, is_gmail_enabled
        enabled = is_gmail_enabled()
        if not enabled:
            return {"enabled": False, "connected": False, "reason": "Disabled in hosted/demo mode."}

        store = CredentialStore(storage_dir=storage_dir)
        tokens = store.load_tokens()
        if not tokens:
            return {"enabled": True, "connected": False}

        return {
            "enabled": True,
            "connected": True,
            "account_email": tokens.get("account_email", "unknown"),
            "saved_at": tokens.get("saved_at", ""),
            "protected_by": tokens.get("protected_by", "file"),
        }

    def sync_gmail(
        self,
        client_id: str,
        client_secret: str,
        *,
        days: int = 30,
        max_messages: int = 100,
        storage_dir: str = "runtime/credentials",
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        """Synchronize recent messages from connected Gmail account."""
        from .gmail import CredentialStore, GmailClient, sync_gmail
        store = CredentialStore(storage_dir=storage_dir)
        client = GmailClient(store, client_id=client_id, client_secret=client_secret)
        return sync_gmail(
            self,
            client,
            days=days,
            max_messages=max_messages,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )

    def disconnect_gmail(
        self,
        client_id: str,
        client_secret: str,
        storage_dir: str = "runtime/credentials",
    ) -> dict:
        """Disconnect Gmail and revoke stored access token."""
        from .gmail import CredentialStore, disconnect_gmail
        store = CredentialStore(storage_dir=storage_dir)
        return disconnect_gmail(store, client_id=client_id, client_secret=client_secret)


    def save_feedback(self, email_id: int, category: str, priority: str) -> tuple[int, bool]:
        category = category.strip().casefold()
        priority = priority.strip().casefold()
        if category not in CATEGORIES or priority not in PRIORITIES:
            raise ValueError("Feedback must use one of the supported categories and priorities.")
        return self.repo.save_feedback(email_id, category, priority)

    def review_rows(self, *, include_confident: bool = False, order: str = "Lowest confidence first",
                    category="All categories", priority="All priorities", import_batch="All batches", unresolved=False) -> list[dict]:
        result = []
        for raw in self.repo.inbox_rows(review_only=False, include_confident=include_confident):
            row = _row_dict(raw)
            if ((category != "All categories" and row['effective_category'] != category)
                or (priority != "All priorities" and row['effective_priority'] != priority)
                or (import_batch != "All batches" and row['import_batch'] != import_batch)
                or (unresolved and row['feedback_id'] is not None)):
                continue
            row["suggested_action"] = ACTION_SUGGESTIONS[row["effective_category"]]
            row["routing_reason"] = self.routing_reason(row)
            result.append(row)
        if order == "Newest first":
            result.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
        else:
            result.sort(key=lambda r: (min(r["category_confidence"], r["priority_confidence"]), r["id"]))
        return result

    def routing_reason(self, row: dict) -> str:
        if row["status"] == "needs_review":
            reasons = []
            if float(row["category_confidence"]) < self.settings.category_threshold:
                reasons.append(f"category estimate {float(row['category_confidence']):.1%} is below {self.settings.category_threshold:.0%}")
            if float(row["priority_confidence"]) < self.settings.priority_threshold:
                reasons.append(f"priority estimate {float(row['priority_confidence']):.1%} is below {self.settings.priority_threshold:.0%}")
            return "Queued for review because " + " and ".join(reasons) + ". Confidence is an uncalibrated model estimate."
        if row["status"] == "corrected":
            return "A human correction is recorded; the original prediction remains available for comparison."
        return "Automatically classified because both confidence estimates met their thresholds. Confidence is an uncalibrated model estimate."

    def train(self) -> dict | None:
        seed_rows = load_demo_rows("demo_seed.csv")
        with self.repo.training_transaction() as conn:
            active = self.repo.active_version(conn)
            if not active:
                raise RuntimeError("No active model version is available.")
            latest = self.repo.latest_feedback(conn)
            membership = self.repo.feedback_membership(int(active["id"]), conn)
            revisions = []
            new_feedback = []
            for row in latest:
                previous = membership.get(int(row["email_id"]))
                if previous and (int(previous["feedback_id"]) != int(row["id"])
                                 or previous["category"] != row["category"]
                                 or previous["priority"] != row["priority"]):
                    revisions.append(row)
                elif not previous:
                    new_feedback.append(row)
            if not revisions and not new_feedback:
                return None

            registry_key = (int(active["id"]), dataset_hash(seed_rows),
                            json.dumps([int(row["id"]) for row in latest]),
                            f"{TRAINING_RECIPE_VERSION}:random_state={self.settings.random_state}")
            existing = conn.execute(
                """SELECT version_id FROM candidate_registry WHERE parent_id=? AND seed_hash=?
                   AND feedback_revision_ids=? AND recipe_version=?""", registry_key,
            ).fetchone()
            if existing:
                version = conn.execute("SELECT * FROM model_versions WHERE id=?", (existing["version_id"],)).fetchone()
                metadata = json.loads(version["metadata_json"])
                return {"version_id": int(version["id"]), "parent_id": int(active["id"]),
                        "mode": metadata["training_mode"], "feedback_count": metadata["trained_feedback_count"],
                        "reused": True}

            # Check complete content before fitting or committing any new model state.
            all_training_rows = seed_rows + [_row_dict(row) for row in latest]
            assert_split_isolated(all_training_rows, load_demo_rows("demo_eval.csv"))
            assert_split_isolated(all_training_rows, load_demo_rows("demo_validation.csv"))

            if revisions:
                training_rows = seed_rows + [_row_dict(row) for row in latest]
                bundle = train_bundle(training_rows, random_state=self.settings.random_state)
                mode = "rebuild_from_seed_plus_latest_feedback"
                trained_count = len(latest)
            else:
                base = deserialize_bundle(active["model_blob"])
                training_rows = [_row_dict(row) for row in new_feedback]
                bundle = train_bundle(training_rows, base=base, incremental=True)
                mode = "incremental_feedback"
                trained_count = len(new_feedback)
            metadata = {
                "description": "Human-confirmed feedback model version.",
                "training_mode": mode,
                "trained_feedback_count": trained_count,
                "feedback_count": len(latest),
                "seed_count": len(seed_rows),
                "dependencies": _dependency_versions(),
                "random_state": self.settings.random_state,
                "parent_version": active["label"],
                "feedback_content_source": "emails joined to latest human corrections",
                "seed_content_keys": [split_key(row) for row in seed_rows],
                "recipe_version": registry_key[3],
            }
            version_id = self.repo.create_version_conn(
                conn,
                blob=serialize_bundle(bundle),
                parent_id=int(active["id"]),
                kind="trained",
                metadata=metadata,
                feedback_rows=latest,
                seed_count=len(seed_rows),
                activate=False,
            )
            conn.execute("INSERT INTO candidate_registry VALUES (?,?,?,?,?)", (version_id, *registry_key))
        return {"version_id": version_id, "parent_id": int(active["id"]), "mode": mode,
                "feedback_count": trained_count, "reused": False}

    def current_evaluation(self, version_id: int):
        return self.repo.evaluation_for_version(version_id, dataset_hash(load_demo_rows("demo_eval.csv")))

    def activate(self, version_id: int) -> None:
        heldout_hash = dataset_hash(load_demo_rows("demo_eval.csv"))
        with self.repo.training_transaction() as conn:
            version = conn.execute("SELECT id FROM model_versions WHERE id=?", (version_id,)).fetchone()
            if not version:
                raise ValueError("Model version does not exist.")
            candidate = conn.execute("SELECT version_id FROM candidate_registry WHERE version_id=?", (version_id,)).fetchone()
            if candidate and not conn.execute(
                """SELECT id FROM evaluation_results WHERE updated_version_id=?
                   AND dataset_name='demo_eval.csv' AND heldout_hash=?""", (version_id, heldout_hash),
            ).fetchone():
                raise ValueError("Evaluate this candidate on the current held-out dataset before activation.")
            conn.execute("UPDATE model_versions SET is_active=0")
            conn.execute("UPDATE model_versions SET is_active=1 WHERE id=?", (version_id,))
            conn.execute("DELETE FROM candidate_registry WHERE version_id=?", (version_id,))

    def rollback(self, version_id: int) -> None:
        self.activate(version_id)

    def feedback_status(self, version_id: int) -> dict:
        membership = self.repo.feedback_membership(version_id)
        latest = self.repo.latest_feedback()
        included = sum(row["email_id"] in membership and
                       membership[row["email_id"]]["feedback_id"] == row["id"] for row in latest)
        return {"included": included, "omitted": len(latest) - included, "total": len(latest)}

    def preview_key(self, before_id: int, after_id: int) -> str:
        data = [before_id, after_id, [dict(row) for row in self.repo.export_rows()],
                [int(row["id"]) for row in self.repo.latest_feedback()]]
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def prediction_preview(self, before_id: int, after_id: int) -> dict:
        """Predict from immutable snapshots without persisting or rerouting anything."""
        versions = [self.repo.version(version_id) for version_id in (before_id, after_id)]
        if any(version is None for version in versions):
            raise ValueError("Model version does not exist.")
        bundles = [deserialize_bundle(version["model_blob"]) for version in versions]
        memberships = [self.repo.feedback_membership(version_id) for version_id in (before_id, after_id)]
        seed_keys = [{tuple(key) for key in json.loads(version["metadata_json"]).get(
            "seed_content_keys", [split_key(row) for row in load_demo_rows("demo_seed.csv")])} for version in versions]
        rows = []
        for raw in self.repo.export_rows():
            email = dict(raw)
            row = {"id": email["id"], "subject": email["subject"],
                   "human_category": email["corrected_category"], "human_priority": email["corrected_priority"]}
            for index, prefix in enumerate(("before", "after")):
                prediction = bundles[index].predict(email, versions[index]["id"],
                                                    self.settings.category_threshold, self.settings.priority_threshold)
                for field in ("category", "priority", "category_confidence", "priority_confidence"):
                    row[f"{prefix}_{field}"] = prediction[field]
                row[f"{prefix}_training_member"] = email["id"] in memberships[index] or split_key(email) in seed_keys[index]
            row["category_changed"] = row["before_category"] != row["after_category"]
            row["priority_changed"] = row["before_priority"] != row["after_priority"]
            row["changed"] = row["category_changed"] or row["priority_changed"]
            rows.append(row)
        return {"rows": rows, "total": len(rows), "changed": sum(row["changed"] for row in rows),
                "category_changed": sum(row["category_changed"] for row in rows),
                "priority_changed": sum(row["priority_changed"] for row in rows)}

    def compare_versions(self, updated_version_id: int | None = None, dataset_name: str = "demo_eval.csv") -> dict:
        baseline_row = next((row for row in self.repo.versions() if row["kind"] == "baseline"), None)
        if not baseline_row:
            raise RuntimeError("Baseline model version is missing.")
        updated_row = self.repo.version(updated_version_id) if updated_version_id else self.repo.active_version()
        if not updated_row:
            raise RuntimeError("Updated model version is missing.")
        eval_rows = load_demo_rows(dataset_name)
        train_rows = load_demo_rows("demo_seed.csv") + [dict(row) for row in self.repo._all(
            """SELECT e.* FROM emails e JOIN version_feedback vf ON vf.email_id=e.id
               WHERE vf.version_id=?""", (updated_row["id"],))]
        assert_split_isolated(train_rows, eval_rows)
        baseline_metrics = evaluate_bundle(deserialize_bundle(baseline_row["model_blob"]), eval_rows)
        updated_metrics = evaluate_bundle(deserialize_bundle(updated_row["model_blob"]), eval_rows)
        result = comparison_payload(
            baseline_metrics,
            updated_metrics,
            heldout_hash=dataset_hash(eval_rows),
            note="The held-out demonstration set is identical for both versions. Repeated inspection of this score is not an unbiased final benchmark.",
        )
        if updated_row["parent_id"]:
            parent = self.repo.version(updated_row["parent_id"])
            result["parent"] = evaluate_bundle(deserialize_bundle(parent["model_blob"]), eval_rows)
            result["parent_version"] = parent["label"]
        evaluation_id = self.repo.save_evaluation(
            int(baseline_row["id"]), int(updated_row["id"]), dataset_name, result["heldout_hash"], result
        )
        result["evaluation_id"] = evaluation_id
        result["baseline_version"] = baseline_row["label"]
        result["updated_version"] = updated_row["label"]
        return result

    def validation_tuning(self, target_precision: float = 0.80) -> dict:
        active = self.repo.active_version()
        if not active:
            raise RuntimeError("No active model version is available.")
        validation_rows = load_demo_rows("demo_validation.csv")
        train_rows = load_demo_rows("demo_seed.csv") + [_row_dict(row) for row in self.repo.latest_feedback()]
        assert_split_isolated(train_rows, validation_rows)
        result = tune_review_thresholds(deserialize_bundle(active["model_blob"]), validation_rows, target_precision)
        result["active_version"] = active["label"]
        return result

    def export_csv(self) -> bytes:
        fields = [
            "id", "subject", "body", "sender", "source", "created_at", "predicted_category", "predicted_priority",
            "category_confidence", "priority_confidence", "model_version_id", "status", "corrected_category", "corrected_priority",
            "effective_category", "effective_priority", "label_source",
        ]

        def safe(value) -> str:
            text = "" if value is None else str(value)
            if text.lstrip()[:1] in ("=", "+", "-", "@", "\t", "\r", "\n"):
                return "'" + text
            return text

        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in self.repo.export_rows():
            writer.writerow({field: safe(row[field]) for field in fields})
        return output.getvalue().encode("utf-8")

    def version_metadata(self, version_id: int) -> dict:
        row = self.repo.version(version_id)
        if not row:
            raise ValueError("Model version does not exist.")
        return json.loads(row["metadata_json"])
