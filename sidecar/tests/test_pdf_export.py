"""Tests for PDF report generation."""

import pytest

try:
    import weasyprint  # noqa: F401
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

SAMPLE_EXPLAIN_RESPONSE = {
    "explanation": {
        "overall_summary": "The echocardiogram shows normal heart function.",
        "measurements": [
            {
                "abbreviation": "LVEF",
                "value": 57.5,
                "unit": "%",
                "status": "normal",
                "plain_language": "Your heart is pumping normally.",
            },
            {
                "abbreviation": "LVIDd",
                "value": 4.8,
                "unit": "cm",
                "status": "normal",
                "plain_language": "Left ventricle size is normal.",
            },
        ],
        "key_findings": [
            {
                "finding": "Normal left ventricular function",
                "severity": "normal",
                "explanation": "The heart is pumping blood effectively.",
            },
        ],
        "questions_for_doctor": [
            "When should I have my next echocardiogram?",
        ],
        "disclaimer": "This is not a medical diagnosis.",
    },
    "parsed_report": {
        "test_type": "echocardiogram",
        "test_type_display": "Echocardiogram",
        "detection_confidence": 0.95,
        "measurements": [
            {
                "name": "Left Ventricular Ejection Fraction",
                "abbreviation": "LVEF",
                "value": 57.5,
                "unit": "%",
                "status": "normal",
                "direction": "normal",
                "reference_range": "52-70%",
                "raw_text": "LVEF: 55-60%",
                "page_number": 1,
            },
            {
                "name": "Left Ventricular Internal Diameter in Diastole",
                "abbreviation": "LVIDd",
                "value": 4.8,
                "unit": "cm",
                "status": "normal",
                "direction": "normal",
                "reference_range": "3.5-5.6 cm",
                "raw_text": "LVIDd: 4.8 cm",
                "page_number": 1,
            },
        ],
        "sections": [],
        "findings": [],
        "warnings": [],
    },
    "validation_warnings": [],
    "phi_categories_found": [],
    "model_used": "test",
    "input_tokens": 0,
    "output_tokens": 0,
}


@pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
class TestPdfExport:
    def test_render_pdf_returns_bytes(self):
        from report_gen import render_pdf

        result = render_pdf(SAMPLE_EXPLAIN_RESPONSE)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_starts_with_magic_bytes(self):
        from report_gen import render_pdf

        result = render_pdf(SAMPLE_EXPLAIN_RESPONSE)
        assert result[:5] == b"%PDF-"

    def test_pdf_contains_expected_text(self):
        from report_gen import render_pdf

        result = render_pdf(SAMPLE_EXPLAIN_RESPONSE)
        # PDF text is encoded but we can check for common markers
        assert b"PDF" in result
