from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType, split_text_zones, keyword_zone_weight
from .glossary import TEE_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement

# ---------------------------------------------------------------------------
# TEE prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_TEE_STYLE = (
    "This is a transesophageal echocardiogram (TEE).\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by indication,\n"
    "then LAA, septum, valves, aorta, other findings.\n"
    "At Grade 12 literacy: explain what each finding means in context. Define\n"
    "terms before using them.\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very\n"
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Lead with findings relevant to the indication."
)

_TEE_RULES = (
    "TRANSESOPHAGEAL ECHOCARDIOGRAM — DECISION TREE:\n\n"
    "STEP 1 — INDICATION-DRIVEN PRIMARY ASSESSMENT:\n"
    "  - Identify the indication (pre-op, stroke workup, endocarditis,\n"
    "    valve assessment, AF/cardioversion) and LEAD with findings relevant\n"
    "    to that indication.\n"
    "  - Stroke workup -> PFO/ASD and LAA thrombus are the headline findings.\n"
    "  - Endocarditis -> vegetation presence/absence is the headline.\n"
    "  - Pre-op valve -> valve anatomy and severity are the headline.\n"
    "  - AF/cardioversion -> LAA thrombus and SEC (smoke) are the headline.\n\n"
    "STEP 2 — LEFT ATRIAL APPENDAGE (LAA):\n"
    "  - Thrombus: present or absent. If absent, state clearly.\n"
    "  - Emptying velocity: >=40 cm/s normal, <40 cm/s sluggish flow\n"
    "    (increased thrombus risk).\n"
    "  - Spontaneous echo contrast (SEC/'smoke'): if present, note as\n"
    "    marker of sluggish flow.\n\n"
    "STEP 3 — INTERATRIAL SEPTUM:\n"
    "  - PFO: if bubble study performed, state result (positive/negative\n"
    "    for right-to-left shunt).\n"
    "  - ASD: if present, note type and size.\n"
    "  - Intact septum: state clearly.\n\n"
    "STEP 4 — VALVE ASSESSMENT:\n"
    "  - Detailed valve morphology (TEE provides superior views).\n"
    "  - Regurgitation severity with mechanism if visible.\n"
    "  - Prosthetic valve function if applicable (paravalvular leak,\n"
    "    gradient, effective orifice area).\n\n"
    "STEP 5 — AORTA:\n"
    "  - Atheroma: grade (I-V) if present. Grade IV-V (mobile/protruding\n"
    "    components) is significant for stroke risk.\n"
    "  - Ascending aorta size.\n\n"
    "STEP 6 — OTHER FINDINGS:\n"
    "  - Pericardial effusion, masses, other incidental findings.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Stroke/TIA → LAA thrombus, PFO, aortic atheroma grade IV-V.\n"
    "  - AF/cardioversion → LAA thrombus, SEC/smoke.\n"
    "  - Murmur evaluation → detailed valve morphology, regurgitation severity.\n"
    "  - Endocarditis → vegetation presence/absence, abscess, fistula.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "GUARDRAILS:\n"
    "  - TEE is semi-invasive — patients may be anxious. Acknowledge\n"
    "    normal findings with clear reassurance.\n"
    "  - Negative stroke workup (no PFO, no thrombus, no significant\n"
    "    atheroma): frame as clearly reassuring.\n"
    "  - Do NOT restate indications or mention who read the study.\n"
    "  - LVEF above normal range: Do NOT flag, caution, or comment on an EF\n"
    "    above the upper limit of normal. An EF of 65-75%% is not clinically\n"
    "    concerning and should simply be stated as normal. Do NOT use terms\n"
    "    like 'above normal', 'supranormal', or 'hyperdynamic' UNLESS the\n"
    "    report specifically raises concern for HCM.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class TEEHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "tee"

    @property
    def display_name(self) -> str:
        return "Transesophageal Echocardiogram"

    @property
    def keywords(self) -> list[str]:
        return [
            "transesophageal echocardiogram",
            "transesophageal echocardiography",
            "tee",
            "trans-esophageal",
            "tee study",
            "esophageal probe",
            "midesophageal",
            "mid-esophageal",
            "transgastric",
            "bicaval",
            "left atrial appendage",
            "laa",
            "interatrial septum",
            "patent foramen ovale",
            "pfo",
            "atrial septal defect",
            "asd",
            "aortic atheroma",
        ]

    @property
    def category(self) -> str:
        return "cardiac"

    def detect(self, extraction_result: ExtractionResult) -> float:
        """Keyword-based detection with tiered scoring and positional weighting.

        Keywords in the report title/header count more than keywords in the
        comparison section (which may reference a different modality).
        """
        title, comparison, body = split_text_zones(extraction_result.full_text)

        strong_keywords = [
            "transesophageal echocardiogram",
            "transesophageal echocardiography",
            "tee",
            "trans-esophageal",
            "tee study",
        ]
        moderate_keywords = [
            "esophageal probe",
            "midesophageal",
            "mid-esophageal",
            "transgastric",
            "bicaval",
            "left atrial appendage",
            "laa",
            "laa thrombus",
            "interatrial septum",
            "patent foramen ovale",
            "pfo",
            "atrial septal defect",
            "asd",
            "aortic atheroma",
            "mitral valve",
            "aortic valve",
        ]
        weak_keywords = [
            "3d reconstruction",
            "biplane",
            "deep transgastric",
            "appendage velocities",
        ]

        # TTE-specific terms -- if these appear in title/body, this is likely
        # a transthoracic echo, not a TEE.
        tte_negatives = [
            "transthoracic",
            "parasternal",
            "apical view",
            "subcostal",
        ]

        # Positional weighting: strong keywords in comparison-only don't
        # count as strong (e.g. "Comparison: TEE on ...").
        strong_title_or_body = 0
        strong_comparison_only = 0
        for k in strong_keywords:
            w = keyword_zone_weight(k, title, comparison, body)
            if w >= 1.0:
                strong_title_or_body += 1
            elif w > 0:
                strong_comparison_only += 1

        moderate_count = sum(1 for k in moderate_keywords
                            if keyword_zone_weight(k, title, comparison, body) >= 1.0)
        weak_count = sum(1 for k in weak_keywords
                         if keyword_zone_weight(k, title, comparison, body) >= 1.0)

        # Only title/body strong keywords earn the 0.8 base
        if strong_title_or_body > 0:
            base = 0.8
        elif moderate_count >= 3:
            base = 0.4
        elif moderate_count >= 1:
            base = 0.2
        elif strong_comparison_only > 0:
            # "tee" only in comparison -- very weak signal
            base = 0.15
        else:
            base = 0.0

        bonus = min(0.2, moderate_count * 0.05 + weak_count * 0.02)
        score = min(1.0, base + bonus)

        # TTE negative penalty -- only count TTE terms in title/body
        tte_count = sum(1 for k in tte_negatives
                        if keyword_zone_weight(k, title, comparison, body) >= 1.0)
        if tte_count > 0:
            score *= max(0.0, 1.0 - tte_count * 0.3)

        return score

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
            classification = classify_measurement(m.abbreviation, m.value, gender)
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
        return TEE_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "cardiology",
            "test_type": "transesophageal echocardiogram",
            "category": "cardiac",
            "guidelines": "ASE/SCA 2013 TEE Guidelines",
            "explanation_style": _TEE_STYLE,
            "interpretation_rules": _TEE_RULES,
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"LEFT\s+ATRIAL\s+APPENDAGE|LAA",
            r"INTERATRIAL\s+SEPTUM|IAS|PFO|ASD",
            r"MITRAL\s+VALVE",
            r"AORTIC\s+VALVE",
            r"TRICUSPID\s+VALVE",
            r"AORTA|ASCENDING\s+AORTA|DESCENDING\s+AORTA",
            r"PROSTHETIC\s+VALVE",
            r"ENDOCARDITIS|VEGETATION",
            r"CONCLUSION|IMPRESSION|SUMMARY|FINDINGS",
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
        """Extract conclusion/findings/impression lines."""
        findings: list[str] = []
        findings_re = re.compile(
            r"(?:CONCLUSION|IMPRESSION|SUMMARY|FINDINGS)\s*[:\-]?\s*\n"
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
