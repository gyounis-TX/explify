"""Tests for TestTypeRegistry and auto-detection."""

from api.models import ExtractionResult, InputMode, PageExtractionResult
from test_types import registry
from test_types.echo.handler import EchocardiogramHandler
from test_types.registry import TestTypeRegistry


def _make_extraction(text: str) -> ExtractionResult:
    return ExtractionResult(
        input_mode=InputMode.TEXT,
        full_text=text,
        pages=[
            PageExtractionResult(
                page_number=1,
                text=text,
                extraction_method="test",
                confidence=1.0,
                char_count=len(text),
            )
        ],
        tables=[],
        total_pages=1,
        total_chars=len(text),
    )


class TestRegistry:
    def test_register_and_get(self):
        reg = TestTypeRegistry()
        handler = EchocardiogramHandler()
        reg.register(handler)
        assert reg.get("echocardiogram") is handler

    def test_get_unknown_returns_none(self):
        reg = TestTypeRegistry()
        assert reg.get("unknown") is None

    def test_list_types(self):
        reg = TestTypeRegistry()
        reg.register(EchocardiogramHandler())
        types = reg.list_types()
        assert len(types) == 1
        assert types[0]["test_type_id"] == "echocardiogram"

    def test_detect_echo(self):
        extraction = _make_extraction(
            "TRANSTHORACIC ECHOCARDIOGRAM\n"
            "LVEF: 55%\n"
            "Mitral valve: trace regurgitation\n"
        )
        type_id, confidence = registry.detect(extraction)
        assert type_id == "echocardiogram"
        assert confidence >= 0.7

    def test_detect_lab_results(self):
        extraction = _make_extraction("Complete Blood Count results: WBC 7.2")
        type_id, confidence = registry.detect(extraction)
        assert type_id == "lab_results"
        assert confidence >= 0.7

    def test_detect_unrecognized(self):
        extraction = _make_extraction("Patient visited the clinic for a routine checkup today.")
        type_id, confidence = registry.detect(extraction)
        assert confidence < 0.3


class TestModuleSingleton:
    def test_registry_has_echo(self):
        handler = registry.get("echocardiogram")
        assert handler is not None
        assert handler.test_type_id == "echocardiogram"
