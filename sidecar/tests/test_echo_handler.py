"""Tests for the echocardiogram handler with sample report text."""

from api.analysis_models import SeverityStatus, AbnormalityDirection
from api.models import ExtractionResult, InputMode, PageExtractionResult
from test_types.echo.handler import EchocardiogramHandler
from test_types.echo.measurements import extract_measurements
from test_types.echo.reference_ranges import classify_measurement


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


SAMPLE_ECHO_REPORT = """
TRANSTHORACIC ECHOCARDIOGRAM

Patient: [REDACTED]
Date: 01/15/2025
Indication: Shortness of breath

LEFT VENTRICLE:
  LVIDd: 4.8 cm
  LVIDs: 3.2 cm
  IVSd: 1.0 cm
  LVPWd: 1.0 cm
  LVEF: 55-60%
  Fractional Shortening: 33%
  Wall motion: Normal

LEFT ATRIUM:
  LA diameter: 3.6 cm
  LA Volume Index: 28 mL/m2

RIGHT VENTRICLE:
  RV basal diameter: 3.5 cm
  TAPSE: 2.1 cm

RIGHT ATRIUM:
  RA area: 15 cm2

AORTIC ROOT:
  Aortic root: 3.2 cm

AORTIC VALVE:
  Aortic valve area: 2.5 cm2
  No aortic stenosis. Trace aortic regurgitation.

MITRAL VALVE:
  E/A ratio: 1.2
  E velocity: 75 cm/s
  A velocity: 62 cm/s
  Deceleration time: 190 ms
  Mild mitral regurgitation.

DIASTOLIC FUNCTION:
  e' septal: 9 cm/s
  e' lateral: 12 cm/s
  E/e' ratio: 8.3
  IVRT: 80 ms

TRICUSPID VALVE:
  TR velocity: 2.5 m/s
  RVSP: 30 mmHg
  Trace tricuspid regurgitation.

PERICARDIUM:
  No pericardial effusion.

CONCLUSION:
1. Normal left ventricular size and systolic function with LVEF 55-60%.
2. Normal diastolic function.
3. Mild mitral regurgitation.
4. No significant pericardial effusion.
"""

SAMPLE_ABNORMAL_REPORT = """
ECHOCARDIOGRAM REPORT

LEFT VENTRICLE:
  LVIDd: 6.5 cm
  LVIDs: 5.2 cm
  IVSd: 0.8 cm
  LVPWd: 0.8 cm
  Ejection fraction: 30%
  Wall motion: Global hypokinesis

LEFT ATRIUM:
  LA Volume Index: 42 mL/m2

TRICUSPID VALVE:
  RVSP: 55 mmHg

CONCLUSION:
1. Severely reduced left ventricular systolic function with LVEF 30%.
2. Dilated left ventricle.
3. Moderately dilated left atrium.
4. Moderately elevated RVSP suggesting pulmonary hypertension.
"""


class TestEchoDetection:
    def test_detect_typical_report(self):
        handler = EchocardiogramHandler()
        extraction = _make_extraction(SAMPLE_ECHO_REPORT)
        confidence = handler.detect(extraction)
        assert confidence >= 0.8

    def test_detect_non_echo(self):
        handler = EchocardiogramHandler()
        extraction = _make_extraction("CBC Results: WBC 7.2, RBC 4.5, Hgb 14.2")
        confidence = handler.detect(extraction)
        assert confidence < 0.2


