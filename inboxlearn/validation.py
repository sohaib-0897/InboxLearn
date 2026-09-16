import csv
import hashlib
import io
import json
import re
import unicodedata
from typing import Iterable

from .config import CATEGORIES, PRIORITIES


class CSVValidationError(ValueError):
    """Raised when an uploaded CSV is unsafe or cannot be used."""


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", value).strip().casefold()


def content_key(row: dict) -> str:
    return json.dumps(
        [normalize_text(row.get("subject", "")), normalize_text(row.get("body", "")), normalize_text(row.get("sender", ""))],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def content_hash(row: dict) -> str:
    return hashlib.sha256(content_key(row).encode("utf-8")).hexdigest()


def split_key(row: dict) -> tuple[str, str]:
    """Match normalized email content even if sender metadata is changed/omitted."""
    subject, body = normalize_text(row.get("subject", "")), normalize_text(row.get("body", ""))
    if not subject or not body:
        raise ValueError("Training and split checks require non-empty subject and body.")
    return subject, body


def _clean_headers(fieldnames: Iterable[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise CSVValidationError("CSV must include a header row.")
    cleaned: dict[str, str] = {}
    for original in fieldnames:
        name = (original or "").strip().casefold()
        if name and name not in cleaned:
            cleaned[name] = original
    return cleaned


def parse_csv_bytes(
    payload: bytes,
    *,
    max_bytes: int = 5 * 1024 * 1024,
    max_rows: int = 1_000,
    require_labels: bool = False,
) -> list[dict]:
    if not isinstance(payload, (bytes, bytearray)):
        raise CSVValidationError("CSV content must be bytes.")
    if len(payload) == 0:
        raise CSVValidationError("CSV file is empty.")
    if len(payload) > max_bytes:
        raise CSVValidationError(f"CSV exceeds the {max_bytes:,}-byte file-size limit.")
    try:
        text = bytes(payload).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVValidationError("CSV must be UTF-8 encoded.") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        headers = _clean_headers(reader.fieldnames)
        needed = {"subject", "body"}
        if require_labels:
            needed |= {"category", "priority"}
        missing = sorted(needed - set(headers))
        if missing:
            raise CSVValidationError("Missing required field(s): " + ", ".join(missing) + ".")

        rows: list[dict] = []
        seen: set[str] = set()
        for row_number, raw in enumerate(reader, start=2):
            if row_number - 1 > max_rows:
                raise CSVValidationError(f"CSV exceeds the {max_rows:,}-row limit.")
            if None in raw:
                raise CSVValidationError(f"Row {row_number} has more fields than the header.")
            normalized = {
                "subject": (raw.get(headers["subject"]) or "").strip(),
                "body": (raw.get(headers["body"]) or "").strip(),
                "sender": (raw.get(headers["sender"]) or "").strip() if "sender" in headers else "",
            }
            if not normalized["subject"] or not normalized["body"]:
                raise CSVValidationError(f"Row {row_number} must have non-empty subject and body.")
            key = content_key(normalized)
            if key in seen:
                raise CSVValidationError(f"Duplicate email content found at row {row_number}.")
            seen.add(key)
            if require_labels:
                category = (raw.get(headers["category"]) or "").strip().casefold()
                priority = (raw.get(headers["priority"]) or "").strip().casefold()
                if category not in CATEGORIES:
                    raise CSVValidationError(f"Row {row_number} has invalid category: {category!r}.")
                if priority not in PRIORITIES:
                    raise CSVValidationError(f"Row {row_number} has invalid priority: {priority!r}.")
                normalized.update(category=category, priority=priority)
            rows.append(normalized)
        if not rows:
            raise CSVValidationError("CSV has no data rows.")
        return rows
    except csv.Error as exc:
        raise CSVValidationError(f"CSV parsing failed: {exc}") from exc
