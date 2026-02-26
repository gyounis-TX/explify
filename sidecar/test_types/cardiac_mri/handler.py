from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType, split_text_zones, keyword_zone_weight
from .glossary import CMR_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


# ---------------------------------------------------------------------------
# CMR prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_CMR_STYLE = (
    "This is a cardiac MRI (CMR) study.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(scar/LGE -> biventricular function -> tissue mapping -> perfusion -> additional).\n"
    "At Grade 12 literacy: explain what each finding means in context. Define "
    "terms before using them (e.g., 'late gadolinium enhancement, which highlights "
    "areas of scar tissue in the heart muscle...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Lead with the most clinically significant finding. Scar pattern "
    "and extent are the headline findings on CMR."
)

_CMR_RULES = (
    "CARDIAC MRI — DECISION TREE:\n\n"
    "STEP 1 — LGE / SCAR (always first — most important CMR finding):\n"
    "  - Pattern is critical:\n"
    "    * Ischemic = subendocardial or transmural in a coronary territory.\n"
    "    * Non-ischemic = mid-wall, epicardial, or patchy (not following a\n"
    "      coronary distribution).\n"
    "    * Myocarditis = subepicardial, typically inferolateral.\n"
    "    * Amyloid = diffuse subendocardial enhancement.\n"
    "  - Scar burden: >15%% of LV mass is extensive.\n"
    "  - Transmurality: <50%% = viable myocardium (may recover with\n"
    "    revascularization); >50%% = non-viable (unlikely to recover).\n"
    "  - No LGE = no scar. State clearly and move on.\n\n"
    "STEP 2 — BIVENTRICULAR FUNCTION:\n"
    "  - LVEF: normal >=57%% male, >=61%% female by CMR (higher than echo\n"
    "    norms). Report with severity classification.\n"
    "  - LV volumes (EDV, ESV) and LV mass: note if dilated or hypertrophied.\n"
    "  - RVEF: >=45%% normal. RV volumes.\n"
    "  - Wall motion abnormalities: correlate with scar distribution from Step 1.\n\n"
    "STEP 3 — TISSUE MAPPING:\n"
    "  - T2: elevated = active edema/inflammation (acute process vs chronic).\n"
    "    Helps distinguish acute myocarditis or infarction from chronic scar.\n"
    "  - T1: elevated = fibrosis or infiltration; low = Fabry disease or iron\n"
    "    overload.\n"
    "  - ECV: normal ~25-30%%. Elevated = diffuse fibrosis. >40%% suggests\n"
    "    amyloidosis. Provides information about tissue between cells.\n"
    "  - If no mapping data in report, skip this step.\n\n"
    "STEP 4 — PERFUSION (stress CMR only):\n"
    "  - Reversible perfusion defect = ischemia. State territory and extent.\n"
    "  - Fixed perfusion defect = scar (correlate with LGE).\n"
    "  - If no stress perfusion was performed, skip this step.\n\n"
    "STEP 5 — ADDITIONAL FINDINGS:\n"
    "  - LA size, valvular function, pericardium, extracardiac findings.\n"
    "  - Note only if abnormal or clinically relevant.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Chest pain → scar pattern (ischemic vs non-ischemic), perfusion defects.\n"
    "  - Heart failure / dyspnea → reduced EF, elevated ECV, scar burden.\n"
    "  - Palpitations / arrhythmia → scar substrate (mid-wall fibrosis).\n"
    "  - Myocarditis symptoms → T2 edema + subepicardial LGE pattern.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - No scar + normal function: very reassuring.\n"
    "  - Ischemic scar <50%% transmural: viable — may benefit from treatment.\n"
    "  - RV insertion point LGE alone: benign in ~10%% of normal CMRs.\n\n"
    "GUARDRAILS:\n"
    "  - RV insertion point LGE alone is a common, benign finding — do NOT\n"
    "    alarm. It is seen at the junction of the RV and LV and is usually\n"
    "    of no clinical significance.\n"
    "  - LVEF above normal range: Do NOT flag. CMR EF norms are higher than\n"
    "    echo norms. An EF of 65-75%% is normal on CMR.\n"
    "  - Mild T1 elevation without LGE or T2 changes: do NOT over-interpret.\n"
    "    Isolated mild T1 changes can be non-specific.\n"
    "  - Normal CMR: keep concise. 'No scar, normal heart function, and\n"
    "    normal tissue characterization' is sufficient.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class CardiacMRIHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "cardiac_mri"

    @property
    def display_name(self) -> str:
        return "Cardiac MRI"

    @property
    def keywords(self) -> list[str]:
        return [
            "cardiac mri",
            "cardiac magnetic resonance",
            "cmr",
            "mr cardiac",
            "mri cardiac",
            "cine imaging",
            "late gadolinium enhancement",
            "lge",
            "t1 mapping",
            "t2 mapping",
            "myocardial perfusion mri",
            "delayed enhancement",
            "gadolinium",
            "t2 stir",
            "strain imaging",
            "native t1",
            "extracellular volume",
            "ecv",
            "myocardial fibrosis",
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
            "cardiac mri",
            "cardiac magnetic resonance",
            "cmr",
            "mr cardiac",
            "mri cardiac",
            "cardiac magnetic resonance imaging",
        ]
        moderate_keywords = [
            "late gadolinium enhancement",
            "lge",
            "t1 mapping",
            "t2 mapping",
            "cine imaging",
            "delayed enhancement",
            "native t1",
            "extracellular volume",
            "strain imaging",
            "myocardial perfusion",
        ]
        weak_keywords = [
            "gadolinium",
            "t2 stir",
            "myocardial fibrosis",
            "scar burden",
            "edema",
        ]

        # Echo-specific terms -- if these appear in title/body, this is likely
        # an echocardiogram, not a cardiac MRI.
        echo_negatives = [
            "echocardiogram",
            "echocardiography",
            "transthoracic",
            "2d echo",
            "doppler",
        ]

        # Positional weighting: strong keywords in comparison-only don't
        # count as strong (e.g. "Comparison: Cardiac MRI on ...").
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
            # "cardiac mri" only in comparison -- very weak signal
            base = 0.15
        else:
            base = 0.0

        bonus = min(0.3, moderate_count * 0.05 + weak_count * 0.02)
        score = min(1.0, base + bonus)

        # Echo negative penalty -- only count echo terms in title/body
        echo_count = sum(1 for k in echo_negatives
                         if keyword_zone_weight(k, title, comparison, body) >= 1.0)
        if echo_count > 0:
            score *= max(0.0, 1.0 - echo_count * 0.3)

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
        return CMR_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "cardiology",
            "test_type": "cardiac_mri",
            "category": "cardiac",
            "guidelines": "SCMR 2020 Standardized CMR Protocols",
            "explanation_style": _CMR_STYLE,
            "interpretation_rules": _CMR_RULES,
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"LEFT\s+VENTRICLE|LV\s+(?:FUNCTION|DIMENSIONS?|VOLUMES?)",
            r"RIGHT\s+VENTRICLE|RV\s+(?:FUNCTION|VOLUMES?)",
            r"LEFT\s+ATRIUM|LA\b",
            r"RIGHT\s+ATRIUM|RA\b",
            r"TISSUE\s+CHARACTERIZATION",
            r"LATE\s+GADOLINIUM\s+ENHANCEMENT|LGE",
            r"T1\s+MAPPING|NATIVE\s+T1",
            r"T2\s+MAPPING",
            r"PERFUSION",
            r"CINE\s+IMAGING",
            r"VALV(?:E|ULAR)\s+(?:FUNCTION|ASSESSMENT)",
            r"AORT(?:A|IC)",
            r"PERICARDI(?:UM|AL)",
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
