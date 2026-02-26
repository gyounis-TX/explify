from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType, split_text_zones, keyword_zone_weight
from .glossary import RHC_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


# ---------------------------------------------------------------------------
# RHC prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_RHC_STYLE = (
    "This is a right heart catheterization (RHC) study.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(PH screening -> PH classification -> PVR -> cardiac output -> RA pressure "
    "-> additional).\n"
    "At Grade 12 literacy: explain what each pressure measurement means in "
    "context. Define terms before using them (e.g., 'pulmonary vascular "
    "resistance, which measures how hard it is for blood to flow through "
    "the lungs...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Lead with the most clinically significant finding. If all "
    "pressures are normal, say so clearly and concisely up front."
)

_RHC_RULES = (
    "RIGHT HEART CATHETERIZATION — DECISION TREE:\n\n"
    "STEP 1 — PH SCREENING (always first):\n"
    "  - mPAP <20 mmHg = normal. Headline: 'No pulmonary hypertension.'\n"
    "  - mPAP 21-24 mmHg = borderline elevation. Note but do NOT diagnose PH.\n"
    "  - mPAP >=25 mmHg = pulmonary hypertension present.\n"
    "  - Note: ESC/ERS 2022 uses >20 mmHg threshold, but many labs still\n"
    "    report using >=25 mmHg. Acknowledge both if borderline.\n"
    "  - If mPAP is normal, keep the rest of the explanation concise.\n\n"
    "STEP 2 — PH CLASSIFICATION (only if PH present):\n"
    "  - PCWP <=15 + PVR >2 WU = pre-capillary PH (WHO Group 1, 3, 4, 5).\n"
    "  - PCWP >15 + PVR <=2 WU = isolated post-capillary PH (WHO Group 2).\n"
    "  - PCWP >15 + PVR >2 WU = combined pre- and post-capillary PH.\n"
    "  - TPG (mPAP - PCWP): <12 = passive, >=12 = reactive component.\n"
    "  - DPG (diastolic PA - PCWP): <7 = passive, >=7 = pulmonary\n"
    "    vascular disease component.\n"
    "  - Explain the classification in plain language: pre-capillary =\n"
    "    problem in the lung vessels themselves; post-capillary = back-pressure\n"
    "    from the left heart.\n\n"
    "STEP 3 — PVR (pulmonary vascular resistance):\n"
    "  - <2 WU = normal.\n"
    "  - 2-3 WU = mildly elevated.\n"
    "  - 3-5 WU = moderately elevated.\n"
    "  - >5 WU = severely elevated.\n"
    "  - Explain as the 'resistance' blood encounters flowing through the\n"
    "    lungs — like water flowing through pipes of different widths.\n\n"
    "STEP 4 — CARDIAC OUTPUT / INDEX:\n"
    "  - CI >=2.5 L/min/m² = normal.\n"
    "  - CI 2.0-2.5 = mildly reduced.\n"
    "  - CI <2.0 = low output state — significant.\n"
    "  - Note method (Fick vs thermodilution) if both are reported.\n"
    "  - Explain as how much blood the heart pumps per minute.\n\n"
    "STEP 5 — RA PRESSURE:\n"
    "  - 0-5 mmHg = normal.\n"
    "  - 6-10 mmHg = mildly elevated.\n"
    "  - >10 mmHg = significantly elevated (RV failure or volume overload).\n"
    "  - Elevated RA pressure = right heart struggling. Correlate with\n"
    "    clinical signs (edema, JVD).\n\n"
    "STEP 6 — ADDITIONAL FINDINGS:\n"
    "  - O2 saturations (step-up may suggest intracardiac shunt).\n"
    "  - Vasodilator challenge results (if performed for PAH evaluation).\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Dyspnea → elevated mPAP, elevated PCWP, reduced CI.\n"
    "  - Edema / ascites → elevated RA pressure, RV failure.\n"
    "  - Exercise intolerance → reduced CI, elevated PVR.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - Normal RHC: very reassuring — excludes pulmonary hypertension.\n"
    "  - Borderline mPAP 21-24: clinical significance uncertain — contextualize.\n\n"
    "GUARDRAILS:\n"
    "  - Normal RHC: keep concise. 'Normal right heart pressures and\n"
    "    cardiac output' is sufficient.\n"
    "  - Borderline mPAP (21-24): Do NOT diagnose pulmonary hypertension.\n"
    "    Say 'borderline elevation' and suggest clinical correlation.\n"
    "  - Elevated PCWP with normal mPAP: this is NOT pulmonary hypertension.\n"
    "    This is elevated left-sided filling pressure.\n"
    "  - Fick vs thermodilution discrepancy: note the difference but do NOT\n"
    "    pick a winner. Both methods have limitations.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class RightHeartCathHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "right_heart_cath"

    @property
    def display_name(self) -> str:
        return "Right Heart Catheterization"

    @property
    def keywords(self) -> list[str]:
        return [
            "right heart catheterization",
            "right heart cath",
            "swan-ganz",
            "swan ganz",
            "pulmonary artery catheterization",
            "pulmonary capillary wedge",
            "pcwp",
            "cardiac output",
            "cardiac index",
            "pulmonary vascular resistance",
            "pvr",
            "transpulmonary gradient",
            "fick",
            "thermodilution",
            "mixed venous",
            "pa pressure",
            "pulmonary artery pressure",
            "right atrial pressure",
            "wedge pressure",
            "mean pa",
            "diastolic pa",
            "systolic pa",
            "oxygen saturation",
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
            "right heart catheterization",
            "right heart cath",
            "swan-ganz",
            "swan ganz",
            "pulmonary artery catheterization",
        ]
        moderate_keywords = [
            "pulmonary capillary wedge",
            "pcwp",
            "cardiac output",
            "cardiac index",
            "pulmonary vascular resistance",
            "pvr",
            "transpulmonary gradient",
            "fick",
            "thermodilution",
            "mixed venous",
            "pa pressure",
            "pulmonary artery pressure",
            "right atrial pressure",
        ]
        weak_keywords = [
            "wedge pressure",
            "mean pa",
            "diastolic pa",
            "systolic pa",
            "oxygen saturation",
        ]

        # Left heart cath terms -- if these appear, this is likely a left
        # heart cath or coronary angiogram, not an isolated RHC.
        lhc_negatives = [
            "coronary angiogram",
            "coronary angiography",
            "lvedp",
            "ventriculogram",
            "pci",
            "stent",
        ]

        # Positional weighting: strong keywords in comparison-only don't
        # count as strong (e.g. "Comparison: Right heart cath on ...").
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

        # Only title/body strong keywords earn the 0.7 base
        if strong_title_or_body > 0:
            base = 0.7
        elif moderate_count >= 3:
            base = 0.4
        elif moderate_count >= 1:
            base = 0.2
        elif strong_comparison_only > 0:
            # "right heart cath" only in comparison -- very weak signal
            base = 0.15
        else:
            base = 0.0

        bonus = min(0.3, moderate_count * 0.05 + weak_count * 0.02)
        score = min(1.0, base + bonus)

        # LHC negative penalty -- only count LHC terms in title/body
        lhc_count = sum(1 for k in lhc_negatives
                        if keyword_zone_weight(k, title, comparison, body) >= 1.0)
        if lhc_count > 0:
            score *= max(0.0, 1.0 - lhc_count * 0.3)

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
        return RHC_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "cardiology/pulmonary",
            "test_type": "right_heart_catheterization",
            "category": "cardiac",
            "guidelines": "ESC/ERS 2022 Pulmonary Hypertension Guidelines",
            "explanation_style": _RHC_STYLE,
            "interpretation_rules": _RHC_RULES,
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"RIGHT\s+ATRIUM|RA\s+PRESSURE",
            r"PULMONARY\s+ARTERY|PA\s+PRESSURE",
            r"WEDGE|PCWP|PAWP",
            r"CARDIAC\s+OUTPUT",
            r"OXYGEN\s+SATURATION|O2\s+SAT",
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
