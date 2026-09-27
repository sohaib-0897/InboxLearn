import json
import pickle
import struct
import zlib
import numpy as np
import pytest

from inboxlearn.classifier import (
    MAGIC,
    MAX_MODEL_BLOB_SIZE,
    MAX_UNCOMPRESSED_PAYLOAD,
    ModelBundle,
    _new_models,
    clone_bundle,
    deserialize_bundle,
    migrate_legacy_database,
    migrate_legacy_model_blob,
    serialize_bundle,
    train_bundle,
)
from inboxlearn.config import Settings
from inboxlearn.demo import load_demo_rows
from inboxlearn.evaluation import assert_split_isolated, evaluate_bundle
from inboxlearn.service import InboxLearnService


@pytest.fixture
def sample_bundle():
    seed = load_demo_rows("demo_seed.csv")
    return train_bundle(seed, random_state=42)


def test_safe_serialization_roundtrip_and_predict_match(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    assert blob.startswith(MAGIC)
    restored = deserialize_bundle(blob)
    assert restored.random_state == sample_bundle.random_state

    # Verify identical predictions on seed rows
    seed = load_demo_rows("demo_seed.csv")
    for row in seed:
        p1 = sample_bundle.predict(row, 1, 0.7, 0.7)
        p2 = restored.predict(row, 1, 0.7, 0.7)
        assert p1 == p2


def test_clone_bundle_is_independent(sample_bundle):
    cloned = clone_bundle(sample_bundle)
    # Mutate cloned via partial_fit
    feedback = load_demo_rows("demo_feedback.csv")
    train_bundle(feedback, base=cloned, incremental=True)

    # Original should be untouched
    seed = load_demo_rows("demo_seed.csv")
    for row in seed:
        orig_pred = sample_bundle.predict(row, 1, 0.7, 0.7)
        cloned_pred = cloned.predict(row, 1, 0.7, 0.7)
        assert orig_pred == cloned_pred


def test_corrupted_magic_header():
    with pytest.raises(ValueError, match="missing or corrupted IBL1 magic header"):
        deserialize_bundle(b"BAD1\x00somepayload")


def test_truncated_blob():
    with pytest.raises(ValueError, match="truncated before header length"):
        deserialize_bundle(b"IBL1\x00\x00")


def test_corrupted_header_json(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    magic_len = len(MAGIC)
    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    corrupted_header = b"{" + b"X" * (header_len - 1)
    corrupted_blob = blob[:magic_len + 4] + corrupted_header + blob[magic_len + 4 + header_len:]
    with pytest.raises(ValueError, match="Malformed model header JSON"):
        deserialize_bundle(corrupted_blob)


def test_missing_header_keys(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    magic_len = len(MAGIC)
    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    header = json.loads(blob[magic_len + 4:magic_len + 4 + header_len].decode("utf-8"))
    del header["category"]
    new_h_bytes = json.dumps(header).encode("utf-8")
    new_blob = MAGIC + struct.pack(">I", len(new_h_bytes)) + new_h_bytes + blob[magic_len + 4 + header_len:]
    with pytest.raises(ValueError, match="missing required fields"):
        deserialize_bundle(new_blob)


def test_unsupported_format_version(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    magic_len = len(MAGIC)
    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    header = json.loads(blob[magic_len + 4:magic_len + 4 + header_len].decode("utf-8"))
    header["format_version"] = 99
    new_h_bytes = json.dumps(header).encode("utf-8")
    new_blob = MAGIC + struct.pack(">I", len(new_h_bytes)) + new_h_bytes + blob[magic_len + 4 + header_len:]
    with pytest.raises(ValueError, match="Unsupported model format version: 99"):
        deserialize_bundle(new_blob)


def test_corrupted_zlib_payload(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    magic_len = len(MAGIC)
    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    header_end = magic_len + 4 + header_len
    corrupted_blob = blob[:header_end] + b"\x00\x01\x02\x03\x04"
    with pytest.raises(ValueError, match="Payload decompression failed"):
        deserialize_bundle(corrupted_blob)


def test_payload_sha256_checksum_mismatch(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    magic_len = len(MAGIC)
    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    header = json.loads(blob[magic_len + 4:magic_len + 4 + header_len].decode("utf-8"))
    header["payload_sha256"] = "0" * 64
    new_h_bytes = json.dumps(header).encode("utf-8")
    new_blob = MAGIC + struct.pack(">I", len(new_h_bytes)) + new_h_bytes + blob[magic_len + 4 + header_len:]
    with pytest.raises(ValueError, match="Model payload SHA-256 integrity checksum mismatch"):
        deserialize_bundle(new_blob)


def test_shape_mismatches(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    magic_len = len(MAGIC)
    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    header = json.loads(blob[magic_len + 4:magic_len + 4 + header_len].decode("utf-8"))
    # Corrupt category shape
    header["category"]["coef_shape"] = [5, 2048]
    new_h_bytes = json.dumps(header).encode("utf-8")
    new_blob = MAGIC + struct.pack(">I", len(new_h_bytes)) + new_h_bytes + blob[magic_len + 4 + header_len:]
    with pytest.raises(ValueError, match="Category coefficient shape mismatch"):
        deserialize_bundle(new_blob)


def test_unrecognized_category_classes(sample_bundle):
    blob = serialize_bundle(sample_bundle)
    magic_len = len(MAGIC)
    header_len = struct.unpack(">I", blob[magic_len:magic_len + 4])[0]
    header = json.loads(blob[magic_len + 4:magic_len + 4 + header_len].decode("utf-8"))
    header["category"]["classes"][0] = "unauthorized_class"
    new_h_bytes = json.dumps(header).encode("utf-8")
    new_blob = MAGIC + struct.pack(">I", len(new_h_bytes)) + new_h_bytes + blob[magic_len + 4 + header_len:]
    with pytest.raises(ValueError, match="Unrecognized category label"):
        deserialize_bundle(new_blob)


def test_non_finite_weights_rejected(sample_bundle):
    # Inject NaN into weights
    cat = sample_bundle.category_model
    original_coef = np.copy(cat.coef_)
    cat.coef_[0, 0] = np.nan
    try:
        blob = serialize_bundle(sample_bundle)
        with pytest.raises(ValueError, match="Model weight arrays contain non-finite values"):
            deserialize_bundle(blob)
    finally:
        cat.coef_ = original_coef


def test_oversized_payload_rejected(sample_bundle):
    oversized = b"IBL1\x00" + b"\x00" * (MAX_MODEL_BLOB_SIZE + 1)
    with pytest.raises(ValueError, match="exceeds maximum permitted limit"):
        deserialize_bundle(oversized)


def test_legacy_pickle_rejected_by_default(sample_bundle):
    legacy_pickle = pickle.dumps(sample_bundle)
    with pytest.raises(ValueError, match="Legacy pickle model blob detected"):
        deserialize_bundle(legacy_pickle)


def test_legacy_pickle_trusted_migration(sample_bundle):
    legacy_pickle = pickle.dumps(sample_bundle)
    with pytest.raises(ValueError, match="Refusing to unpickle legacy model blob without explicit trusted=True"):
        migrate_legacy_model_blob(legacy_pickle, trusted=False)

    safe_blob = migrate_legacy_model_blob(legacy_pickle, trusted=True)
    assert safe_blob.startswith(MAGIC)
    restored = deserialize_bundle(safe_blob)
    assert restored.random_state == sample_bundle.random_state


def test_migrate_legacy_database(tmp_path, sample_bundle):
    import sqlite3
    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE model_versions (id INTEGER PRIMARY KEY, model_blob BLOB)")
        legacy_pickle = pickle.dumps(sample_bundle)
        conn.execute("INSERT INTO model_versions VALUES (1, ?)", (legacy_pickle,))
        conn.commit()

    with pytest.raises(ValueError, match="Refusing to migrate legacy database without explicit trusted=True"):
        migrate_legacy_database(db_path, trusted=False)

    count = migrate_legacy_database(db_path, trusted=True)
    assert count == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT model_blob FROM model_versions WHERE id=1").fetchone()
        assert row["model_blob"].startswith(MAGIC)
        bundle = deserialize_bundle(row["model_blob"])
        assert bundle.random_state == sample_bundle.random_state


def test_rollback_after_safe_serialization(tmp_path):
    db_path = tmp_path / "service_test.sqlite3"
    service = InboxLearnService(Settings(db_path=db_path))

    # Ingest and correct
    feedback = load_demo_rows("demo_feedback.csv")
    payload = b"subject,body\n" + b"\n".join(f'"{r["subject"]}","{r["body"]}"'.encode("utf-8") for r in feedback)
    service.classify_upload(payload)
    email_id = service.repo.inbox_rows()[0]["id"]
    service.save_feedback(email_id, "bills", "high")

    cand = service.train()
    cand_id = cand["version_id"]
    # Check evaluation gate
    service.compare_versions(cand_id)
    service.activate(cand_id)
    assert service.active_version()["id"] == cand_id

    # Roll back
    service.rollback(1)
    assert service.active_version()["id"] == 1
    # Check model blob is valid IBL1
    assert service.active_version()["model_blob"].startswith(MAGIC)


def test_expanded_evaluation_split_isolation_and_execution(tmp_path):
    seed = load_demo_rows("demo_seed.csv")
    feedback = load_demo_rows("demo_feedback.csv")
    eval_hist = load_demo_rows("demo_eval.csv")
    validation = load_demo_rows("demo_validation.csv")
    expanded = load_demo_rows("demo_eval_expanded.csv")

    assert len(expanded) == 25
    for name, rows in [("seed", seed), ("feedback", feedback), ("validation", validation), ("eval", eval_hist)]:
        assert_split_isolated(expanded, rows)

    v1 = train_bundle(seed, random_state=42)
    res = evaluate_bundle(v1, expanded)
    assert res["rows"] == 25
    assert 0.0 <= res["category_accuracy"] <= 1.0
    assert 0.0 <= res["priority_accuracy"] <= 1.0
