from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType
from .glossary import LAB_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


class LabResultsHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "lab_results"

    @property
    def display_name(self) -> str:
        return "Blood Lab Results"

    @property
    def keywords(self) -> list[str]:
        return [
            "laboratory results",
            "lab results",
            "complete blood count",
            "comprehensive metabolic panel",
            "basic metabolic panel",
            "lipid panel",
            "cbc",
            "cmp",
            "bmp",
            "glucose",
            "creatinine",
            "hemoglobin",
            "hematocrit",
            "cholesterol",
            "triglycerides",
            "tsh",
            "hba1c",
            "ferritin",
        ]

    def detect(self, extraction_result: ExtractionResult) -> float:
        """Keyword-based detection with tiered scoring."""
        text = extraction_result.full_text.lower()

        strong_keywords = [
            "laboratory results",
            "lab results",
            "lab report",
            "complete blood count",
            "comprehensive metabolic panel",
            "basic metabolic panel",
            "lipid panel",
            "chemistry panel",
            "metabolic panel",
            "thyroid panel",
            "iron studies",
            "hematology",
            "haematology",
            "cbc with differential",
            "complete haemogram",
            "complete hemogram",
        ]
        moderate_keywords = [
            "cbc",
            "cmp",
            "bmp",
            "glucose",
            "creatinine",
            "hemoglobin",
            "haemoglobin",
            "hematocrit",
            "haematocrit",
            "wbc",
            "rbc",
            "potassium",
            "sodium",
            "cholesterol",
            "triglycerides",
            "tsh",
            "hba1c",
            "a1c",
            "alt",
            "ast",
            "bun",
            "egfr",
            "ferritin",
            "albumin",
            "bilirubin",
            "platelet",
            "hdl",
            "ldl",
            "alkaline phosphatase",
            "haemogram",
            "leucocyte",
            "erythrocyte",
        ]
        weak_keywords = [
            "mg/dl",
            "g/dl",
            "meq/l",
            "k/ul",
            "u/l",
            "ng/ml",
            "ng/dl",
            "gm/dl",
            "gm/ dl",
            "reference range",
            "flag",
            "abnormal",
            "out of range",
            "/cumm",
            "lakh/",
        ]

        strong_count = sum(1 for k in strong_keywords if k in text)
        moderate_count = sum(1 for k in moderate_keywords if k in text)
        weak_count = sum(1 for k in weak_keywords if k in text)

        if strong_count > 0:
            base = 0.7
        elif moderate_count >= 3:
            base = 0.4
        elif moderate_count >= 1:
            base = 0.2
        else:
            base = 0.0

        bonus = min(0.3, moderate_count * 0.05 + weak_count * 0.02)
        return min(1.0, base + bonus)

    def parse(self, extraction_result: ExtractionResult) -> ParsedReport:
        """Extract structured measurements, sections, and findings."""
        text = extraction_result.full_text
        warnings: list[str] = []

        raw_measurements = extract_measurements(
            text, extraction_result.pages, extraction_result.tables
        )

        parsed_measurements: list[ParsedMeasurement] = []
        for m in raw_measurements:
            classification = classify_measurement(m.abbreviation, m.value)
            parsed_measurements.append(
                ParsedMeasurement(
                    name=m.name,
                    abbreviation=m.abbreviation,
                    value=m.value,
                    unit=m.unit,
                    status=classification.status,
                    direction=classification.direction,
                    reference_range=classification.reference_range_str,
                    raw_text=m.raw_text,
                    page_number=m.page_number,
                )
            )

        sections = self._extract_sections(text)
        findings = self._extract_findings(text)

        if not parsed_measurements:
            warnings.append(
                "No measurements could be extracted. "
                "The report format may not be supported."
            )

        detection_confidence = self.detect(extraction_result)

        return ParsedReport(
            test_type=self.test_type_id,
            test_type_display=self.display_name,
            detection_confidence=detection_confidence,
            measurements=parsed_measurements,
            sections=sections,
            findings=findings,
            warnings=warnings,
        )

    def get_reference_ranges(self) -> dict:
        return {
            abbr: {
                "normal_min": rr.normal_min,
                "normal_max": rr.normal_max,
                "unit": rr.unit,
                "source": rr.source,
            }
            for abbr, rr in REFERENCE_RANGES.items()
        }

    def get_glossary(self) -> dict[str, str]:
        return LAB_GLOSSARY

    def get_prompt_context(self) -> dict:
        return {
            "specialty": "laboratory medicine",
            "test_type": "blood_lab_results",
            "guidelines": "Standard clinical laboratory reference ranges for adult patients",
            "explanation_style": (
                "Group related analytes (kidney: BUN+Creatinine+eGFR; "
                "liver: AST+ALT+ALP+Bilirubin; blood sugar: Glucose+HbA1c). "
                "Highlight abnormal values. For borderline values, note they may not "
                "be clinically significant. When multiple related values are abnormal, "
                "explain the pattern (e.g., low iron+low ferritin+high TIBC = iron deficiency)."
            ),
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"CHEMISTRY|CHEM\s+PANEL",
            r"HA?EMATOLOGY",
            r"(?:COMPLETE\s+)?(?:BLOOD\s+COUNT|HA?EMOGRAM)|CBC",
            r"(?:COMPREHENSIVE|BASIC)\s+METABOLIC\s+PANEL|CMP|BMP",
            r"LIPID\s+(?:PANEL|PROFILE)",
            r"THYROID\s+(?:PANEL|FUNCTION|STUDIES)",
            r"IRON\s+STUDIES|IRON\s+PANEL",
            r"LIVER\s+(?:FUNCTION|PANEL|ENZYMES)|HEPATIC\s+(?:FUNCTION|PANEL)",
            r"RENAL\s+(?:FUNCTION|PANEL)|KIDNEY\s+FUNCTION",
            r"URINALYSIS|UA\b",
            r"DIFFERENTIAL\s+LE[U]?COCYTE\s+COUNT",
            r"PERIPHERAL\s+SMEAR",
            r"COMMENT|INTERPRETATION|NOTE|CLINICAL\s+NOTE|IMPRESSION|ADVISED",
        ]

        combined = "|".join(f"({p})" for p in section_headers)
        header_re = re.compile(
            r"(?:^|\n)\s*(" + combined + r")\s*[:\-]?\s*",
            re.IGNORECASE | re.MULTILINE,
        )

        matches = list(header_re.finditer(text))
        sections: list[ReportSection] = []

        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_name = match.group(1).strip().rstrip(":-").strip()
            content = text[start:end].strip()
            if content:
                sections.append(
                    ReportSection(
                        name=section_name.upper(),
                        content=content,
                    )
                )

        return sections

    def _extract_findings(self, text: str) -> list[str]:
        """Extract comment/interpretation/note lines."""
        findings: list[str] = []
        findings_re = re.compile(
            r"(?:COMMENT|INTERPRETATION|NOTE|CLINICAL\s+NOTE|IMPRESSION|ADVISED)\s*[:\-]?\s*\n"
            r"([\s\S]*?)(?:\n\s*\n|\Z)",
            re.IGNORECASE,
        )
        for match in findings_re.finditer(text):
            block = match.group(1).strip()
            lines = re.split(r"\n\s*(?:\d+[\.\)]\s*|[-*]\s*)", block)
            for line in lines:
                line = line.strip()
                if line and len(line) > 10:
                    findings.append(line)

        return findings
