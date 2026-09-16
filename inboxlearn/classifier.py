import pickle
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier

from .config import CATEGORIES, PRIORITIES
from .validation import split_key


def row_text(row: dict) -> str:
    return f"subject: {row.get('subject', '')}\nsender: {row.get('sender', '')}\nbody: {row.get('body', '')}"


@dataclass
class ModelBundle:
    vectorizer: HashingVectorizer
    category_model: SGDClassifier
    priority_model: SGDClassifier
    random_state: int

    def predict(self, row: dict, model_version_id: int, category_threshold: float, priority_threshold: float) -> dict:
        features = self.vectorizer.transform([row_text(row)])
        category_probabilities = self.category_model.predict_proba(features)[0]
        priority_probabilities = self.priority_model.predict_proba(features)[0]
        category_index = int(np.argmax(category_probabilities))
        priority_index = int(np.argmax(priority_probabilities))
        category_confidence = float(category_probabilities[category_index])
        priority_confidence = float(priority_probabilities[priority_index])
        return {
            "category": str(self.category_model.classes_[category_index]),
            "priority": str(self.priority_model.classes_[priority_index]),
            "category_confidence": category_confidence,
            "priority_confidence": priority_confidence,
            "model_version_id": model_version_id,
            "status": "needs_review"
            if category_confidence < category_threshold or priority_confidence < priority_threshold
            else "classified",
        }


def _new_models(random_state: int) -> tuple[HashingVectorizer, SGDClassifier, SGDClassifier]:
    vectorizer = HashingVectorizer(
        n_features=2**12,
        alternate_sign=False,
        lowercase=True,
        ngram_range=(1, 2),
        norm="l2",
    )
    category_model = SGDClassifier(
        loss="log_loss", random_state=random_state, max_iter=1, tol=None, learning_rate="optimal"
    )
    priority_model = SGDClassifier(
        loss="log_loss", random_state=random_state, max_iter=1, tol=None, learning_rate="optimal"
    )
    return vectorizer, category_model, priority_model


def train_bundle(rows: list[dict], *, random_state: int = 42, base: ModelBundle | None = None, incremental: bool = False) -> ModelBundle:
    if not rows:
        raise ValueError("At least one labelled row is required to train.")
    for row in rows:
        split_key(row)  # Fail early instead of silently fitting labels to empty email text.
    if base is None:
        vectorizer, category_model, priority_model = _new_models(random_state)
    else:
        # Pickle is used here as a small, complete clone for safe version construction.
        vectorizer, category_model, priority_model = pickle.loads(pickle.dumps((base.vectorizer, base.category_model, base.priority_model)))
        random_state = base.random_state
    features = vectorizer.transform([row_text(row) for row in rows])
    categories = np.asarray([row["category"] for row in rows])
    priorities = np.asarray([row["priority"] for row in rows])
    if base is None or not incremental:
        category_model.partial_fit(features, categories, classes=np.asarray(CATEGORIES))
        priority_model.partial_fit(features, priorities, classes=np.asarray(PRIORITIES))
    else:
        category_model.partial_fit(features, categories)
        priority_model.partial_fit(features, priorities)
    return ModelBundle(vectorizer, category_model, priority_model, random_state)


def serialize_bundle(bundle: ModelBundle) -> bytes:
    return pickle.dumps(bundle, protocol=pickle.HIGHEST_PROTOCOL)


def deserialize_bundle(blob: bytes) -> ModelBundle:
    bundle = pickle.loads(blob)
    if not isinstance(bundle, ModelBundle):
        raise ValueError("Stored model is not an InboxLearn model bundle.")
    return bundle
