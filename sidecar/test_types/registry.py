from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional

from api.models import ExtractionResult
from .base import BaseTestType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Correction-based score adjustment cache
# ---------------------------------------------------------------------------
# Loaded from detection_corrections table; refreshed every 10 minutes.
# Structure: {detected_type: {corrected_type: count}}
_correction_cache: dict[str, dict[str, int]] = {}
_cache_ts: float = 0.0
_CACHE_TTL: float = 600.0  # 10 minutes


async def refresh_correction_cache() -> None:
    """Load aggregate correction stats from DB. Called at startup + periodically."""
    global _correction_cache, _cache_ts

    stats: list[dict] = []
    if os.getenv("DATABASE_URL", ""):
        try:
            from storage.pg_database import get_correction_stats
            stats = await get_correction_stats()
        except Exception:
            logger.exception("Failed to load PG correction stats")
    else:
        try:
            from storage.database import get_db
            db = get_db()
            conn = db._get_conn()
            try:
                rows = conn.execute(
                    """SELECT detected_type, corrected_type, COUNT(*) as cnt
                       FROM detection_corrections
                       WHERE created_at > datetime('now', '-6 months')
                       GROUP BY detected_type, corrected_type
                       HAVING COUNT(*) >= 2"""
                ).fetchall()
                stats = [dict(r) for r in rows]
            finally:
                conn.close()
        except Exception:
            logger.debug("No detection_corrections table in SQLite (expected on fresh install)")

    cache: dict[str, dict[str, int]] = {}
    for row in stats:
        detected = row["detected_type"]
        corrected = row["corrected_type"]
        cnt = row["cnt"]
        cache.setdefault(detected, {})[corrected] = cnt
    _correction_cache = cache
    _cache_ts = time.monotonic()
    if cache:
        logger.info("Correction cache loaded: %d correction patterns", sum(len(v) for v in cache.values()))


def _apply_correction_adjustments(
    scores: list[tuple[str, float, "BaseTestType"]],
) -> list[tuple[str, float, "BaseTestType"]]:
    """Adjust scores based on historical corrections.

    For each scored type that has been frequently corrected FROM, apply a
    penalty of -0.03 per correction (capped at -0.10).
    For types it was corrected TO, apply a boost of +0.03 (capped at +0.10).
    """
    if not _correction_cache:
        return scores

    # Collect all corrected-TO types across the cache for boost lookup
    boost_for: dict[str, int] = {}  # {type_id: total_count}
    for detected, corrections in _correction_cache.items():
        for corrected, cnt in corrections.items():
            boost_for[corrected] = boost_for.get(corrected, 0) + cnt

    adjusted: list[tuple[str, float, "BaseTestType"]] = []
    for type_id, confidence, handler in scores:
        adj = 0.0

        # Penalty: this type was frequently corrected FROM
        if type_id in _correction_cache:
            total_corrections = sum(_correction_cache[type_id].values())
            adj -= min(total_corrections * 0.03, 0.10)

        # Boost: this type was frequently corrected TO
        if type_id in boost_for:
            adj += min(boost_for[type_id] * 0.03, 0.10)

        new_confidence = max(0.0, min(1.0, confidence + adj))
        adjusted.append((type_id, new_confidence, handler))

    return adjusted

_HEADER_PATTERNS = [
    # Labeled formats: "Report: ...", "Exam Type: ...", "Study: ...", "Procedure: ..."
    re.compile(r"(?i)(?:report|exam(?:ination)?|test|study|procedure|modality)\s*(?:type)?[:\-]\s*(.+)", re.MULTILINE),
    re.compile(r"(?i)^(?:IMPRESSION|INDICATION|FINDINGS)\s+(?:FOR|OF)\s+(.+)", re.MULTILINE),
    # Standalone modality on first line (e.g. "MRI BRAIN WITHOUT CONTRAST")
    re.compile(
        r"(?i)^\s*((?:MRI|MR|CT|CTA|MRA|X-?RAY|ULTRASOUND|US|ECHO|PET|SPECT|DEXA|EKG|ECG|EEG|EMG)"
        r"\s+.{3,60})\s*$",
        re.MULTILINE,
    ),
]


