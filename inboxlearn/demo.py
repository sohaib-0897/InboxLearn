from pathlib import Path

from .validation import parse_csv_bytes


def demo_data_path(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / name


def load_demo_rows(name: str, *, require_labels: bool = True) -> list[dict]:
    path = demo_data_path(name)
    return parse_csv_bytes(path.read_bytes(), max_bytes=2_000_000, max_rows=500, require_labels=require_labels)
