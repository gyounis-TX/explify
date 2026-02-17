"""Tests for the CTA coronary handler with sample report text."""

from api.analysis_models import SeverityStatus, AbnormalityDirection
from api.models import ExtractionResult, InputMode, PageExtractionResult
from test_types.cta_coronary.handler import CTACoronaryHandler
from test_types.cta_coronary.measurements import extract_measurements
from test_types.cta_coronary.reference_ranges import classify_measurement


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


SAMPLE_CTA_REPORT = """
CTA CORONARY

Patient: [REDACTED]
Date: 06/18/2025
Indication: Chest pain evaluation

TECHNIQUE:
  Prospective ECG-gated coronary CTA performed with 70 mL Omnipaque 350.
  Heart rate: 58 bpm. Excellent image quality.

CALCIUM SCORE:
  Total Agatston calcium score: 0
  No coronary artery calcium identified.

LEFT MAIN:
  Normal caliber. No stenosis.

LAD:
  Normal caliber. No stenosis or plaque. No stenosis identified (0%).

LCx:
  Normal caliber. No stenosis or plaque. No stenosis identified (0%).

RCA:
  Normal caliber. No stenosis or plaque. No stenosis identified (0%).

NON-CORONARY FINDINGS:
  No pericardial effusion. Normal cardiac chambers.

CONCLUSION:
1. Calcium score of 0 Agatston units.
2. No coronary artery stenosis. CAD-RADS 0.
3. No significant non-coronary findings.
"""

SAMPLE_ABNORMAL_CTA_REPORT = """
CTA CORONARY REPORT

CALCIUM SCORE:
  Total Agatston calcium score: 450
  Moderate coronary artery calcium burden.

LEFT MAIN:
  No significant stenosis.

LAD:
  Mixed plaque in proximal LAD with 75% stenosis.
  Non-calcified plaque in mid-LAD with 40% stenosis.

LCx:
  Calcified plaque in proximal LCx with 50% stenosis.

RCA:
  Mixed plaque in mid-RCA with 30% stenosis.

CONCLUSION:
1. Calcium score 450 (moderate).
2. Severe stenosis of proximal LAD (75%). CAD-RADS 4A.
3. Moderate stenosis of proximal LCx (50%).
4. Mild stenosis of mid-RCA (30%).
"""


class TestDetection:
    def test_detect_typical_report(self):
        handler = CTACoronaryHandler()
        extraction = _make_extraction(SAMPLE_CTA_REPORT)
        confidence = handler.detect(extraction)
        assert confidence >= 0.8

    def test_detect_non_cta(self):
        handler = CTACoronaryHandler()
        extraction = _make_extraction("CBC Results: WBC 7.2, RBC 4.5, Hgb 14.2")
        confidence = handler.detect(extraction)
        assert confidence < 0.2


class TestMeasurementExtraction:
    def test_extract_from_normal_report(self):
        extraction = _make_extraction(SAMPLE_CTA_REPORT)
        measurements = extract_measurements(SAMPLE_CTA_REPORT, extraction.pages)
        abbrs = {m.abbreviation for m in measurements}

        assert "CAC_score" in abbrs or "CAC" in abbrs or "Agatston" in abbrs

    def test_cac_score_value(self):
        extraction = _make_extraction(SAMPLE_CTA_REPORT)
        measurements = extract_measurements(SAMPLE_CTA_REPORT, extraction.pages)
        cac = next(
            m for m in measurements
            if m.abbreviation in ("CAC_score", "CAC", "Agatston")
        )
        assert cac.value == 0.0

    def test_abnormal_report_measurements(self):
        extraction = _make_extraction(SAMPLE_ABNORMAL_CTA_REPORT)
        measurements = extract_measurements(SAMPLE_ABNORMAL_CTA_REPORT, extraction.pages)
        abbrs = {m.abbreviation: m for m in measurements}
        cac_key = next(
            k for k in abbrs if k in ("CAC_score", "CAC", "Agatston")
        )
        assert abbrs[cac_key].value == 450.0


class TestReferenceRanges:
    def test_normal_cac(self):
        result = classify_measurement("CAC_score", 0.0)
        assert result.status == SeverityStatus.NORMAL

    def test_severe_cac(self):
        result = classify_measurement("CAC_score", 500.0)
        assert result.status in (
            SeverityStatus.MODERATELY_ABNORMAL,
            SeverityStatus.SEVERELY_ABNORMAL,
        )
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL

    def test_normal_stenosis(self):
        result = classify_measurement("LAD_stenosis", 0.0)
        assert result.status == SeverityStatus.NORMAL

    def test_moderate_stenosis(self):
        result = classify_measurement("LAD_stenosis", 55.0)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL

    def test_severe_stenosis(self):
        result = classify_measurement("LAD_stenosis", 80.0)
        assert result.status in (
            SeverityStatus.MODERATELY_ABNORMAL,
            SeverityStatus.SEVERELY_ABNORMAL,
        )
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL


class TestFullParse:
    def test_parse_normal_report(self):
        handler = CTACoronaryHandler()
        extraction = _make_extraction(SAMPLE_CTA_REPORT)
        report = handler.parse(extraction)

        assert report.test_type == "cta_coronary"
        assert report.test_type_display == "CTA Coronary"
        assert report.detection_confidence >= 0.8
        assert len(report.measurements) >= 1
        assert len(report.findings) >= 1
        assert not report.warnings

    def test_parse_abnormal_report(self):
        handler = CTACoronaryHandler()
        extraction = _make_extraction(SAMPLE_ABNORMAL_CTA_REPORT)
        report = handler.parse(extraction)

        cac = next(
            m for m in report.measurements
            if m.abbreviation in ("CAC_score", "CAC", "Agatston")
        )
        assert cac.status != SeverityStatus.NORMAL

    def test_parse_empty_text(self):
        handler = CTACoronaryHandler()
        extraction = _make_extraction("This is not a medical report.")
        report = handler.parse(extraction)

        assert len(report.measurements) == 0
        assert len(report.warnings) > 0


class TestGlossary:
    def test_glossary_has_key_terms(self):
        handler = CTACoronaryHandler()
        glossary = handler.get_glossary()
        assert "CTA Coronary" in glossary
        assert "Calcium Score (Agatston Score)" in glossary
        assert "CAD-RADS" in glossary
        assert len(glossary) >= 15

    def test_glossary_values_are_nonempty(self):
        handler = CTACoronaryHandler()
        glossary = handler.get_glossary()
        for term, definition in glossary.items():
            assert len(definition) > 20, f"Definition too short for '{term}'"
