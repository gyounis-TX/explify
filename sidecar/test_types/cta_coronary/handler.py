from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType, split_text_zones, keyword_zone_weight
from .glossary import CTA_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


# ---------------------------------------------------------------------------
# CTA Coronary prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_CTA_CORONARY_STYLE = (
    "This is a coronary CT angiography (CTA) study.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(calcium score -> vessel-by-vessel stenosis -> CAD-RADS -> CT-FFR -> secondary).\n"
    "At Grade 12 literacy: explain what each finding means in context. Define "
    "terms before using them (e.g., 'calcium score, which measures mineral "
    "buildup in the coronary arteries...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Lead with the most clinically significant finding. If calcium "
    "score is zero and no stenosis, say so clearly and concisely up front."
)

_CTA_CORONARY_RULES = (
    "CTA CORONARY — DECISION TREE:\n\n"
    "STEP 1 — CALCIUM SCORE:\n"
    "  - Agatston score + age/sex percentile if available.\n"
    "  - Categories: 0 = no coronary calcium (very reassuring); 1-10 = minimal;\n"
    "    11-100 = mild; 101-400 = moderate; >400 = severe.\n"
    "  - Percentile contextualizes by age and sex (e.g., a score of 150 at\n"
    "    age 45 is more significant than at age 75).\n"
    "  - CAC 0: extremely reassuring. Do NOT pad with caveats.\n\n"
    "STEP 2 — VESSEL-BY-VESSEL STENOSIS:\n"
    "  - Evaluate: Left Main (LM), LAD, LCx, RCA (and branches if reported).\n"
    "  - Severity: none / minimal (1-24%%) / mild (25-49%%) / moderate\n"
    "    (50-69%%) / severe (70-99%%) / occluded (100%%).\n"
    "  - Plaque type: calcified (stable) / non-calcified (softer) / mixed.\n"
    "  - High-risk plaque features: positive remodeling, low-attenuation\n"
    "    plaque, napkin-ring sign, spotty calcification.\n"
    "  - LM >=50%% is ALWAYS hemodynamically significant.\n\n"
    "STEP 3 — CAD-RADS CLASSIFICATION:\n"
    "  - CAD-RADS 0: no plaque or stenosis.\n"
    "  - CAD-RADS 1: 1-24%% minimal stenosis or plaque.\n"
    "  - CAD-RADS 2: 25-49%% mild stenosis.\n"
    "  - CAD-RADS 3: 50-69%% moderate stenosis.\n"
    "  - CAD-RADS 4A: 70-99%% severe stenosis (one or two vessels).\n"
    "  - CAD-RADS 4B: left main >=50%% or three-vessel >=70%%.\n"
    "  - CAD-RADS 5: total occlusion.\n"
    "  - Modifiers: /S = stent present, /G = graft present.\n"
    "  - Explain the CAD-RADS grade in patient-friendly language.\n\n"
    "STEP 4 — CT-FFR (if available):\n"
    "  - CT-FFR >0.80 = not hemodynamically significant.\n"
    "  - CT-FFR <=0.80 = hemodynamically significant stenosis.\n"
    "  - Explain as a 'virtual stress test' that estimates whether a\n"
    "    narrowing is actually affecting blood flow.\n"
    "  - If no CT-FFR data, skip this step.\n\n"
    "STEP 5 — SECONDARY FINDINGS:\n"
    "  - LVEF from gated CT (if available).\n"
    "  - Extracardiac findings (lung nodules, pleural effusions, etc.).\n"
    "  - Aortic or valvular calcification.\n"
    "  - Note only if abnormal or clinically relevant.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Chest pain → stenosis severity, plaque characteristics.\n"
    "  - Dyspnea → LV function on gated CT, significant stenosis.\n"
    "  - Risk factor screening → calcium score percentile for age/sex.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - CAC 0: <1%% chance of significant stenosis.\n"
    "  - CAD-RADS 0-1: very low risk — routine follow-up.\n"
    "  - CAD-RADS 2: low risk — risk factor management.\n\n"
    "GUARDRAILS:\n"
    "  - CAC 0: Do NOT pad with unnecessary caveats. A zero calcium score\n"
    "    is very reassuring and should be communicated as such.\n"
    "  - CAD-RADS 1-2: Do NOT alarm. Minimal-to-mild plaque is common\n"
    "    and does not require intervention.\n"
    "  - Non-calcified plaque: Do NOT catastrophize. Note it is 'softer'\n"
    "    plaque but avoid implying imminent danger.\n"
    "  - High CAC in elderly patients: contextualize with age. A score of\n"
    "    300 at age 80 is less alarming than at age 50.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class CTACoronaryHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "cta_coronary"

    @property
    def display_name(self) -> str:
        return "CTA Coronary"

    @property
    def keywords(self) -> list[str]:
        return [
            "cta coronary",
            "coronary cta",
            "ct coronary angiography",
            "coronary ct angiography",
            "cardiac ct angiography",
            "ccta",
            "calcium score",
            "agatston",
            "coronary artery calcium",
            "cac score",
            "coronary stenosis",
            "plaque burden",
            "coronary arteries",
            "left main",
            "lad",
            "lcx",
            "rca",
            "ct fractional flow reserve",
            "ct-ffr",
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
            "cta coronary",
            "coronary cta",
            "ct coronary angiography",
            "coronary ct angiography",
            "cardiac ct angiography",
            "ccta",
        ]
        moderate_keywords = [
            "calcium score",
            "agatston",
            "coronary artery calcium",
            "cac score",
            "heart scan",
            "coronary stenosis",
            "plaque burden",
            "coronary arteries",
            "left main",
            "lad",
            "lcx",
            "rca",
            "ct fractional flow reserve",
            "ct-ffr",
        ]
        weak_keywords = [
            "contrast enhanced",
            "gated ct",
            "prospective gating",
            "retrospective gating",
            "coronary",
            "stenosis",
            "plaque",
        ]

        # Negative keywords -- if these appear in title/body this is likely
        # a different cardiac study, not a CTA coronary.
        negative_keywords = [
            "cardiac mri",
            "echocardiogram",
            "catheterization",
            "angiogram",
        ]

        # Positional weighting: strong keywords in comparison-only don't
        # count as strong (e.g. "Comparison: CTA Coronary on ...").
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
            # "cta coronary" only in comparison -- very weak signal
            base = 0.15
        else:
            base = 0.0

        bonus = min(0.3, moderate_count * 0.05 + weak_count * 0.02)
        score = min(1.0, base + bonus)

        # Negative penalty -- only count negative terms in title/body
        neg_count = sum(1 for k in negative_keywords
                        if keyword_zone_weight(k, title, comparison, body) >= 1.0)
        if neg_count > 0:
            score *= max(0.0, 1.0 - neg_count * 0.3)

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
        return CTA_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "cardiology",
            "test_type": "cta_coronary",
            "category": "cardiac",
            "guidelines": "SCCT 2022 Guidelines for Coronary CTA",
            "explanation_style": _CTA_CORONARY_STYLE,
            "interpretation_rules": _CTA_CORONARY_RULES,
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"CALCIUM\s+SCORE|CAC",
            r"LEFT\s+MAIN|LM\b",
            r"LEFT\s+ANTERIOR\s+DESCENDING|LAD\b",
            r"LEFT\s+CIRCUMFLEX|LCX\b|LCx\b",
            r"RIGHT\s+CORONARY|RCA\b",
            r"BYPASS\s+GRAFT",
            r"NON[- ]?CORONARY|EXTRACARDIAC",
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
