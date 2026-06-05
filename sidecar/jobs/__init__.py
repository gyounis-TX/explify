"""Async extraction jobs (scaffolding).

Decouples the heavy OCR/extraction pipeline from the request path: the API enqueues a
job, a scale-to-zero worker processes it, and the client polls for the result. See
docs/async-extraction/DESIGN.md.

Everything here is additive and inert unless ``ASYNC_EXTRACTION`` is enabled and the
SQS queue / worker are deployed (infra/async-extraction/).
"""

from .models import JobKind, JobStatus, ExtractionJob

__all__ = ["JobKind", "JobStatus", "ExtractionJob"]
