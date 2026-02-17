"""Tests for the right heart catheterization handler with sample report text."""

from api.analysis_models import SeverityStatus, AbnormalityDirection
from api.models import ExtractionResult, InputMode, PageExtractionResult
from test_types.right_heart_cath.handler import RightHeartCathHandler
from test_types.right_heart_cath.measurements import extract_measurements
from test_types.right_heart_cath.reference_ranges import classify_measurement


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


SAMPLE_RHC_REPORT = """
RIGHT HEART CATHETERIZATION

Patient: [REDACTED]
Date: 04/22/2025
Indication: Evaluation of dyspnea and suspected pulmonary hypertension

ACCESS:
  Right internal jugular vein access. Swan-Ganz catheter advanced to
  pulmonary artery without difficulty.

HEMODYNAMICS:
  Right atrial pressure (RA): mean 4 mmHg
  Right ventricular pressure (RV): 24/4 mmHg
  Pulmonary artery pressure (PA): 22/10 mmHg, mean 15 mmHg
  Pulmonary capillary wedge pressure (PCWP): 10 mmHg
  Cardiac output (thermodilution): 5.2 L/min
  Cardiac index: 2.8 L/min/m2
  Pulmonary vascular resistance (PVR): 1.0 Wood units
  Transpulmonary gradient: 5 mmHg

OXYGEN SATURATIONS:
  SVC: 72%
  PA: 74%
  Aorta: 98%

CONCLUSION:
1. Normal right atrial pressure.
2. Normal pulmonary artery pressures. No pulmonary hypertension.
3. Normal PCWP. No left heart filling pressure elevation.
4. Normal cardiac output and cardiac index.
5. Normal PVR.
"""

SAMPLE_ABNORMAL_RHC_REPORT = """
RIGHT HEART CATHETERIZATION REPORT

HEMODYNAMICS:
  Right atrial pressure (RA): mean 12 mmHg
  Pulmonary artery pressure (PA): 65/30 mmHg, mean 42 mmHg
  Pulmonary capillary wedge pressure (PCWP): 8 mmHg
  Cardiac output (thermodilution): 3.8 L/min
  Cardiac index: 2.1 L/min/m2
  Pulmonary vascular resistance (PVR): 8.9 Wood units
  Transpulmonary gradient: 34 mmHg

CONCLUSION:
1. Severely elevated pulmonary artery pressures with mPAP 42 mmHg.
2. Pre-capillary pulmonary hypertension with normal PCWP and markedly elevated PVR.
3. Elevated right atrial pressure suggesting right heart failure.
4. Low cardiac index indicating reduced cardiac output.
"""


class TestDetection:
    def test_detect_typical_report(self):
        handler = RightHeartCathHandler()
        extraction = _make_extraction(SAMPLE_RHC_REPORT)
        confidence = handler.detect(extraction)
        assert confidence >= 0.8

    def test_detect_non_rhc(self):
        handler = RightHeartCathHandler()
        extraction = _make_extraction("CBC Results: WBC 7.2, RBC 4.5, Hgb 14.2")
        confidence = handler.detect(extraction)
        assert confidence < 0.2


class TestMeasurementExtraction:
    def test_extract_from_normal_report(self):
        extraction = _make_extraction(SAMPLE_RHC_REPORT)
        measurements = extract_measurements(SAMPLE_RHC_REPORT, extraction.pages)
        abbrs = {m.abbreviation for m in measurements}

        assert "RA_mean" in abbrs or "RA" in abbrs
        assert "CI" in abbrs

    def test_ra_mean_value(self):
        extraction = _make_extraction(SAMPLE_RHC_REPORT)
        measurements = extract_measurements(SAMPLE_RHC_REPORT, extraction.pages)
        ra = next(m for m in measurements if m.abbreviation == "RA_mean")
        assert ra.value == 4.0
        assert ra.unit == "mmHg"

    def test_ci_value(self):
        extraction = _make_extraction(SAMPLE_RHC_REPORT)
        measurements = extract_measurements(SAMPLE_RHC_REPORT, extraction.pages)
        ci = next(m for m in measurements if m.abbreviation == "CI")
        assert ci.value == 2.8

    def test_abnormal_report_measurements(self):
        extraction = _make_extraction(SAMPLE_ABNORMAL_RHC_REPORT)
        measurements = extract_measurements(SAMPLE_ABNORMAL_RHC_REPORT, extraction.pages)
        abbrs = {m.abbreviation: m for m in measurements}
        assert abbrs["RA_mean"].value == 12.0
        assert abbrs["CI"].value == 2.1


class TestReferenceRanges:
    def test_normal_ra(self):
        result = classify_measurement("RA_mean", 4.0)
        assert result.status == SeverityStatus.NORMAL

    def test_elevated_ra(self):
        result = classify_measurement("RA_mean", 12.0)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL

    def test_normal_pa_mean(self):
        result = classify_measurement("PA_mean", 18.0)
        assert result.status == SeverityStatus.NORMAL

    def test_elevated_pa_mean(self):
        result = classify_measurement("PA_mean", 42.0)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.ABOVE_NORMAL

    def test_normal_pcwp(self):
        result = classify_measurement("PCWP", 10.0)
        assert result.status == SeverityStatus.NORMAL

    def test_normal_ci(self):
        result = classify_measurement("CI", 2.8)
        assert result.status == SeverityStatus.NORMAL

    def test_low_ci(self):
        result = classify_measurement("CI", 1.4)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.BELOW_NORMAL


class TestFullParse:
    def test_parse_normal_report(self):
        handler = RightHeartCathHandler()
        extraction = _make_extraction(SAMPLE_RHC_REPORT)
        report = handler.parse(extraction)

        assert report.test_type == "right_heart_cath"
        assert report.test_type_display == "Right Heart Catheterization"
        assert report.detection_confidence >= 0.8
        assert len(report.measurements) >= 2
        assert len(report.findings) >= 1
        assert not report.warnings

    def test_parse_abnormal_report(self):
        handler = RightHeartCathHandler()
        extraction = _make_extraction(SAMPLE_ABNORMAL_RHC_REPORT)
        report = handler.parse(extraction)

        ra = next(m for m in report.measurements if m.abbreviation == "RA_mean")
        assert ra.status != SeverityStatus.NORMAL

    def test_parse_empty_text(self):
        handler = RightHeartCathHandler()
        extraction = _make_extraction("This is not a medical report.")
        report = handler.parse(extraction)

        assert len(report.measurements) == 0
        assert len(report.warnings) > 0


class TestGlossary:
    def test_glossary_has_key_terms(self):
        handler = RightHeartCathHandler()
        glossary = handler.get_glossary()
        assert "Right Heart Catheterization" in glossary
        assert "Cardiac Output" in glossary
        assert "PCWP / Wedge Pressure" in glossary
        assert len(glossary) >= 15

    def test_glossary_values_are_nonempty(self):
        handler = RightHeartCathHandler()
        glossary = handler.get_glossary()
        for term, definition in glossary.items():
            assert len(definition) > 20, f"Definition too short for '{term}'"
