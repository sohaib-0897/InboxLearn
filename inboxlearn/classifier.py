from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier

from .config import CATEGORIES, PRIORITIES
from .validation import split_key

MAGIC = b"IBL1\x00"
MAX_MODEL_BLOB_SIZE = 10 * 1024 * 1024  # 10 MiB limit on serialized payload
MAX_UNCOMPRESSED_PAYLOAD = 5 * 1024 * 1024  # 5 MiB uncompressed array buffer limit


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


def _clone_sgd(clf: SGDClassifier, random_state: int) -> SGDClassifier:
    new_clf = SGDClassifier(
        loss="log_loss",
        random_state=random_state,
        max_iter=1,
        tol=None,
        learning_rate="optimal",
    )
    if hasattr(clf, "classes_"):
        new_clf.classes_ = np.copy(clf.classes_)
    if hasattr(clf, "coef_"):
        new_clf.coef_ = np.copy(clf.coef_)
    if hasattr(clf, "intercept_"):
        new_clf.intercept_ = np.copy(clf.intercept_)
    if hasattr(clf, "t_"):
        new_clf.t_ = float(clf.t_)
    return new_clf


def clone_bundle(base: ModelBundle) -> ModelBundle:
    """In-memory deep copy of a model bundle without Python pickle serialization."""
    vec = HashingVectorizer(
        n_features=2**12,
        alternate_sign=False,
        lowercase=True,
        ngram_range=(1, 2),
        norm="l2",
    )
    cat = _clone_sgd(base.category_model, base.random_state)
    prio = _clone_sgd(base.priority_model, base.random_state)
    return ModelBundle(vec, cat, prio, base.random_state)


def train_bundle(rows: list[dict], *, random_state: int = 42, base: ModelBundle | None = None, incremental: bool = False) -> ModelBundle:
    if not rows:
        raise ValueError("At least one labelled row is required to train.")
    for row in rows:
        split_key(row)  # Fail early instead of silently fitting labels to empty email text.
    if base is None:
        vectorizer, category_model, priority_model = _new_models(random_state)
    else:
        cloned = clone_bundle(base)
        vectorizer, category_model, priority_model = cloned.vectorizer, cloned.category_model, cloned.priority_model
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
    """Safely serialize model state to an explicit, non-executable binary format.

    Structure:
      - 5 bytes magic header: b"IBL1\x00"
      - 4 bytes unsigned int (big-endian): header JSON byte length
      - UTF-8 JSON header: metadata, shapes, classes, and payload SHA-256
      - zlib-compressed binary payload: contiguous float64 array buffers
    """
    cat = bundle.category_model
    prio = bundle.priority_model

    cat_classes = [str(c) for c in cat.classes_]
    prio_classes = [str(c) for c in prio.classes_]

    cat_coef = np.ascontiguousarray(cat.coef_, dtype=np.float64)
    cat_intercept = np.ascontiguousarray(cat.intercept_, dtype=np.float64)
    prio_coef = np.ascontiguousarray(prio.coef_, dtype=np.float64)
    prio_intercept = np.ascontiguousarray(prio.intercept_, dtype=np.float64)

    raw_payload = cat_coef.tobytes() + cat_intercept.tobytes() + prio_coef.tobytes() + prio_intercept.tobytes()
    payload_sha256 = hashlib.sha256(raw_payload).hexdigest()
    compressed_payload = zlib.compress(raw_payload, level=6)

    header = {
        "format_version": 1,
        "random_state": int(bundle.random_state),
        "vectorizer": {
            "n_features": 4096,
            "ngram_range": [1, 2],
            "alternate_sign": False,
            "lowercase": True,
            "norm": "l2",
        },
        "category": {
            "classes": cat_classes,
            "coef_shape": list(cat_coef.shape),
            "intercept_shape": list(cat_intercept.shape),
            "t": float(getattr(cat, "t_", 0.0)),
        },
        "priority": {
            "classes": prio_classes,
            "coef_shape": list(prio_coef.shape),
            "intercept_shape": list(prio_intercept.shape),
            "t": float(getattr(prio, "t_", 0.0)),
        },
        "payload_sha256": payload_sha256,
        "payload_size": len(raw_payload),
    }
    header_bytes = json.dumps(header, sort_keys=True).encode("utf-8")
    header_len = len(header_bytes)
    return MAGIC + struct.pack(">I", header_len) + header_bytes + compressed_payload