class TestTypeRegistry:
    """Registry for medical test type handlers."""

    def __init__(self):
        self._handlers: dict[str, BaseTestType] = {}
        # Maps subtype IDs to their parent family handler
        self._subtype_parents: dict[str, BaseTestType] = {}
        # Handler IDs that are family parents (hidden from list_types)
        self._hidden_ids: set[str] = set()

    def register(self, handler: BaseTestType) -> None:
        type_id = handler.test_type_id
        if type_id in self._handlers:
            logger.warning(f"Overwriting existing handler for '{type_id}'")
        self._handlers[type_id] = handler
        logger.info(f"Registered test type handler: {type_id}")

    def register_subtype(self, subtype_id: str, parent_handler: BaseTestType) -> None:
        """Map a subtype ID to its parent family handler."""
        self._subtype_parents[subtype_id] = parent_handler
        # Hide the parent from type listings (replaced by subtypes)
        self._hidden_ids.add(parent_handler.test_type_id)

    def detect_from_header(self, extraction_result: ExtractionResult) -> tuple[Optional[str], float]:
        """Pre-pass: scan first 500 chars for explicit report type labels."""
        header_text = extraction_result.full_text[:500]
        for pattern in _HEADER_PATTERNS:
            m = pattern.search(header_text)
            if m:
                label = m.group(1).strip().rstrip(".")
                resolved_id, handler = self.resolve(label)
                if resolved_id is not None:
                    return (resolved_id, 0.85)
        return (None, 0.0)

    async def _maybe_refresh_corrections(self) -> None:
        """Refresh correction cache if stale (> TTL seconds old)."""
        if time.monotonic() - _cache_ts > _CACHE_TTL:
            await refresh_correction_cache()

    def detect(
        self, extraction_result: ExtractionResult
    ) -> tuple[Optional[str], float]:
        """Auto-detect test type. Returns (type_id, confidence) or (None, 0.0)."""
        # Pre-pass: explicit header labels
        header_id, header_conf = self.detect_from_header(extraction_result)
        if header_id is not None:
            return (header_id, header_conf)

        scores: list[tuple[str, float, BaseTestType]] = []
        for type_id, handler in self._handlers.items():
            try:
                confidence = handler.detect(extraction_result)
                if confidence > 0.0:
                    scores.append((type_id, confidence, handler))
            except Exception as e:
                logger.error(f"Detection failed for '{type_id}': {e}")

        if not scores:
            return (None, 0.0)

        # Apply correction-based adjustments (learned from user overrides)
        scores = _apply_correction_adjustments(scores)

        scores.sort(key=lambda x: x[1], reverse=True)
        best_id, best_confidence, best_handler = scores[0]

        # Disambiguation: prefer specialized over generic when close
        if len(scores) >= 2:
            _, second_conf, second_handler = scores[1]
            if best_confidence - second_conf <= 0.15:
                from test_types.generic import GenericTestType
                if isinstance(best_handler, GenericTestType) and not isinstance(second_handler, GenericTestType):
                    best_id, best_confidence, best_handler = scores[1]

        # Allow family-style handlers to resolve to a specific subtype
        subtype = best_handler.resolve_subtype(extraction_result)
        if subtype is not None:
            best_id = subtype[0]

        return (best_id, best_confidence)

    def detect_multi(
        self, extraction_result: ExtractionResult, threshold: float = 0.3,
    ) -> list[tuple[str, float]]:
        """Detect all test types above *threshold*.

        Returns list of (type_id, confidence) sorted descending by confidence.
        The first entry is the primary type.
        """
        results: list[tuple[str, float]] = []

        # Pre-pass: explicit header labels
        header_id, header_conf = self.detect_from_header(extraction_result)
        if header_id is not None:
            results.append((header_id, header_conf))

        for type_id, handler in self._handlers.items():
            try:
                confidence = handler.detect(extraction_result)
                if confidence >= threshold:
                    # Resolve subtypes
                    resolved_id = type_id
                    subtype = handler.resolve_subtype(extraction_result)
                    if subtype is not None:
                        resolved_id = subtype[0]
                    results.append((resolved_id, confidence))
            except Exception as e:
                logger.error(f"Multi-detection failed for '{type_id}': {e}")

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get(self, type_id: str) -> Optional[BaseTestType]:
        # Prefer specialized family handler for subtype IDs
        parent = self._subtype_parents.get(type_id)
        if parent is not None:
            return parent
        return self._handlers.get(type_id)

    def resolve(self, type_id_or_name: str) -> tuple[Optional[str], Optional[BaseTestType]]:
        """Resolve a type ID or free-text name to a handler.

        1. Exact ID match (existing behavior)
        2. Subtype parent match (family handlers)
        3. Keyword match against registered handlers
        Returns (resolved_id, handler) or (None, None).
        """
        # Subtype parent match — prefer the specialized family handler
        parent = self._subtype_parents.get(type_id_or_name)
        if parent is not None:
            return (type_id_or_name, parent)

        # Exact match
        handler = self._handlers.get(type_id_or_name)
        if handler is not None:
            return (type_id_or_name, handler)

        # Keyword match: check if the user string matches any handler's keywords
        query = type_id_or_name.lower()
        best_handler = None
        best_id: Optional[str] = None
        best_score = 0
        for tid, h in self._handlers.items():
            for kw in h.keywords:
                if kw.lower() in query or query in kw.lower():
                    score = len(kw)  # longer keyword match = more specific
                    if score > best_score:
                        best_score = score
                        best_handler = h
                        best_id = tid

        return (best_id, best_handler) if best_handler else (None, None)

    def list_types(self) -> list[dict]:
        return [
            handler.get_metadata()
            for tid, handler in self._handlers.items()
            if tid not in self._hidden_ids
        ]
