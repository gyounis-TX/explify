"""Tests for the transesophageal echocardiogram (TEE) handler with sample report text."""

from api.analysis_models import SeverityStatus, AbnormalityDirection
from api.models import ExtractionResult, InputMode, PageExtractionResult
from test_types.tee.handler import TEEHandler
from test_types.tee.measurements import extract_measurements
from test_types.tee.reference_ranges import classify_measurement


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


SAMPLE_TEE_REPORT = """
TRANSESOPHAGEAL ECHOCARDIOGRAM

Patient: [REDACTED]
Date: 05/14/2025
Indication: Pre-cardioversion evaluation, rule out LAA thrombus

SEDATION:
  Moderate sedation with midazolam and fentanyl. Probe inserted without difficulty.

LEFT ATRIAL APPENDAGE:
  LAA emptying velocity: 55 cm/s
  No thrombus or spontaneous echo contrast identified in the LAA.
  LAA morphology: Chicken wing type.

INTERATRIAL SEPTUM:
  Normal interatrial septum. No PFO or ASD identified.
  Bubble study with agitated saline: negative for right-to-left shunt.

AORTIC VALVE:
  Trileaflet aortic valve with normal leaflet excursion.
  Aortic valve area: 2.5 cm2
  AV mean gradient: 8 mmHg
  No aortic regurgitation.

MITRAL VALVE:
  Normal mitral valve morphology.
  Mitral valve area: 4.5 cm2
  Trace mitral regurgitation.

AORTA:
  No aortic atheroma. Normal ascending aorta and aortic arch.

CONCLUSION:
1. No LAA thrombus. Normal LAA emptying velocity of 55 cm/s.
2. Normal interatrial septum. Negative bubble study.
3. Normal aortic valve with AVA 2.5 cm2 and mean gradient 8 mmHg.
4. Normal mitral valve with trace MR.
5. No significant aortic atheroma.
"""

SAMPLE_ABNORMAL_TEE_REPORT = """
TRANSESOPHAGEAL ECHOCARDIOGRAM REPORT

LEFT ATRIAL APPENDAGE:
  LAA emptying velocity: 15 cm/s
  Dense spontaneous echo contrast (smoke) in LAA.
  A 1.2 cm x 0.8 cm thrombus identified in the LAA.

INTERATRIAL SEPTUM:
  Patent foramen ovale (PFO) identified with right-to-left shunt
  demonstrated on bubble study at rest and with Valsalva.

AORTIC VALVE:
  Severely calcified trileaflet aortic valve.
  Aortic valve area: 0.8 cm2
  AV mean gradient: 48 mmHg
  Mild aortic regurgitation.

CONCLUSION:
1. LAA thrombus measuring 1.2 x 0.8 cm. Severely reduced LAA emptying velocity.
2. PFO with right-to-left shunt at rest and with Valsalva.
3. Severe aortic stenosis with AVA 0.8 cm2 and mean gradient 48 mmHg.
"""


class TestDetection:
    def test_detect_typical_report(self):
        handler = TEEHandler()
        extraction = _make_extraction(SAMPLE_TEE_REPORT)
        confidence = handler.detect(extraction)
        assert confidence >= 0.8

    def test_detect_non_tee(self):
        handler = TEEHandler()
        extraction = _make_extraction("CBC Results: WBC 7.2, RBC 4.5, Hgb 14.2")
        confidence = handler.detect(extraction)
        assert confidence < 0.2


class TestMeasurementExtraction:
    def test_extract_from_normal_report(self):
        extraction = _make_extraction(SAMPLE_TEE_REPORT)
        measurements = extract_measurements(SAMPLE_TEE_REPORT, extraction.pages)
        abbrs = {m.abbreviation for m in measurements}

        assert "LAA_vel" in abbrs or "LAA_emptying_vel" in abbrs
        assert "AVA" in abbrs
        assert "MV_area" in abbrs or "MVA" in abbrs
        assert "AV_gradient_mean" in abbrs or "AV_mean_gradient" in abbrs

    def test_ava_value(self):
        extraction = _make_extraction(SAMPLE_TEE_REPORT)
        measurements = extract_measurements(SAMPLE_TEE_REPORT, extraction.pages)
        ava = next(m for m in measurements if m.abbreviation == "AVA")
        assert ava.value == 2.5
        assert ava.unit == "cm2"

    def test_abnormal_report_measurements(self):
        extraction = _make_extraction(SAMPLE_ABNORMAL_TEE_REPORT)
        measurements = extract_measurements(SAMPLE_ABNORMAL_TEE_REPORT, extraction.pages)
        abbrs = {m.abbreviation: m for m in measurements}
        assert abbrs["AVA"].value == 0.8


class TestReferenceRanges:
    def test_normal_laa_vel(self):
        result = classify_measurement("LAA_vel", 55.0)
        assert result.status == SeverityStatus.NORMAL

    def test_low_laa_vel(self):
        result = classify_measurement("LAA_vel", 15.0)
        assert result.status != SeverityStatus.NORMAL
        assert result.direction == AbnormalityDirection.BELOW_NORMAL

    def test_normal_ava(self):
        result = classify_measurement("AVA", 2.5)
        assert result.status == SeverityStatus.NORMAL

    def test_severe_ava(self):
        result = classify_measurement("AVA", 0.8)
        assert result.status in (
            SeverityStatus.MODERATELY_ABNORMAL,
            SeverityStatus.SEVERELY_ABNORMAL,
        )
        assert result.direction == AbnormalityDirection.BELOW_NORMAL

    def test_unknown_measurement(self):
        result = classify_measurement("UNKNOWN", 42.0)
        assert result.status == SeverityStatus.UNDETERMINED


class TestFullParse:
    def test_parse_normal_report(self):
        handler = TEEHandler()
        extraction = _make_extraction(SAMPLE_TEE_REPORT)
        report = handler.parse(extraction)

        assert report.test_type == "tee"
        assert report.test_type_display == "Transesophageal Echocardiogram"
        assert report.detection_confidence >= 0.8
        assert len(report.measurements) >= 3
        assert len(report.findings) >= 1
        assert not report.warnings

    def test_parse_abnormal_report(self):
        handler = TEEHandler()
        extraction = _make_extraction(SAMPLE_ABNORMAL_TEE_REPORT)
        report = handler.parse(extraction)

        ava = next(m for m in report.measurements if m.abbreviation == "AVA")
        assert ava.status in (
            SeverityStatus.MODERATELY_ABNORMAL,
            SeverityStatus.SEVERELY_ABNORMAL,
        )

    def test_parse_empty_text(self):
        handler = TEEHandler()
        extraction = _make_extraction("This is not a medical report.")
        report = handler.parse(extraction)

        assert len(report.measurements) == 0
        assert len(report.warnings) > 0


class TestGlossary:
    def test_glossary_has_key_terms(self):
        handler = TEEHandler()
        glossary = handler.get_glossary()
        assert "Transesophageal Echocardiogram" in glossary
        assert "Left Atrial Appendage (LAA)" in glossary
        assert "LAA Emptying Velocity" in glossary
        assert len(glossary) >= 20

    def test_glossary_values_are_nonempty(self):
        handler = TEEHandler()
        glossary = handler.get_glossary()
        for term, definition in glossary.items():
            assert len(definition) > 20, f"Definition too short for '{term}'"
