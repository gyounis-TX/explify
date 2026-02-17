"""Tests for the cardiac MRI handler with sample report text."""

from api.analysis_models import SeverityStatus, AbnormalityDirection
from api.models import ExtractionResult, InputMode, PageExtractionResult
from test_types.cardiac_mri.handler import CardiacMRIHandler
from test_types.cardiac_mri.measurements import extract_measurements
from test_types.cardiac_mri.reference_ranges import classify_measurement


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


SAMPLE_CMR_REPORT = """
CARDIAC MRI

Patient: [REDACTED]
Date: 03/10/2025
Indication: Evaluation of cardiomyopathy

TECHNIQUE:
  Cine imaging, late gadolinium enhancement, T1 mapping, T2 mapping.
  Gadolinium contrast administered: 0.1 mmol/kg Gadovist.

LEFT VENTRICLE:
  LVEDV: 140 mL
  LVESV: 53 mL
  LVSV: 87 mL
  LVEF: 62%
  LV mass: 120 g
  Wall motion: Normal

RIGHT VENTRICLE:
  RVEDV: 130 mL
  RVESV: 50 mL
  RVEF: 62%

TISSUE CHARACTERIZATION:
  Native T1 (mid-septum): 1010 ms
  T2 (mid-septum): 48 ms
  ECV: 25%

LATE GADOLINIUM ENHANCEMENT:
  No late gadolinium enhancement identified.
  No evidence of myocardial scar or fibrosis.

PERFUSION:
  Normal first-pass perfusion. No perfusion defects at rest or stress.

CONCLUSION:
1. Normal biventricular size and systolic function with LVEF 62%.
2. No late gadolinium enhancement to suggest myocardial scar or fibrosis.
3. Normal T1 and T2 mapping values. Normal ECV.
4. No perfusion defects.
"""

SAMPLE_ABNORMAL_CMR_REPORT = """
CARDIAC MRI REPORT

LEFT VENTRICLE:
  LVEDV: 280 mL
  LVESV: 202 mL
  LVEF: 28%
  LV mass: 190 g

TISSUE CHARACTERIZATION:
  Native T1 (mid-septum): 1120 ms
  T2 (mid-septum): 65 ms
  ECV: 35%

LATE GADOLINIUM ENHANCEMENT:
  Extensive mid-wall late gadolinium enhancement involving the septum
  and inferior wall. Scar burden estimated at 18%.

CONCLUSION:
1. Severely reduced left ventricular systolic function with LVEF 28%.
2. Severely dilated left ventricle.
3. Elevated native T1 and T2 values suggesting active myocardial inflammation.
4. Elevated ECV consistent with diffuse fibrosis.
5. Extensive mid-wall LGE with scar burden of 18%.
"""


class TestDetection:
    def test_detect_typical_report(self):
        handler = CardiacMRIHandler()
        extraction = _make_extraction(SAMPLE_CMR_REPORT)
        confidence = handler.detect(extraction)
        assert confidence >= 0.8

    def test_detect_non_cmr(self):
        handler = CardiacMRIHandler()
        extraction = _make_extraction("CBC Results: WBC 7.2, RBC 4.5, Hgb 14.2")
        confidence = handler.detect(extraction)
        assert confidence < 0.2


class TestMeasurementExtraction:
    def test_extract_from_normal_report(self):
        extraction = _make_extraction(SAMPLE_CMR_REPORT)
        measurements = extract_measurements(SAMPLE_CMR_REPORT, extraction.pages)
        abbrs = {m.abbreviation for m in measurements}

        assert "LVEF" in abbrs
        assert "LVEDV" in abbrs
        assert "ECV" in abbrs

    def test_lvef_value(self):
        extraction = _make_extraction(SAMPLE_CMR_REPORT)
        measurements = extract_measurements(SAMPLE_CMR_REPORT, extraction.pages)
        ef = next(m for m in measurements if m.abbreviation == "LVEF")
        assert ef.value == 62.0

    def test_lvedv_value(self):
        extraction = _make_extraction(SAMPLE_CMR_REPORT)
        measurements = extract_measurements(SAMPLE_CMR_REPORT, extraction.pages)
        m = next(m for m in measurements if m.abbreviation == "LVEDV")
        assert m.value == 140.0
        assert m.unit == "mL"

    def test_abnormal_report_measurements(self):
        extraction = _make_extraction(SAMPLE_ABNORMAL_CMR_REPORT)
        measurements = extract_measurements(SAMPLE_ABNORMAL_CMR_REPORT, extraction.pages)
        abbrs = {m.abbreviation: m for m in measurements}
        assert abbrs["LVEF"].value == 28.0
        assert abbrs["LVEDV"].value == 280.0


class TestReferenceRanges:
    def test_normal_lvef(self):
        result = classify_measurement("LVEF", 60.0)
        assert result.status == SeverityStatus.NORMAL

    def test_reduced_lvef(self):
        result = classify_measurement("LVEF", 28.0)
        assert result.status in (
            SeverityStatus.MODERATELY_ABNORMAL,
            SeverityStatus.SEVERELY_ABNORMAL,
        )
        assert result.direction == AbnormalityDirection.BELOW_NORMAL

    def test_normal_native_t1(self):
        result = classify_measurement("NativeT1", 1010.0)
        assert result.status == SeverityStatus.NORMAL

    def test_elevated_native_t1(self):
        result = classify_measurement("NativeT1", 1120.0)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL

    def test_unknown_measurement(self):
        result = classify_measurement("UNKNOWN", 42.0)
        assert result.status == SeverityStatus.UNDETERMINED


class TestFullParse:
    def test_parse_normal_report(self):
        handler = CardiacMRIHandler()
        extraction = _make_extraction(SAMPLE_CMR_REPORT)
        report = handler.parse(extraction)

        assert report.test_type == "cardiac_mri"
        assert report.test_type_display == "Cardiac MRI"
        assert report.detection_confidence >= 0.8
        assert len(report.measurements) >= 5
        assert len(report.findings) >= 1
        assert not report.warnings

    def test_parse_abnormal_report(self):
        handler = CardiacMRIHandler()
        extraction = _make_extraction(SAMPLE_ABNORMAL_CMR_REPORT)
        report = handler.parse(extraction)

        ef = next(m for m in report.measurements if m.abbreviation == "LVEF")
        assert ef.status == SeverityStatus.SEVERELY_ABNORMAL

    def test_parse_empty_text(self):
        handler = CardiacMRIHandler()
        extraction = _make_extraction("This is not a medical report.")
        report = handler.parse(extraction)

        assert len(report.measurements) == 0
        assert len(report.warnings) > 0


class TestGlossary:
    def test_glossary_has_key_terms(self):
        handler = CardiacMRIHandler()
        glossary = handler.get_glossary()
        assert "Cardiac MRI" in glossary
        assert "T1 Mapping" in glossary
        assert "Late Gadolinium Enhancement (LGE)" in glossary
        assert len(glossary) >= 20

    def test_glossary_values_are_nonempty(self):
        handler = CardiacMRIHandler()
        glossary = handler.get_glossary()
        for term, definition in glossary.items():
            assert len(definition) > 20, f"Definition too short for '{term}'"
