"""Tests for the pulmonary function test (PFT) handler with sample report text."""

from api.analysis_models import SeverityStatus, AbnormalityDirection
from api.models import ExtractionResult, InputMode, PageExtractionResult
from test_types.pft.handler import PFTHandler
from test_types.pft.measurements import extract_measurements
from test_types.pft.reference_ranges import classify_measurement


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


SAMPLE_PFT_REPORT = """
PULMONARY FUNCTION TEST

Patient: [REDACTED]
Date: 07/09/2025
Indication: Evaluation of dyspnea

SPIROMETRY:
                    Actual    Predicted    % Predicted
  FEV1:            3.5 L     3.7 L        95%
  FVC:             4.2 L     4.3 L        98%
  FEV1/FVC:        83%
  PEF:             8.5 L/s   9.0 L/s      94%

LUNG VOLUMES:
  TLC:             6.0 L     6.0 L        100%
  RV:              1.8 L     1.8 L        100%
  FRC:             3.0 L     3.0 L        100%

DIFFUSION:
  DLCO:            28 mL/min/mmHg         92% predicted

INTERPRETATION:
1. Normal spirometry. FEV1 and FVC within normal limits.
2. FEV1/FVC ratio normal at 83%.
3. Normal lung volumes.
4. Normal diffusing capacity (DLCO 92% predicted).
5. No evidence of obstructive or restrictive ventilatory defect.
"""

SAMPLE_ABNORMAL_PFT_REPORT = """
PULMONARY FUNCTION TEST REPORT

SPIROMETRY:
                    Actual    Predicted    % Predicted
  FEV1:            1.8 L     3.7 L        48%
  FVC:             3.0 L     4.2 L        72%
  FEV1/FVC:        60%
  PEF:             4.2 L/s   9.0 L/s      47%

LUNG VOLUMES:
  TLC:             7.2 L     5.5 L        130%
  RV:              3.8 L     1.8 L        211%

DIFFUSION:
  DLCO:            15 mL/min/mmHg         42% predicted

BRONCHODILATOR:
  Post-bronchodilator FEV1: 2.0 L (11% improvement). No significant
  bronchodilator response.

INTERPRETATION:
1. Severe obstructive ventilatory defect with FEV1 48% predicted.
2. FEV1/FVC ratio reduced at 60%, consistent with obstruction.
3. Air trapping with elevated RV and TLC.
4. Moderately reduced diffusing capacity (DLCO 42% predicted).
5. No significant bronchodilator response.
"""


class TestDetection:
    def test_detect_typical_report(self):
        handler = PFTHandler()
        extraction = _make_extraction(SAMPLE_PFT_REPORT)
        confidence = handler.detect(extraction)
        assert confidence >= 0.8

    def test_detect_non_pft(self):
        handler = PFTHandler()
        extraction = _make_extraction("CBC Results: WBC 7.2, RBC 4.5, Hgb 14.2")
        confidence = handler.detect(extraction)
        assert confidence < 0.2


class TestMeasurementExtraction:
    def test_extract_from_normal_report(self):
        extraction = _make_extraction(SAMPLE_PFT_REPORT)
        measurements = extract_measurements(SAMPLE_PFT_REPORT, extraction.pages)
        abbrs = {m.abbreviation for m in measurements}

        assert "FEV1_pct" in abbrs or "FEV1" in abbrs
        assert "FVC_pct" in abbrs or "FVC" in abbrs
        assert "FEV1_FVC" in abbrs or "FEV1/FVC" in abbrs
        assert "DLCO_pct" in abbrs or "DLCO" in abbrs
        assert "TLC_pct" in abbrs or "TLC" in abbrs

    def test_fev1_value(self):
        extraction = _make_extraction(SAMPLE_PFT_REPORT)
        measurements = extract_measurements(SAMPLE_PFT_REPORT, extraction.pages)
        fev1 = next(
            m for m in measurements
            if m.abbreviation in ("FEV1_pct", "FEV1")
        )
        # Either the absolute value (3.5) or percent predicted (95)
        assert fev1.value in (3.5, 95.0)

    def test_abnormal_report_measurements(self):
        extraction = _make_extraction(SAMPLE_ABNORMAL_PFT_REPORT)
        measurements = extract_measurements(SAMPLE_ABNORMAL_PFT_REPORT, extraction.pages)
        abbrs = {m.abbreviation: m for m in measurements}

        fev1_key = next(
            k for k in abbrs if k in ("FEV1_pct", "FEV1")
        )
        # Either absolute 1.8 or percent predicted 48
        assert abbrs[fev1_key].value in (1.8, 48.0)


class TestReferenceRanges:
    def test_normal_fev1_pct(self):
        result = classify_measurement("FEV1_pct", 95.0)
        assert result.status == SeverityStatus.NORMAL

    def test_mild_fev1_pct(self):
        result = classify_measurement("FEV1_pct", 75.0)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.BELOW_NORMAL

    def test_severe_fev1_pct(self):
        result = classify_measurement("FEV1_pct", 30.0)
        assert result.status in (
            SeverityStatus.MODERATELY_ABNORMAL,
            SeverityStatus.SEVERELY_ABNORMAL,
        )
        assert result.direction == AbnormalityDirection.BELOW_NORMAL

    def test_normal_fev1_fvc(self):
        result = classify_measurement("FEV1_FVC", 83.0)
        assert result.status == SeverityStatus.NORMAL

    def test_low_fev1_fvc(self):
        result = classify_measurement("FEV1_FVC", 60.0)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.BELOW_NORMAL

    def test_absolute_fev1_undetermined(self):
        result = classify_measurement("FEV1_abs", 3.5)
        assert result.status == SeverityStatus.UNDETERMINED


class TestFullParse:
    def test_parse_normal_report(self):
        handler = PFTHandler()
        extraction = _make_extraction(SAMPLE_PFT_REPORT)
        report = handler.parse(extraction)

        assert report.test_type == "pft"
        assert report.test_type_display == "Pulmonary Function Test"
        assert report.detection_confidence >= 0.8
        assert len(report.measurements) >= 3
        assert len(report.findings) >= 1
        assert not report.warnings

    def test_parse_abnormal_report(self):
        handler = PFTHandler()
        extraction = _make_extraction(SAMPLE_ABNORMAL_PFT_REPORT)
        report = handler.parse(extraction)

        fev1_measures = [
            m for m in report.measurements
            if m.abbreviation in ("FEV1_pct", "FEV1")
        ]
        assert len(fev1_measures) > 0
        assert fev1_measures[0].status != SeverityStatus.NORMAL

    def test_parse_empty_text(self):
        handler = PFTHandler()
        extraction = _make_extraction("This is not a medical report.")
        report = handler.parse(extraction)

        assert len(report.measurements) == 0
        assert len(report.warnings) > 0


class TestGlossary:
    def test_glossary_has_key_terms(self):
        handler = PFTHandler()
        glossary = handler.get_glossary()
        assert "Pulmonary Function Test" in glossary
        assert "FEV1" in glossary
        assert "FEV1/FVC Ratio" in glossary
        assert len(glossary) >= 20

    def test_glossary_values_are_nonempty(self):
        handler = PFTHandler()
        glossary = handler.get_glossary()
        for term, definition in glossary.items():
            assert len(definition) > 20, f"Definition too short for '{term}'"
