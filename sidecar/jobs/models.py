"""Job data model for the async extraction pipeline (scaffolding)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


def async_extraction_enabled() -> bool:
    """Feature flag. When false (default), none of the async path is active."""
    return os.getenv("ASYNC_EXTRACTION", "").lower() in ("1", "true", "yes")


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class JobKind(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"


@dataclass
class ExtractionJob:
    job_id: str
    user_id: Optional[str]
    practice_id: Optional[str]
    kind: JobKind
    status: JobStatus
    input_s3_key: Optional[str] = None
    result_s3_key: Optional[str] = None
    attempts: int = 0
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in (JobStatus.DONE, JobStatus.FAILED)
