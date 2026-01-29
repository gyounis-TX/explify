from __future__ import annotations

from abc import ABC, abstractmethod

from api.models import ExtractionResult
from api.analysis_models import ParsedReport


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
    def parse(self, extraction_result: ExtractionResult) -> ParsedReport:
        """Parse extraction result into structured report."""
        ...

    @abstractmethod
    def get_reference_ranges(self) -> dict:
        """Return reference ranges for this test type."""
        ...

    @abstractmethod
    def get_glossary(self) -> dict[str, str]:
        """Map medical terms to plain English definitions."""
        ...

    def get_prompt_context(self) -> dict:
        """Additional context for LLM prompt construction (Phase 4).
        Default returns empty dict; override in subclass."""
        return {}

    def get_metadata(self) -> dict:
        """Return metadata for listing in registry."""
        return {
            "test_type_id": self.test_type_id,
            "display_name": self.display_name,
            "keywords": self.keywords,
        }