def deserialize_bundle(blob: bytes) -> ModelBundle:
    """Safely reconstruct a ModelBundle from validated explicit primitive data.

    Rejects legacy pickle blobs, oversized blobs, corrupt headers, shape mismatches,
    non-finite values, and payload checksum mismatches. Zero arbitrary code execution.
    """
    if not isinstance(blob, (bytes, bytearray, memoryview)):
        raise ValueError("Model blob must be bytes.")
    blob = bytes(blob)

    if len(blob) > MAX_MODEL_BLOB_SIZE:
        raise ValueError(f"Model blob size ({len(blob)} bytes) exceeds maximum permitted limit ({MAX_MODEL_BLOB_SIZE} bytes).")

    if blob.startswith(b"\x80"):
        raise ValueError(
            "Legacy pickle model blob detected. Automatic unpickling of untrusted databases is disabled for security. "
            "Use migrate_legacy_database(db_path, trusted=True) or migrate_legacy_model_blob(blob, trusted=True) "
            "to convert trusted legacy models to the safe IBL1 format."
        )

    if not blob.startswith(MAGIC):
        raise ValueError("Invalid model blob: missing or corrupted IBL1 magic header.")

    magic_len = len(MAGIC)
    if len(blob) < magic_len + 4:
        raise ValueError("Model blob is truncated before header length.")

    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    if header_len < 10 or header_len > 65536:
        raise ValueError(f"Invalid model header length ({header_len} bytes).")

    header_end = magic_len + 4 + header_len
    if len(blob) < header_end:
        raise ValueError("Model blob is truncated before end of header.")

    header_bytes = blob[magic_len + 4:header_end]
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Malformed model header JSON: {e}") from e

    expected_keys = {"format_version", "random_state", "vectorizer", "category", "priority", "payload_sha256", "payload_size"}
    if not expected_keys.issubset(header.keys()):
        missing = expected_keys - set(header.keys())
        raise ValueError(f"Model header missing required fields: {sorted(missing)}")

    if header["format_version"] != 1:
        raise ValueError(f"Unsupported model format version: {header['format_version']}. Supported versions: [1].")

    # Validate vectorizer parameters
    vec_params = header["vectorizer"]
    if vec_params.get("n_features") != 4096 or vec_params.get("ngram_range") != [1, 2] or vec_params.get("alternate_sign") is not False:
        raise ValueError("Model vectorizer configuration does not match expected architecture.")

    expected_payload_size = header["payload_size"]
    if expected_payload_size > MAX_UNCOMPRESSED_PAYLOAD:
        raise ValueError(f"Declared payload size ({expected_payload_size} bytes) exceeds limit ({MAX_UNCOMPRESSED_PAYLOAD} bytes).")

    compressed_payload = blob[header_end:]
    try:
        decompressor = zlib.decompressobj()
        raw_payload = decompressor.decompress(compressed_payload, MAX_UNCOMPRESSED_PAYLOAD)
        if decompressor.unconsumed_tail:
            raise ValueError("Excess payload bytes after decompression.")
    except Exception as e:
        raise ValueError(f"Payload decompression failed: {e}") from e

    if len(raw_payload) != expected_payload_size:
        raise ValueError(f"Decompressed payload size mismatch: expected {expected_payload_size}, got {len(raw_payload)}.")

    actual_sha256 = hashlib.sha256(raw_payload).hexdigest()
    if actual_sha256 != header["payload_sha256"]:
        raise ValueError("Model payload SHA-256 integrity checksum mismatch.")

    # Validate category specifications
    cat_info = header["category"]
    cat_classes = cat_info["classes"]
    for c in cat_classes:
        if c not in CATEGORIES:
            raise ValueError(f"Unrecognized category label in model header: {c}")

    cat_shape = tuple(cat_info["coef_shape"])
    if len(cat_shape) != 2 or cat_shape[0] != len(cat_classes) or cat_shape[1] != 4096:
        raise ValueError(f"Category coefficient shape mismatch: {cat_shape}.")
    cat_size = int(np.prod(cat_shape)) * 8

    cat_intercept_shape = tuple(cat_info["intercept_shape"])
    if len(cat_intercept_shape) != 1 or cat_intercept_shape[0] != len(cat_classes):
        raise ValueError(f"Category intercept shape mismatch: {cat_intercept_shape}.")
    cat_intercept_size = int(np.prod(cat_intercept_shape)) * 8

    # Validate priority specifications
    prio_info = header["priority"]
    prio_classes = prio_info["classes"]
    for p in prio_classes:
        if p not in PRIORITIES:
            raise ValueError(f"Unrecognized priority label in model header: {p}")

    prio_shape = tuple(prio_info["coef_shape"])
    if len(prio_shape) != 2 or prio_shape[0] != len(prio_classes) or prio_shape[1] != 4096:
        raise ValueError(f"Priority coefficient shape mismatch: {prio_shape}.")
    prio_size = int(np.prod(prio_shape)) * 8

    prio_intercept_shape = tuple(prio_info["intercept_shape"])
    if len(prio_intercept_shape) != 1 or prio_intercept_shape[0] != len(prio_classes):
        raise ValueError(f"Priority intercept shape mismatch: {prio_intercept_shape}.")
    prio_intercept_size = int(np.prod(prio_intercept_shape)) * 8

    total_expected = cat_size + cat_intercept_size + prio_size + prio_intercept_size
    if total_expected != expected_payload_size:
        raise ValueError("Payload segment declarations do not sum to total payload size.")

    # Slice array buffers
    offset = 0
    cat_coef = np.frombuffer(raw_payload[offset:offset + cat_size], dtype=np.float64).reshape(cat_shape)
    offset += cat_size
    cat_intercept = np.frombuffer(raw_payload[offset:offset + cat_intercept_size], dtype=np.float64).reshape(cat_intercept_shape)
    offset += cat_intercept_size
    prio_coef = np.frombuffer(raw_payload[offset:offset + prio_size], dtype=np.float64).reshape(prio_shape)
    offset += prio_size
    prio_intercept = np.frombuffer(raw_payload[offset:offset + prio_intercept_size], dtype=np.float64).reshape(prio_intercept_shape)

    # Validate weights are finite numbers
    if not (np.all(np.isfinite(cat_coef)) and np.all(np.isfinite(cat_intercept)) and
            np.all(np.isfinite(prio_coef)) and np.all(np.isfinite(prio_intercept))):
        raise ValueError("Model weight arrays contain non-finite values (NaN or Inf).")

    # Reconstruct bundle
    rand_state = int(header["random_state"])
    vec = HashingVectorizer(n_features=4096, alternate_sign=False, lowercase=True, ngram_range=(1, 2), norm="l2")

    cat_model = SGDClassifier(loss="log_loss", random_state=rand_state, max_iter=1, tol=None, learning_rate="optimal")
    cat_model.classes_ = np.array(cat_classes)
    cat_model.coef_ = np.copy(cat_coef)
    cat_model.intercept_ = np.copy(cat_intercept)
    cat_model.t_ = float(cat_info.get("t", 0.0))

    prio_model = SGDClassifier(loss="log_loss", random_state=rand_state, max_iter=1, tol=None, learning_rate="optimal")
    prio_model.classes_ = np.array(prio_classes)
    prio_model.coef_ = np.copy(prio_coef)
    prio_model.intercept_ = np.copy(prio_intercept)
    prio_model.t_ = float(prio_info.get("t", 0.0))

    return ModelBundle(vec, cat_model, prio_model, rand_state)


