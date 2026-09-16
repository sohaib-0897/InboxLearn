import hashlib
import json

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from .classifier import ModelBundle, row_text
from .config import CATEGORIES, PRIORITIES
from .validation import content_key, split_key


def dataset_hash(rows: list[dict]) -> str:
    # Labels are part of dataset identity: relabeling a held-out row invalidates scores.
    canonical = json.dumps([(content_key(row), row.get("category"), row.get("priority"))
                            for row in rows], ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assert_split_isolated(train_rows: list[dict], heldout_rows: list[dict]) -> None:
    train_keys = {split_key(row) for row in train_rows}
    overlap = train_keys & {split_key(row) for row in heldout_rows}
    if overlap:
        raise ValueError(f"Normalized-content overlap detected across splits ({len(overlap)} row(s)).")


def evaluate_bundle(bundle: ModelBundle, rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("Evaluation data is empty.")
    features = bundle.vectorizer.transform([row_text(row) for row in rows])
    predicted_categories = bundle.category_model.predict(features)
    predicted_priorities = bundle.priority_model.predict(features)
    actual_categories = [row["category"] for row in rows]
    actual_priorities = [row["priority"] for row in rows]
    return {
        "rows": len(rows),
        "category_accuracy": float(accuracy_score(actual_categories, predicted_categories)),
        "category_macro_f1": float(f1_score(actual_categories, predicted_categories, labels=CATEGORIES, average="macro", zero_division=0)),
        "category_confusion_matrix": confusion_matrix(actual_categories, predicted_categories, labels=CATEGORIES).tolist(),
        "category_labels": list(CATEGORIES),
        "priority_accuracy": float(accuracy_score(actual_priorities, predicted_priorities)),
        "priority_macro_f1": float(f1_score(actual_priorities, predicted_priorities, labels=PRIORITIES, average="macro", zero_division=0)),
        "priority_confusion_matrix": confusion_matrix(actual_priorities, predicted_priorities, labels=PRIORITIES).tolist(),
        "priority_labels": list(PRIORITIES),
    }


def tune_review_thresholds(bundle: ModelBundle, rows: list[dict], target_precision: float = 0.80) -> dict:
    """Suggest review thresholds from labelled validation data without changing the model."""
    if not rows:
        raise ValueError("Validation data is empty.")
    features = bundle.vectorizer.transform([row_text(row) for row in rows])
    category_probabilities = bundle.category_model.predict_proba(features)
    priority_probabilities = bundle.priority_model.predict_proba(features)
    category_confidence = np.max(category_probabilities, axis=1)
    priority_confidence = np.max(priority_probabilities, axis=1)
    category_correct = bundle.category_model.predict(features) == np.asarray([row["category"] for row in rows])
    priority_correct = bundle.priority_model.predict(features) == np.asarray([row["priority"] for row in rows])

    def choose(confidence, correct):
        candidates = [round(value, 2) for value in np.arange(0.50, 1.00, 0.05)]
        scored = []
        for threshold in candidates:
            accepted = confidence >= threshold
            precision = float(np.mean(correct[accepted])) if np.any(accepted) else 0.0
            coverage = float(np.mean(accepted))
            scored.append((threshold, precision, coverage))
        eligible = [item for item in scored if item[1] >= target_precision and item[2] > 0]
        chosen = eligible[0] if eligible else max(scored, key=lambda item: (item[1], item[2]))
        return {"threshold": chosen[0], "accepted_precision": chosen[1], "coverage": chosen[2]}

    return {
        "dataset": "demo_validation.csv",
        "rows": len(rows),
        "target_precision": target_precision,
        "category": choose(category_confidence, category_correct),
        "priority": choose(priority_confidence, priority_correct),
        "note": "Validation-only threshold suggestion. It changes no model version and should be treated as a tuning aid.",
    }


def comparison_payload(baseline: dict, updated: dict, *, heldout_hash: str, note: str) -> dict:
    return {
        "baseline": baseline,
        "updated": updated,
        "heldout_hash": heldout_hash,
        "note": note,
    }
