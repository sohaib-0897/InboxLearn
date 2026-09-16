from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EmailInput:
    subject: str
    body: str
    sender: str = ""


@dataclass(frozen=True)
class Prediction:
    category: str
    priority: str
    category_confidence: float
    priority_confidence: float
    model_version_id: int
    status: str


@dataclass(frozen=True)
class FeedbackResult:
    correction_id: int
    created: bool


@dataclass(frozen=True)
class VersionInfo:
    id: int
    version_number: int
    label: str
    parent_id: Optional[int]
    kind: str
    is_active: bool
    created_at: str
    metadata: dict
