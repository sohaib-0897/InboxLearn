import json
import sqlite3
import pytest
from inboxlearn.db import Repository

def test_fresh_database_gets_v2_schema(tmp_path):
    repo = Repository(tmp_path / "test.db")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.row_factory = sqlite3.Row
        # Check emails table has message_id
        cursor = conn.execute("PRAGMA table_info(emails)")
        columns = [row["name"] for row in cursor.fetchall()]
        assert "message_id" in columns
        assert "thread_id" in columns
        assert "import_batch" in columns

        # Check extracted_entities table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_entities'")
        assert cursor.fetchone() is not None

def test_existing_v1_database_migrates_cleanly(tmp_path):
    db_path = tmp_path / "test.db"
    
    # Create V1 database manually
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sender TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL DEFAULT 'upload',
            created_at TEXT NOT NULL
        );
        """)
    
    # Init Repository which should trigger migration
    repo = Repository(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("PRAGMA table_info(emails)")
        columns = [row["name"] for row in cursor.fetchall()]
        assert "message_id" in columns
        assert "import_batch" in columns

def test_migration_is_idempotent(tmp_path):
    repo = Repository(tmp_path / "test.db")
    
    # Should not raise any errors when migrating again
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        repo._migrate(conn)
        repo._migrate(conn)

def test_insert_email_extended(tmp_path):
    repo = Repository(tmp_path / "test.db")
    
    # Create dummy model version to satisfy foreign key constraint
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.execute("INSERT INTO model_versions(version_number,label,kind,metadata_json,model_blob,created_at) VALUES(1,'v1','sgd','{}',x'00','2023-01-01')")
    
    row = {"subject": "Test", "body": "Body", "sender": "test@test.com"}
    prediction = {"model_version_id": 1, "category": "Updates", "priority": "Low", "category_confidence": 0.9, "priority_confidence": 0.8, "status": "needs_review"}
    
    email_id = repo.insert_email_extended(
        row, "hash1", prediction,
        import_batch="batch_1", message_id="<msg1>", thread_id="thread1"
    )
    
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.row_factory = sqlite3.Row
        email_row = conn.execute("SELECT * FROM emails WHERE id=?", (email_id,)).fetchone()
        assert email_row["message_id"] == "<msg1>"
        assert email_row["import_batch"] == "batch_1"

def test_import_batches(tmp_path):
    repo = Repository(tmp_path / "test.db")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.execute("INSERT INTO model_versions(version_number,label,kind,metadata_json,model_blob,created_at) VALUES(1,'v1','sgd','{}',x'00','2023-01-01')")
    
    row = {"subject": "Test", "body": "Body"}
    pred = {"model_version_id": 1, "category": "Updates", "priority": "Low", "category_confidence": 0.9, "priority_confidence": 0.8, "status": "needs_review"}
    repo.insert_email_extended(row, "h1", pred, import_batch="b1")
    repo.insert_email_extended(row, "h2", pred, import_batch="b1")
    repo.insert_email_extended(row, "h3", pred, import_batch="b2")
    
    batches = repo.import_batches()
    assert len(batches) == 2
    # Ensure ordered and counts correct
    batch_map = {b["import_batch"]: b["count"] for b in batches}
    assert batch_map["b1"] == 2
    assert batch_map["b2"] == 1

def test_save_entity_and_entities_for_email(tmp_path):
    repo = Repository(tmp_path / "test.db")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.execute("INSERT INTO emails(subject, body, sender, content_hash, created_at) VALUES('s','b','s','h','2023')")
        email_id = 1
        
    repo.save_entity(email_id, "PER", "John Doe", "Dr. John Doe", 0.99)
    entities = repo.entities_for_email(email_id)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "PER"
    assert entities[0]["entity_value"] == "John Doe"

def test_action_journal(tmp_path):
    repo = Repository(tmp_path / "test.db")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.execute("INSERT INTO emails(subject, body, sender, content_hash, created_at) VALUES('s','b','s','h','2023')")
        email_id = 1
        
    action_id = repo.save_action(email_id, "archive", {"folder": "archived"})
    
    actions = repo.actions_for_email(email_id)
    assert len(actions) == 1
    assert actions[0]["status"] == "staged"
    
    repo.execute_action(action_id)
    actions = repo.actions_for_email(email_id)
    assert actions[0]["status"] == "executed"
    assert actions[0]["executed_at"] is not None
    
    repo.revert_action(action_id)
    actions = repo.actions_for_email(email_id)
    assert actions[0]["status"] == "reverted"

def test_existing_insert_works(tmp_path):
    repo = Repository(tmp_path / "test.db")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.execute("INSERT INTO model_versions(version_number,label,kind,metadata_json,model_blob,created_at) VALUES(1,'v1','sgd','{}',x'00','2023-01-01')")
    
    row = {"subject": "S", "body": "B"}
    prediction = {"model_version_id": 1, "category": "C", "priority": "P", "category_confidence": 0.5, "priority_confidence": 0.5, "status": "needs_review"}
    eid = repo.insert_email_with_prediction(row, "hashx", prediction)
    assert eid > 0

def test_existing_inbox_rows_works(tmp_path):
    repo = Repository(tmp_path / "test.db")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.execute("INSERT INTO model_versions(version_number,label,kind,metadata_json,model_blob,created_at) VALUES(1,'v1','sgd','{}',x'00','2023-01-01')")
    
    row = {"subject": "S", "body": "B"}
    prediction = {"model_version_id": 1, "category": "C", "priority": "P", "category_confidence": 0.5, "priority_confidence": 0.5, "status": "needs_review"}
    repo.insert_email_with_prediction(row, "hashy", prediction)
    
    rows = repo.inbox_rows()
    assert len(rows) == 1
    assert rows[0]["subject"] == "S"

def test_inbox_rows_filtered(tmp_path):
    repo = Repository(tmp_path / "test.db")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        conn.execute("INSERT INTO model_versions(version_number,label,kind,metadata_json,model_blob,created_at) VALUES(1,'v1','sgd','{}',x'00','2023-01-01')")
    
    row = {"subject": "Test", "body": "Body"}
    pred = {"model_version_id": 1, "category": "Updates", "priority": "Low", "category_confidence": 0.9, "priority_confidence": 0.8, "status": "needs_review"}
    repo.insert_email_extended(row, "h1", pred, import_batch="b1")
    repo.insert_email_extended(row, "h2", pred, import_batch="b2")
    
    rows = repo.inbox_rows_filtered(import_batch="b1")
    assert len(rows) == 1
    assert rows[0]["import_batch"] == "b1"
