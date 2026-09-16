from dataclasses import dataclass
import os
from pathlib import Path

CATEGORIES = (
    "job opportunities",
    "university",
    "bills",
    "promotions",
    "spam",
)
PRIORITIES = ("low", "normal", "high")


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("runtime/inboxlearn.sqlite3")
    max_upload_bytes: int = 5 * 1024 * 1024
    max_rows: int = 1_000
    category_threshold: float = 0.70
    priority_threshold: float = 0.70
    random_state: int = 42

    @classmethod
    def from_environment(cls) -> "Settings":
        def number(name: str, fallback: float) -> float:
            try:
                return float(os.getenv(name, fallback))
            except (TypeError, ValueError):
                return fallback

        def integer(name: str, fallback: int) -> int:
            try:
                return int(os.getenv(name, fallback))
            except (TypeError, ValueError):
                return fallback

        return cls(
            db_path=Path(os.getenv("INBOXLEARN_DB", str(cls.db_path))),
            max_upload_bytes=integer("INBOXLEARN_MAX_UPLOAD_BYTES", cls.max_upload_bytes),
            max_rows=integer("INBOXLEARN_MAX_ROWS", cls.max_rows),
            category_threshold=number("INBOXLEARN_CATEGORY_THRESHOLD", cls.category_threshold),
            priority_threshold=number("INBOXLEARN_PRIORITY_THRESHOLD", cls.priority_threshold),
            random_state=integer("INBOXLEARN_RANDOM_STATE", cls.random_state),
        )
