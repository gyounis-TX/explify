from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType
from .glossary import CAROTID_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


# ---------------------------------------------------------------------------
# Carotid Doppler prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_CAROTID_DOPPLER_STYLE = (
    "This is a carotid Doppler ultrasound.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(stenosis grading -> velocity details -> plaque characteristics -> "
    "vertebral arteries -> IMT).\n"
    "At Grade 12 literacy: explain what each finding means in context. Define "
    "terms before using them (e.g., 'peak systolic velocity, which measures "
    "how fast blood flows through the artery...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Lead with the most clinically significant finding. If no "
    "significant stenosis, say so clearly and concisely up front."
)

_CAROTID_DOPPLER_RULES = (
    "CAROTID DOPPLER — DECISION TREE:\n\n"
    "STEP 1 — STENOSIS GRADING (SRU Consensus Criteria):\n"
    "  - Normal: ICA PSV <125 cm/s, no plaque.\n"
    "  - <50%% stenosis: ICA PSV <125 cm/s with visible plaque.\n"
    "  - 50-69%% stenosis: ICA PSV 125-230 cm/s, ICA/CCA ratio 2.0-4.0.\n"
    "  - >=70%% stenosis: ICA PSV >230 cm/s, ICA/CCA ratio >4.0.\n"
    "  - Near-occlusion: variable PSV (may be high or paradoxically low),\n"
    "    visible narrowing on B-mode.\n"
    "  - Total occlusion: no detectable flow.\n"
    "  - Grade each side (right and left) separately.\n\n"
    "STEP 2 — VELOCITY DETAILS:\n"
    "  - Report ICA PSV, ICA EDV, and ICA/CCA ratio for each side.\n"
    "  - Higher velocity = more stenosis (blood speeds up through a\n"
    "    narrower opening).\n"
    "  - Note which side has higher velocities / more disease.\n\n"
    "STEP 3 — PLAQUE CHARACTERISTICS:\n"
    "  - Calcified plaque: echogenic, stable, lower embolic risk.\n"
    "  - Soft / hypoechoic plaque: more vulnerable, higher embolic risk.\n"
    "  - Ulcerated plaque: irregular surface, embolic risk.\n"
    "  - Heterogeneous plaque: mixed composition.\n"
    "  - Note plaque characteristics only if described in the report.\n\n"
    "STEP 4 — VERTEBRAL ARTERIES:\n"
    "  - Antegrade flow = normal direction.\n"
    "  - Retrograde flow = subclavian steal physiology (blood flowing\n"
    "    backward due to subclavian artery stenosis).\n"
    "  - Note if vertebral arteries are not well visualized.\n\n"
    "STEP 5 — IMT (Intima-Media Thickness, if reported):\n"
    "  - >1.0 mm = abnormal, marker of arterial aging and atherosclerosis.\n"
    "  - If not reported, skip this step.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Stroke / TIA → stenosis severity is the key finding.\n"
    "  - Bruit → correlate with stenosis grade.\n"
    "  - Dizziness → vertebral artery flow direction.\n"
    "  - Screening (asymptomatic) → percentile context for age.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - <50%% stenosis asymptomatic: very low annual stroke risk (~1%%).\n"
    "  - 50-69%% asymptomatic: ~1-2%% annual stroke risk.\n"
    "  - >=70%% asymptomatic: ~2-5%% annual stroke risk without treatment.\n\n"
    "GUARDRAILS:\n"
    "  - Normal carotid ultrasound: keep concise. 'No significant carotid\n"
    "    stenosis on either side' is sufficient.\n"
    "  - <50%% stenosis: Do NOT alarm. Mild plaque without significant\n"
    "    narrowing is very common — found in ~40%% of adults over 60.\n"
    "  - 50-69%% stenosis: significant finding but NOT an emergency.\n"
    "    Frame as 'moderate narrowing that we'll want to\n"
    "    monitor and manage.'\n"
    "  - >=70%% stenosis: important finding. Communicate clearly but\n"
    "    do NOT catastrophize. Frame as 'significant narrowing that\n"
    "    we'll want to discuss treatment options for.'\n"
    "  - Asymmetric findings: note which side is worse.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class CarotidDopplerHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "carotid_doppler"

    @property
    def display_name(self) -> str:
        return "Carotid Doppler Ultrasound"

    @property
    def keywords(self) -> list[str]:
        return [
            "carotid",
            "carotid doppler",
            "carotid ultrasound",
            "carotid duplex",
            "cerebrovascular duplex",
            "carotid artery",
            "internal carotid",
            "common carotid",
            "ica/cca",
            "peak systolic velocity",
            "psv",
            "end diastolic velocity",
            "edv",
            "vertebral artery",
            "stenosis",
            "plaque",
            "intima-media",
        ]

    @property
    def category(self) -> str:
        return "vascular"

    def detect(self, extraction_result: ExtractionResult) -> float:
        """Keyword-based detection with tiered scoring."""
        text = extraction_result.full_text.lower()

        strong_keywords = [
            "carotid doppler",
            "carotid duplex",
            "carotid ultrasound",
            "cerebrovascular duplex",
            "carotid artery duplex",
            "carotid artery ultrasound",
        ]
        moderate_keywords = [
            "internal carotid",
            "common carotid",
            "ica/cca",
            "ica/cca velocity ratio",
            "peak systolic velocity",
            "end diastolic velocity",
            "vertebral artery",
            "carotid stenosis",
            "carotid plaque",
            "prox ica",
            "mid ica",
            "dist ica",
            "dist cca",
        ]
        weak_keywords = [
            "carotid",
            "stenosis",
            "plaque",
            "psv",
            "edv",
            "antegrade flow",
            "patent",
        ]

        strong_count = sum(1 for k in strong_keywords if k in text)
        moderate_count = sum(1 for k in moderate_keywords if k in text)
        weak_count = sum(1 for k in weak_keywords if k in text)

        if strong_count > 0:
            base = 0.8
        elif moderate_count >= 3:
            base = 0.5
        elif moderate_count >= 1:
            base = 0.3
        else:
            base = 0.0

        bonus = min(0.2, moderate_count * 0.05 + weak_count * 0.02)
        return min(1.0, base + bonus)

    def parse(
        self,
        extraction_result: ExtractionResult,
        gender: str | None = None,
        age: int | None = None,
    ) -> ParsedReport:
        """Extract structured measurements, sections, and findings."""
        text = extraction_result.full_text
        warnings: list[str] = []

        raw_measurements = extract_measurements(text, extraction_result.pages)

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
        return CAROTID_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "vascular medicine / cardiology",
            "test_type": "carotid_doppler",
            "category": "vascular",
            "guidelines": "SRU Consensus Criteria for Carotid Stenosis",
            "explanation_style": _CAROTID_DOPPLER_STYLE,
            "interpretation_rules": _CAROTID_DOPPLER_RULES,
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"RIGHT\s+CAROTID",
            r"LEFT\s+CAROTID",
            r"RIGHT\s+VERTEBRAL",
            r"LEFT\s+VERTEBRAL",
            r"VERTEBRAL\s+ARTER(?:Y|IES)",
            r"FINDINGS?",
            r"IMPRESSION[S]?|CONCLUSION[S]?|INTERPRETATION|SUMMARY",
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
        """Extract conclusion/impression/findings lines."""
        findings: list[str] = []
        findings_re = re.compile(
            r"(?:CONCLUSION[S]?|IMPRESSION[S]?|SUMMARY|FINDINGS|INTERPRETATION)"
            r"\s*[:\-]?\s*\n"
            r"([\s\S]*?)(?:\n\s*\n|\Z)",
            re.IGNORECASE,
        )
        for match in findings_re.finditer(text):
            block = match.group(1).strip()
            lines = re.split(r"\n\s*(?:\d+[\.\)]\s*|[-*\u2022]\s*)", block)
            for line in lines:
                line = line.strip()
                if line and len(line) > 10:
                    findings.append(line)

        return findings