class TestMeasurementExtraction:
    def test_extract_from_normal_report(self):
        extraction = _make_extraction(SAMPLE_ECHO_REPORT)
        measurements = extract_measurements(SAMPLE_ECHO_REPORT, extraction.pages)
        abbrs = {m.abbreviation for m in measurements}

        assert "LVEF" in abbrs
        assert "LVIDd" in abbrs
        assert "LVIDs" in abbrs
        assert "IVSd" in abbrs
        assert "LVPWd" in abbrs
        assert "LAVI" in abbrs
        assert "RVSP" in abbrs
        assert "E/A" in abbrs
        assert "E/e'" in abbrs
        assert "TAPSE" in abbrs

    def test_ef_range_midpoint(self):
        extraction = _make_extraction(SAMPLE_ECHO_REPORT)
        measurements = extract_measurements(SAMPLE_ECHO_REPORT, extraction.pages)
        ef = next(m for m in measurements if m.abbreviation == "LVEF")
        assert ef.value == 57.5

    def test_ef_single_value(self):
        text = "LVEF: 45%"
        extraction = _make_extraction(text)
        measurements = extract_measurements(text, extraction.pages)
        ef = next(m for m in measurements if m.abbreviation == "LVEF")
        assert ef.value == 45.0

    def test_lvidd_value(self):
        text = "LVIDd: 4.8 cm"
        extraction = _make_extraction(text)
        measurements = extract_measurements(text, extraction.pages)
        m = next(m for m in measurements if m.abbreviation == "LVIDd")
        assert m.value == 4.8
        assert m.unit == "cm"

    def test_abnormal_report_measurements(self):
        extraction = _make_extraction(SAMPLE_ABNORMAL_REPORT)
        measurements = extract_measurements(SAMPLE_ABNORMAL_REPORT, extraction.pages)
        abbrs = {m.abbreviation: m for m in measurements}
        assert abbrs["LVEF"].value == 30.0
        assert abbrs["LVIDd"].value == 6.5
        assert abbrs["RVSP"].value == 55.0


class TestReferenceRanges:
    def test_normal_ef(self):
        result = classify_measurement("LVEF", 58.0)
        assert result.status == SeverityStatus.NORMAL

    def test_mildly_reduced_ef(self):
        result = classify_measurement("LVEF", 45.0)
        assert result.status == SeverityStatus.MILDLY_ABNORMAL
        assert result.direction == AbnormalityDirection.BELOW_NORMAL

    def test_severely_reduced_ef(self):
        result = classify_measurement("LVEF", 25.0)
        assert result.status == SeverityStatus.SEVERELY_ABNORMAL

    def test_normal_lvidd(self):
        result = classify_measurement("LVIDd", 4.8)
        assert result.status == SeverityStatus.NORMAL

    def test_dilated_lvidd(self):
        result = classify_measurement("LVIDd", 6.5)
        assert result.status in (
            SeverityStatus.MILDLY_ABNORMAL,
            SeverityStatus.MODERATELY_ABNORMAL,
            SeverityStatus.SEVERELY_ABNORMAL,
        )
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL

    def test_elevated_rvsp(self):
        result = classify_measurement("RVSP", 55.0)
        assert result.status == SeverityStatus.MODERATELY_ABNORMAL
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL

    def test_unknown_measurement(self):
        result = classify_measurement("UNKNOWN", 42.0)
        assert result.status == SeverityStatus.UNDETERMINED

    def test_normal_tapse(self):
        result = classify_measurement("TAPSE", 2.1)
        assert result.status == SeverityStatus.NORMAL

    def test_reduced_tapse(self):
        result = classify_measurement("TAPSE", 1.3)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.BELOW_NORMAL


class TestFullParse:
    def test_parse_normal_report(self):
        handler = EchocardiogramHandler()
        extraction = _make_extraction(SAMPLE_ECHO_REPORT)
        report = handler.parse(extraction)

        assert report.test_type == "echocardiogram"
        assert report.test_type_display == "Echocardiogram"
        assert report.detection_confidence >= 0.8
        assert len(report.measurements) >= 10
        assert len(report.findings) >= 1
        assert not report.warnings

    def test_parse_abnormal_report(self):
        handler = EchocardiogramHandler()
        extraction = _make_extraction(SAMPLE_ABNORMAL_REPORT)
        report = handler.parse(extraction)

        ef = next(m for m in report.measurements if m.abbreviation == "LVEF")
        assert ef.status == SeverityStatus.SEVERELY_ABNORMAL

    def test_parse_empty_text(self):
        handler = EchocardiogramHandler()
        extraction = _make_extraction("This is not a medical report.")
        report = handler.parse(extraction)

        assert len(report.measurements) == 0
        assert len(report.warnings) > 0


class TestGlossary:
    def test_glossary_has_key_terms(self):
        handler = EchocardiogramHandler()
        glossary = handler.get_glossary()
        assert "Ejection Fraction" in glossary
        assert "Left Ventricle" in glossary
        assert "Mitral Regurgitation" in glossary
        assert len(glossary) >= 30

    def test_glossary_values_are_nonempty(self):
        handler = EchocardiogramHandler()
        glossary = handler.get_glossary()
        for term, definition in glossary.items():
            assert len(definition) > 20, f"Definition too short for '{term}'"