def migrate_legacy_model_blob(blob: bytes, *, trusted: bool = False) -> bytes:
    """Migrate a legacy pickle model blob to the safe IBL1 format.

    Requires trusted=True to acknowledge that the blob originates from a trusted local source.
    """
    if not trusted:
        raise ValueError(
            "Refusing to unpickle legacy model blob without explicit trusted=True acknowledgment. "
            "Only migrate databases from trusted sources."
        )
    if blob.startswith(MAGIC):
        return blob  # Already in safe format
    if not blob.startswith(b"\x80"):
        raise ValueError("Unrecognized blob format; neither IBL1 nor legacy pickle.")
    import pickle
    bundle = pickle.loads(blob)
    if not isinstance(bundle, ModelBundle):
        raise ValueError("Stored pickle object is not an InboxLearn ModelBundle.")
    return serialize_bundle(bundle)


def migrate_legacy_database(db_path: str | Path, *, trusted: bool = False) -> int:
    """Convert all legacy pickle model blobs in a SQLite database to safe IBL1 format.

    Runs inside an exclusive transaction. Returns the number of migrated versions.
    """
    if not trusted:
        raise ValueError(
            "Refusing to migrate legacy database without explicit trusted=True acknowledgment."
        )
    import sqlite3
    migrated = 0
    with sqlite3.connect(str(db_path), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute("SELECT id, model_blob FROM model_versions").fetchall()
        for row in rows:
            blob = row["model_blob"]
            if blob.startswith(b"\x80"):
                safe_blob = migrate_legacy_model_blob(blob, trusted=True)
                conn.execute("UPDATE model_versions SET model_blob=? WHERE id=?", (safe_blob, row["id"]))
                migrated += 1
        conn.commit()
    return migrated
