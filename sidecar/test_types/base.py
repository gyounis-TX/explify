from __future__ import annotations

import re
from abc import ABC, abstractmethod

from api.models import ExtractionResult
from api.analysis_models import ParsedReport

# ---------------------------------------------------------------------------
# Text-zone utilities for positional keyword weighting
# ---------------------------------------------------------------------------
# Reports follow a rough structure: title/header at the top, an optional
# comparison section referencing prior studies (which may be a *different*
# modality), and the main body.  Keywords found in the title carry more
# weight because they describe *this* report.  Keywords found only in the
# comparison section should be heavily discounted.

_COMPARISON_RE = re.compile(
    r"(?:^|\n)\s*(?:comparison|compared?\s+(?:to|with)|prior\s+(?:study|exam|studies))"
    r"\s*[:\-]?\s*(.*?)(?=\n\s*\n|\n\s*[A-Z]{2,}|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def split_text_zones(full_text: str) -> tuple[str, str, str]:
    """Split report text into (title, comparison, body) zones (all lower-case).

    - **title**: first 500 characters — covers header, procedure name, exam type.
    - **comparison**: text matched by comparison-section patterns.
    - **body**: everything else (full text minus comparison spans).
    """
    lower = full_text.lower()
    title = lower[:500]

    comparison_parts: list[str] = []
    body_chars = list(lower)
    for m in _COMPARISON_RE.finditer(lower):
        comparison_parts.append(m.group(0))
        # Blank out comparison span so body excludes it
        for i in range(m.start(), m.end()):
            if i < len(body_chars):
                body_chars[i] = " "

    comparison = " ".join(comparison_parts)
    body = "".join(body_chars)
    return title, comparison, body


_kw_re_cache: dict[str, re.Pattern] = {}


def _kw_match(kw: str, text: str) -> bool:
    """Check if *kw* appears as a whole word in *text* using word boundaries."""
    pat = _kw_re_cache.get(kw)
    if pat is None:
        pat = re.compile(r"\b" + re.escape(kw) + r"\b")
        _kw_re_cache[kw] = pat
    return bool(pat.search(text))


def keyword_zone_weight(keyword: str, title: str, comparison: str, body: str) -> float:
    """Return a positional weight for *keyword* based on where it appears.

    - In title → 2.0  (this keyword describes the report itself)
    - In body only → 1.0
    - In comparison only → 0.1  (likely referencing a *different* modality)
    - Not found → 0.0
    """
    kw = keyword.lower()
    in_title = _kw_match(kw, title)
    in_body = _kw_match(kw, body)
    in_comp = _kw_match(kw, comparison)
    if in_title:
        return 2.0
    if in_body and not in_comp:
        return 1.0
    if in_body:
        return 1.0
    if in_comp:
        return 0.1
    return 0.0


class BaseTestType(ABC):
    """Abstract base class for medical test type handlers."""

    @property
    @abstractmethod
    def test_type_id(self) -> str:
        """Unique identifier, e.g., 'echocardiogram'."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g., 'Echocardiogram'."""
        ...

    @property
    @abstractmethod
    def keywords(self) -> list[str]:
        """Keywords for auto-detection from extracted text."""
        ...

    @abstractmethod
    def detect(self, extraction_result: ExtractionResult) -> float:
        """Return confidence score 0.0-1.0 that this is the right test type."""
        ...

    @abstractmethod
    def parse(
        self,
        extraction_result: ExtractionResult,
        gender: str | None = None,
        age: int | None = None,
    ) -> ParsedReport:
        """Parse extraction result into structured report.

        Args:
            extraction_result: The extracted text/data from the report
            gender: Patient gender for sex-specific reference ranges (optional)
            age: Patient age for age-specific reference ranges (optional)
        """
        ...

    @abstractmethod
    def get_reference_ranges(self) -> dict:
        """Return reference ranges for this test type."""
        ...

    @abstractmethod
    def get_glossary(self) -> dict[str, str]:
        """Map medical terms to plain English definitions."""
        ...

    @property
    def category(self) -> str:
        """Category for grouping in UI (e.g., 'cardiac', 'imaging_ct').
        Override in subclass; defaults to 'other'."""
        return "other"

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        """Additional context for LLM prompt construction (Phase 4).
        Default returns empty dict; override in subclass."""
        return {}

    def resolve_subtype(self, extraction_result: ExtractionResult) -> tuple[str, str] | None:
        """Resolve to a more specific subtype based on report content.

        Returns (subtype_id, subtype_display_name) or None if this handler
        does not support subtype resolution.
        Override in subclass for family-style handlers.
        """
        return None

    def get_vision_hints(self) -> str | None:
        """Return additional vision OCR hints specific to this test type.

        When a handler returns a non-None string, it signals that re-OCR
        with these hints could improve extraction quality for scanned/image
        documents. Return None (default) to skip re-OCR.
        """
        return None

    def get_metadata(self) -> dict:
        """Return metadata for listing in registry."""
        return {
            "test_type_id": self.test_type_id,
            "display_name": self.display_name,
            "keywords": self.keywords,
            "category": self.category,
        }
