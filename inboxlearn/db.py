from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sender TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'upload',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_number INTEGER NOT NULL UNIQUE,
    label TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES model_versions(id),
    kind TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    model_blob BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL REFERENCES emails(id),
    model_version_id INTEGER NOT NULL REFERENCES model_versions(id),
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    category_confidence REAL NOT NULL,
    priority_confidence REAL NOT NULL,
    status TEXT NOT NULL,
    is_original INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(email_id, is_original)
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL REFERENCES emails(id),
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    replaces_feedback_id INTEGER REFERENCES feedback(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS version_feedback (
    version_id INTEGER NOT NULL REFERENCES model_versions(id),
    email_id INTEGER NOT NULL REFERENCES emails(id),
    feedback_id INTEGER NOT NULL REFERENCES feedback(id),
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    PRIMARY KEY(version_id, email_id)
);
CREATE TABLE IF NOT EXISTS training_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL REFERENCES model_versions(id),
    source_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    feedback_id INTEGER REFERENCES feedback(id),
    label_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(version_id, source_type, source_key)
);
CREATE TABLE IF NOT EXISTS evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_version_id INTEGER NOT NULL REFERENCES model_versions(id),
    updated_version_id INTEGER NOT NULL REFERENCES model_versions(id),
    dataset_name TEXT NOT NULL,
    heldout_hash TEXT NOT NULL,
    results_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_registry (
    version_id INTEGER PRIMARY KEY REFERENCES model_versions(id),
    parent_id INTEGER NOT NULL REFERENCES model_versions(id),
    seed_hash TEXT NOT NULL,
    feedback_revision_ids TEXT NOT NULL,
    recipe_version TEXT NOT NULL,
    UNIQUE(parent_id, seed_hash, feedback_revision_ids, recipe_version)
);
CREATE INDEX IF NOT EXISTS idx_predictions_email ON predictions(email_id);
CREATE INDEX IF NOT EXISTS idx_feedback_email ON feedback(email_id, id DESC);
"""


class Repository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._training_lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Apply additive schema migrations. Safe to call repeatedly."""
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
        
        # Migration 1: V2 Schema Extensions
        row = conn.execute("SELECT version FROM schema_migrations WHERE version=1").fetchone()
        if not row:
            # emails table additions
            try:
                conn.execute("ALTER TABLE emails ADD COLUMN message_id TEXT DEFAULT ''")
                conn.execute("ALTER TABLE emails ADD COLUMN in_reply_to TEXT DEFAULT ''")
                conn.execute("ALTER TABLE emails ADD COLUMN thread_id TEXT DEFAULT ''")
                conn.execute("ALTER TABLE emails ADD COLUMN date_header TEXT DEFAULT ''")
                conn.execute("ALTER TABLE emails ADD COLUMN source_type TEXT NOT NULL DEFAULT 'csv'")
                conn.execute("ALTER TABLE emails ADD COLUMN import_batch TEXT NOT NULL DEFAULT ''")
                conn.execute("ALTER TABLE emails ADD COLUMN parser_warnings_json TEXT")
            except sqlite3.OperationalError:
                pass # columns might already exist

            conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_import_batch ON emails(import_batch)")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS extracted_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
                entity_type TEXT NOT NULL,
                entity_value TEXT NOT NULL,
                source_phrase TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_email ON extracted_entities(email_id)")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS action_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL REFERENCES emails(id),
                action_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'staged',
                executed_at TEXT,
                undo_payload_json TEXT,
                created_at TEXT NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_actions_email ON action_journal(email_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON action_journal(status)")
            
            conn.execute("INSERT INTO schema_migrations (version) VALUES (1)")

    @contextmanager
    def training_transaction(self) -> Iterator[sqlite3.Connection]:
        """Hold the SQLite write lock for the complete model build and version save."""
        with self._training_lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with closing(self._connect()) as conn:
            return conn.execute(sql, params).fetchone()

    def _all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with closing(self._connect()) as conn:
            return conn.execute(sql, params).fetchall()

    def active_version(self, conn: sqlite3.Connection | None = None) -> sqlite3.Row | None:
        sql = "SELECT * FROM model_versions WHERE is_active=1 ORDER BY id DESC LIMIT 1"
        return (conn or self._connect()).execute(sql).fetchone() if conn else self._one(sql)

    def version(self, version_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM model_versions WHERE id=?", (version_id,))

    def versions(self) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM model_versions ORDER BY version_number DESC")

    def insert_email_with_prediction(self, row: dict, content_hash: str, prediction: dict, source: str = "upload") -> int:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT id FROM emails WHERE content_hash=?", (content_hash,)).fetchone()
            if existing:
                conn.commit()
                return int(existing["id"])
            created = utc_now()
            cursor = conn.execute(
                "INSERT INTO emails(subject, body, sender, content_hash, source, created_at) VALUES (?,?,?,?,?,?)",
                (row["subject"], row["body"], row.get("sender", ""), content_hash, source, created),
            )
            email_id = int(cursor.lastrowid)
            conn.execute(
                """INSERT INTO predictions(email_id, model_version_id, category, priority,
                   category_confidence, priority_confidence, status, is_original, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (email_id, prediction["model_version_id"], prediction["category"], prediction["priority"],
                 prediction["category_confidence"], prediction["priority_confidence"], prediction["status"], 1, created),
            )
            conn.commit()
            return email_id

    def inbox_rows(self, *, review_only: bool = False, include_confident: bool = True) -> list[sqlite3.Row]:
        where = "WHERE p.status='needs_review'" if review_only else ""
        if not include_confident and not review_only:
            where = "WHERE p.status='needs_review'"
        return self._all(
            f"""SELECT e.*, p.model_version_id, p.category, p.priority,
                    p.category_confidence, p.priority_confidence, p.status,
                    p.created_at AS prediction_created_at
                FROM emails e JOIN predictions p ON p.email_id=e.id AND p.is_original=1
                {where} ORDER BY e.id DESC"""
        )

    def latest_feedback(self, conn: sqlite3.Connection | None = None) -> list[sqlite3.Row]:
        sql = """SELECT f.*, e.subject, e.body, e.sender FROM feedback f
                 JOIN emails e ON e.id=f.email_id
                 JOIN (SELECT email_id, MAX(id) AS id FROM feedback GROUP BY email_id) latest
                 ON latest.id=f.id ORDER BY f.email_id"""
        return conn.execute(sql).fetchall() if conn else self._all(sql)

    def feedback_for_email(self, email_id: int) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM feedback WHERE email_id=? ORDER BY id", (email_id,))

    def save_feedback(self, email_id: int, category: str, priority: str) -> tuple[int, bool]:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute(
                "SELECT * FROM feedback WHERE email_id=? ORDER BY id DESC LIMIT 1", (email_id,)
            ).fetchone()
            if previous and previous["category"] == category and previous["priority"] == priority:
                conn.commit()
                return int(previous["id"]), False
            cursor = conn.execute(
                "INSERT INTO feedback(email_id, category, priority, replaces_feedback_id, created_at) VALUES (?,?,?,?,?)",
                (email_id, category, priority, previous["id"] if previous else None, utc_now()),
            )
            conn.execute("UPDATE predictions SET status='corrected' WHERE email_id=? AND is_original=1", (email_id,))
            conn.commit()
            return int(cursor.lastrowid), True

    def pending_feedback_count(self) -> int:
        active = self.active_version()
        if not active:
            return len(self.latest_feedback())
        row = self._one(
            """SELECT COUNT(*) AS n FROM feedback f
               JOIN (SELECT email_id, MAX(id) AS id FROM feedback GROUP BY email_id) latest ON latest.id=f.id
               LEFT JOIN version_feedback vf ON vf.version_id=? AND vf.email_id=f.email_id AND vf.feedback_id=f.id
               WHERE vf.email_id IS NULL""",
            (active["id"],),
        )
        return int(row["n"])

    def feedback_membership(self, version_id: int, conn: sqlite3.Connection | None = None) -> dict[int, sqlite3.Row]:
        rows = (conn.execute("SELECT * FROM version_feedback WHERE version_id=?", (version_id,)).fetchall()
                if conn else self._all("SELECT * FROM version_feedback WHERE version_id=?", (version_id,)))
        return {int(row["email_id"]): row for row in rows}

    def create_version_conn(
        self,
        conn: sqlite3.Connection,
        *,
        blob: bytes,
        parent_id: int | None,
        kind: str,
        metadata: dict,
        feedback_rows: list[sqlite3.Row],
        seed_count: int,
        activate: bool = True,
    ) -> int:
        number_row = conn.execute("SELECT COALESCE(MAX(version_number),0)+1 AS n FROM model_versions").fetchone()
        number = int(number_row["n"])
        created = utc_now()
        label = f"v{number}"
        if activate:
            conn.execute("UPDATE model_versions SET is_active=0")
        cursor = conn.execute(
            """INSERT INTO model_versions(version_number,label,parent_id,kind,is_active,created_at,metadata_json,model_blob)
               VALUES (?,?,?,?,?,?,?,?)""",
            (number, label, parent_id, kind, int(activate), created, json.dumps(metadata, sort_keys=True), blob),
        )
        version_id = int(cursor.lastrowid)
        for index in range(seed_count):
            conn.execute(
                "INSERT INTO training_lineage(version_id,source_type,source_key,feedback_id,label_hash,created_at) VALUES (?,?,?,?,?,?)",
                (version_id, "seed", f"seed:{index}", None, "demonstration-seed", created),
            )
        for row in feedback_rows:
            conn.execute(
                "INSERT INTO version_feedback(version_id,email_id,feedback_id,category,priority) VALUES (?,?,?,?,?)",
                (version_id, row["email_id"], row["id"], row["category"], row["priority"]),
            )
            conn.execute(
                "INSERT INTO training_lineage(version_id,source_type,source_key,feedback_id,label_hash,created_at) VALUES (?,?,?,?,?,?)",
                (version_id, "feedback", f"email:{row['email_id']}", row["id"], f"{row['category']}|{row['priority']}", created),
            )
        return version_id

    def candidates(self) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM candidate_registry ORDER BY version_id DESC")

    def evaluation_for_version(self, version_id: int, heldout_hash: str):
        return self._one(
            """SELECT * FROM evaluation_results WHERE updated_version_id=?
               AND dataset_name='demo_eval.csv' AND heldout_hash=? ORDER BY id DESC LIMIT 1""",
            (version_id, heldout_hash),
        )

    def save_evaluation(self, baseline_id: int, updated_id: int, dataset_name: str, heldout_hash: str, results: dict) -> int:
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """INSERT INTO evaluation_results(baseline_version_id,updated_version_id,dataset_name,heldout_hash,results_json,created_at)
                   VALUES (?,?,?,?,?,?)""",
                (baseline_id, updated_id, dataset_name, heldout_hash, json.dumps(results, sort_keys=True), utc_now()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def evaluations(self) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM evaluation_results ORDER BY id DESC")

    def export_rows(self) -> list[sqlite3.Row]:
        return self._all(
            """SELECT e.id, e.subject, e.body, e.sender, e.source, e.created_at,
                      p.category AS predicted_category, p.priority AS predicted_priority,
                      p.category_confidence, p.priority_confidence, p.model_version_id,
                      p.status,
                      f.category AS corrected_category, f.priority AS corrected_priority
               FROM emails e JOIN predictions p ON p.email_id=e.id AND p.is_original=1
               LEFT JOIN feedback f ON f.id=(SELECT MAX(id) FROM feedback WHERE email_id=e.id)
               ORDER BY e.id"""
        )

    def insert_email_extended(self, row: dict, content_hash: str, prediction: dict, *, source: str = 'upload', source_type: str = 'csv', import_batch: str = '', message_id: str = '', in_reply_to: str = '', thread_id: str = '', date_header: str = '', parser_warnings: list[str] | None = None) -> int:
        """Insert email with extended metadata. Deduplicates by content_hash."""
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT id FROM emails WHERE content_hash=?", (content_hash,)).fetchone()
            if existing:
                conn.commit()
                return int(existing["id"])
            created = utc_now()
            warnings_json = json.dumps(parser_warnings) if parser_warnings else None
            
            cursor = conn.execute(
                """INSERT INTO emails(
                    subject, body, sender, content_hash, source, created_at,
                    message_id, in_reply_to, thread_id, date_header, source_type, import_batch, parser_warnings_json
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (row["subject"], row["body"], row.get("sender", ""), content_hash, source, created,
                 message_id, in_reply_to, thread_id, date_header, source_type, import_batch, warnings_json)
            )
            email_id = int(cursor.lastrowid)
            conn.execute(
                """INSERT INTO predictions(email_id, model_version_id, category, priority,
                   category_confidence, priority_confidence, status, is_original, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (email_id, prediction["model_version_id"], prediction["category"], prediction["priority"],
                 prediction["category_confidence"], prediction["priority_confidence"], prediction["status"], 1, created),
            )
            conn.commit()
            return email_id

    def import_batches(self) -> list[dict]:
        """List distinct import batches with counts."""
        rows = self._all("SELECT import_batch, COUNT(*) as count FROM emails GROUP BY import_batch ORDER BY import_batch DESC")
        return [{"import_batch": r["import_batch"], "count": r["count"]} for r in rows if r["import_batch"]]

    def inbox_rows_filtered(self, *, import_batch: str = '', **kwargs) -> list[sqlite3.Row]:
        """Inbox rows with optional import batch filter."""
        review_only = kwargs.get("review_only", False)
        include_confident = kwargs.get("include_confident", True)
        
        where_clauses = []
        if review_only or not include_confident:
            where_clauses.append("p.status='needs_review'")
        if import_batch:
            where_clauses.append("e.import_batch=?")
            
        where = ""
        if where_clauses:
            where = "WHERE " + " AND ".join(where_clauses)
            
        params = (import_batch,) if import_batch else ()
        
        return self._all(
            f"""SELECT e.*, p.model_version_id, p.category, p.priority,
                    p.category_confidence, p.priority_confidence, p.status,
                    p.created_at AS prediction_created_at
                FROM emails e JOIN predictions p ON p.email_id=e.id AND p.is_original=1
                {where} ORDER BY e.id DESC""",
            params
        )

    def save_entity(self, email_id: int, entity_type: str, entity_value: str, source_phrase: str = '', confidence: float = 1.0) -> int:
        """Save an extracted entity for an email."""
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """INSERT INTO extracted_entities(email_id, entity_type, entity_value, source_phrase, confidence, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (email_id, entity_type, entity_value, source_phrase, confidence, utc_now())
            )
            conn.commit()
            return int(cursor.lastrowid)

    def entities_for_email(self, email_id: int) -> list[sqlite3.Row]:
        """Get all extracted entities for an email."""
        return self._all("SELECT * FROM extracted_entities WHERE email_id=? ORDER BY id", (email_id,))

    def save_action(self, email_id: int, action_type: str, payload: dict) -> int:
        """Stage an action in the journal."""
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """INSERT INTO action_journal(email_id, action_type, payload_json, status, created_at)
                   VALUES (?,?,?,?,?)""",
                (email_id, action_type, json.dumps(payload), 'staged', utc_now())
            )
            conn.commit()
            return int(cursor.lastrowid)

    def execute_action(self, action_id: int) -> None:
        """Mark an action as executed with timestamp."""
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE action_journal SET status='executed', executed_at=? WHERE id=?",
                (utc_now(), action_id)
            )
            conn.commit()

    def revert_action(self, action_id: int) -> None:
        """Mark an action as reverted."""
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE action_journal SET status='reverted' WHERE id=?",
                (action_id,)
            )
            conn.commit()

    def actions_for_email(self, email_id: int) -> list[sqlite3.Row]:
        """Get action journal entries for an email."""
        return self._all("SELECT * FROM action_journal WHERE email_id=? ORDER BY id", (email_id,))
