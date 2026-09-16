"""Reproduce the fixed synthetic learning protocol in a private temporary database.

Run: .venv/Scripts/python scripts/experiment.py
Only reports/learning.{json,md} survive the run. INBOXLEARN_DB is never used.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
from itertools import combinations
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from inboxlearn.classifier import deserialize_bundle
from inboxlearn.config import Settings
from inboxlearn.demo import demo_data_path, load_demo_rows
from inboxlearn.evaluation import assert_split_isolated, dataset_hash
from inboxlearn.service import InboxLearnService
from inboxlearn.validation import content_hash, split_key

METRICS = {"category_accuracy": "Category accuracy", "category_macro_f1": "Category macro-F1",
           "priority_accuracy": "Priority accuracy", "priority_macro_f1": "Priority macro-F1"}


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unlabeled(row):
    return {key: row.get(key, "") for key in ("subject", "body", "sender")}


def predict_active(service, rows):
    version = service.active_version()
    model = deserialize_bundle(version["model_blob"])
    return [model.predict(unlabeled(row), int(version["id"]), service.settings.category_threshold,
                          service.settings.priority_threshold) for row in rows]


def confirm_demo_feedback(service, feedback):
    """Replay fixed, pre-authored synthetic labels through the human feedback API."""
    emails = {row["content_hash"]: row for row in service.repo.inbox_rows()}
    ids = []
    for example in feedback:
        email = emails[content_hash(example)]
        correction_id, created = service.save_feedback(email["id"], example["category"], example["priority"])
        if not created:
            raise AssertionError("Expected a fresh correction in the isolated experiment.")
        ids.append(correction_id)
    return ids


def run_experiment(scratch_root=None):
    """Return measured JSON-serializable evidence. No caller database is accepted."""
    splits = {name: load_demo_rows(f"demo_{name}.csv") for name in ("seed", "feedback", "validation", "eval")}
    overlap = {}
    for first, second in combinations(splits, 2):
        assert_split_isolated(splits[first], splits[second])
        overlap[f"{first}/{second}"] = len({split_key(r) for r in splits[first]} & {split_key(r) for r in splits[second]})
    scratch = Path(scratch_root) if scratch_root else ROOT / "runtime" / "experiments"
    scratch.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="inboxlearn-", dir=scratch) as directory:
        settings = Settings(db_path=Path(directory) / "experiment.sqlite3", random_state=42,
                            category_threshold=0.7, priority_threshold=0.7)
        service = InboxLearnService(settings)
        baseline_version = service.active_version()
        baseline_model = deserialize_bundle(baseline_version["model_blob"])
        probes = splits["feedback"] + splits["eval"]
        before = predict_active(service, probes)
        initial_score = service.compare_versions(int(baseline_version["id"]))

        imported = service.classify_upload(demo_data_path("demo_feedback.csv").read_bytes(), source="synthetic-experiment")
        assert imported["new"] == len(splits["feedback"])
        assert service.repo.pending_feedback_count() == 0  # Predictions are never feedback.
        feedback_ids = confirm_demo_feedback(service, splits["feedback"])
        original_predictions = [dict(row) for row in service.repo.inbox_rows()]
        trained = service.train()
        assert trained["mode"] == "incremental_feedback"
        assert trained["feedback_count"] == len(feedback_ids)
        assert predict_active(service, probes) == before
        assert service.train()["version_id"] == trained["version_id"]
        updated_version = service.repo.version(trained["version_id"])
        updated_model = deserialize_bundle(updated_version["model_blob"])
        preview = service.prediction_preview(baseline_version["id"], updated_version["id"])
        try:
            service.activate(updated_version["id"])
        except ValueError:
            pass
        else:
            raise AssertionError("Unevaluated candidates must not activate.")
        scored = service.compare_versions(int(updated_version["id"]))
        service.activate(int(updated_version["id"]))
        after = predict_active(service, probes)
        assert scored["baseline"] == initial_score["baseline"]
        assert scored["heldout_hash"] == initial_score["heldout_hash"] == dataset_hash(splits["eval"])
        assert service.repo.pending_feedback_count() == 0
        assert service.train() is None  # Repeating the request must not learn labels twice.
        assert len(service.repo.versions()) == 2
        membership = service.repo.feedback_membership(int(updated_version["id"]))
        assert {r["feedback_id"] for r in membership.values()} == set(feedback_ids)
        assert [dict(row) for row in service.repo.inbox_rows()] == original_predictions
        updates = {}
        for target in ("category", "priority"):
            base_clf = getattr(baseline_model, target + "_model")
            updated_clf = getattr(updated_model, target + "_model")
            assert updated_clf.t_ - base_clf.t_ == len(feedback_ids)
            assert not np.array_equal(base_clf.coef_, updated_clf.coef_)
            updates[target] = {
                "new_examples_seen": int(updated_clf.t_ - base_clf.t_),
                "coefficient_l2_change": float(np.linalg.norm(updated_clf.coef_ - base_clf.coef_)),
                "changed_probe_labels": sum(a[target] != b[target] for a, b in zip(before, after)),
            }

        service.rollback(int(baseline_version["id"]))
        # Reopen from SQLite; verify actual model state, not merely an activation flag.
        restored = InboxLearnService(settings)
        rolled_back_predictions = predict_active(restored, probes)
        assert rolled_back_predictions == before
        assert restored.active_version()["model_blob"] == baseline_version["model_blob"]
        assert restored.repo.pending_feedback_count() == len(feedback_ids)
        result = {
            "protocol": "inboxlearn-synthetic-v2-candidate-workflow",
            "data_type": "Synthetic demonstration data; not a real-world accuracy estimate.",
            "label_source": "Pre-authored synthetic category/priority labels in demo_feedback.csv, replayed through save_feedback; not predictions or evaluation labels.",
            "random_state": settings.random_state,
            "thresholds": {"category": settings.category_threshold, "priority": settings.priority_threshold},
            "splits": {name: {"file": f"data/demo_{name}.csv", "rows": len(rows),
                               "sha256": fingerprint(demo_data_path(f"demo_{name}.csv")),
                               "category_counts": dict(Counter(r["category"] for r in rows)),
                               "priority_counts": dict(Counter(r["priority"] for r in rows))} for name, rows in splits.items()},
            "overlap": {"normalization": "Unicode NFKC, casefold and whitespace collapse on subject/body; sender ignored", "pair_counts": overlap},
            "validation_used_for_tuning": False,
            "training": {"mode": trained["mode"], "seed_rows": len(splits["seed"]),
                         "feedback_rows": len(feedback_ids), "feedback_ids": feedback_ids,
                         "membership": [dict(row) for row in membership.values()], "updates": updates,
                         "repeat_training_was_noop": True, "original_predictions_preserved": True,
                         "repeat_preparation_reused_candidate": True,
                         "active_predictions_unchanged_before_activation": True,
                         "unevaluated_activation_rejected": True,
                         "evaluated_before_activation": True},
            "inbox_preview": preview,
            "versions": {"baseline": baseline_version["label"], "updated": updated_version["label"],
                         "parent_id": updated_version["parent_id"], "active_after_rollback": restored.active_version()["label"]},
            "baseline": scored["baseline"], "updated": scored["updated"],
            "absolute_changes": {key: scored["updated"][key] - scored["baseline"][key] for key in METRICS},
            "heldout_hash": scored["heldout_hash"],
            "rollback": {"probes": len(probes), "predictions_and_confidences_identical": True,
                         "model_blob_identical": True, "feedback_retained": len(restored.repo.latest_feedback())},
            "probe_predictions": [{"split": "feedback" if i < len(splits["feedback"]) else "eval",
                                   "content_hash": content_hash(row), "baseline": before[i],
                                   "updated": after[i], "rollback": rolled_back_predictions[i]}
                                  for i, row in enumerate(probes)],
            "dependencies": {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in
                             ("scikit-learn", "numpy", "scipy", "joblib", "threadpoolctl", "pandas", "streamlit", "pytest")}},
            "source_sha256": {name: fingerprint(ROOT / name) for name in (
                "scripts/experiment.py", "inboxlearn/service.py", "inboxlearn/db.py", "inboxlearn/classifier.py",
                "inboxlearn/evaluation.py", "inboxlearn/validation.py", "inboxlearn/config.py")},
        }
    result["temporary_database_removed"] = not Path(directory).exists()
    assert result["temporary_database_removed"]
    return result


def markdown_report(result):
    counts = {name: split["rows"] for name, split in result["splits"].items()}
    lines = ["# Synthetic learning experiment", "", result["data_type"], "",
             f"Fixed protocol: {counts['seed']} synthetic seed examples → classify {counts['feedback']} separate feedback emails → replay their pre-authored labels through the human-feedback service → prepare an inactive candidate → inspect inbox prediction changes → evaluate on the same {counts['eval']} held-out examples → explicitly activate → roll back to v1.", "",
             f"The {counts['validation']} validation examples were checked for split isolation but not used for tuning. No thresholds, model parameters or examples were selected in response to held-out scores.", "",
             "| Metric | Baseline v1 | Updated v2 | Absolute change (v2 − v1) | Outcome |",
             "|---|---:|---:|---:|---|"]
    for key, title in METRICS.items():
        delta = result["absolute_changes"][key]
        outcome = "Regression" if delta < 0 else "Increase" if delta > 0 else "Unchanged"
        lines.append(f"| {title} | {result['baseline'][key]:.4f} | {result['updated'][key]:.4f} | {delta:+.4f} | {outcome} |")
    not_improved = [title for key, title in METRICS.items() if result["absolute_changes"][key] <= 0]
    remaining_errors = []
    for target in ("category", "priority"):
        for i, label in enumerate(result["updated"][target + "_labels"]):
            row = result["updated"][target + "_confusion_matrix"][i]
            before = result["baseline"][target + "_confusion_matrix"][i][i]
            if row[i] < sum(row):
                remaining_errors.append(f"- {target.title()} / {label}: {row[i]}/{sum(row)} correct after training (baseline {before}/{sum(row)}).")
    lines += ["", "Values are on a 0–1 scale; changes are signed score-point differences, not relative percentages.", "",
              "Did not improve: " + (", ".join(not_improved) if not_improved else "none of the four metrics in this particular synthetic run") + ".", "",
              "Remaining class-level errors:", "", *remaining_errors, "",
              "## What changed", "",
              f"Candidate preparation left active predictions unchanged and repeated preparation returned the same candidate. Activation was rejected before evaluation. The read-only inbox preview found {result['inbox_preview']['changed']} of {result['inbox_preview']['total']} messages with changed category or priority labels; these feedback training members are not held-out accuracy evidence. The candidate was evaluated before explicit activation.", "",
              "Both classifiers consumed exactly 5 new human-label fixtures through partial_fit; their coefficients changed. Feedback email content is joined to its latest saved labels. Earlier verification found that this join was missing; a regression test now checks that service updates equal updates made directly with the actual email text. Missing text fails early, and overlap with the held-out or validation splits is rejected before fitting.", "",
              "Only the new v2 model changed. Original predictions, the v1 snapshot, all fixture files, model hyperparameters and thresholds stayed fixed. No prediction was reused as a training label. Repeated training was a no-op. The separate validation set was not tuned in this experiment.", "",
              f"Rollback restored v1's exact labels AND confidence estimates on {result['rollback']['probes']} probes (5 feedback + 10 held-out), including after reopening SQLite. The stored model bytes matched exactly. Human feedback remained available. All six split-pair overlap checks returned zero.", "",
              "## Limitations", "",
              "These small, English-language, synthetic fixtures demonstrate mechanics, not real-world generalization. The replayed labels are demonstration ground truth, not newly collected human annotations. Confidence is uncalibrated. Test scores have been repeatedly inspected during development and are not an unbiased final benchmark; use new independent data for that purpose. Feedback can cause regressions. Actions are suggestions only; no sending, deletion, payments or integrations. Hash normalization detects exact normalized duplicates, not semantic paraphrases. Serialized model compatibility depends on the Python/scikit-learn environment; old user versions are not rewritten by this verification.", "",
              "## Reproduce", "", "```powershell", ".\\.venv\\Scripts\\python.exe scripts\\experiment.py", "```", "",
              "This command creates and removes its own temporary database under runtime/experiments, ignores INBOXLEARN_DB, and writes only reports/learning.json and reports/learning.md. Run with the dependency versions recorded in the JSON for the closest numerical reproduction. JSON includes full precision metrics, confusion matrices, fixture and source hashes, class counts, model changes and per-probe rollback evidence.", ""]
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    result = run_experiment()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "learning.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = markdown_report(result)
    (args.output_dir / "learning.md").write_text(report, encoding="utf-8")
    print(report.split("## What changed")[0])
    print(f"Rollback: exact labels/confidences restored on {result['rollback']['probes']} probes; temporary database removed.")
    print(f"Artifacts: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
