from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType
from .glossary import VENOUS_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


# ---------------------------------------------------------------------------
# Venous Duplex prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_VENOUS_DUPLEX_STYLE = (
    "This is a lower extremity venous duplex ultrasound.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(DVT assessment -> reflux/insufficiency -> vein mapping -> bilateral "
    "comparison).\n"
    "At Grade 12 literacy: explain what each finding means in context. Define "
    "terms before using them (e.g., 'deep vein thrombosis, which is a blood "
    "clot in the deep veins of the leg...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: DVT assessment is the headline finding. If no DVT and no "
    "significant reflux, say so clearly and concisely up front."
)

_VENOUS_DUPLEX_RULES = (
    "VENOUS DUPLEX — DECISION TREE:\n\n"
    "STEP 1 — DVT ASSESSMENT (always first — most urgent finding):\n"
    "  - Primary criterion: compressibility. Non-compressible vein = DVT.\n"
    "  - Acute DVT: distended vein, hypoechoic (dark) thrombus,\n"
    "    non-compressible.\n"
    "  - Chronic DVT: echogenic (bright) thrombus, thickened vein walls,\n"
    "    collateral vessels may be present.\n"
    "  - Proximal DVT (popliteal vein and above — CFV, femoral vein,\n"
    "    popliteal): HIGH risk of pulmonary embolism.\n"
    "  - Distal DVT (calf veins below popliteal — peroneal, tibial,\n"
    "    gastrocnemius, soleal): lower PE risk but may propagate.\n"
    "  - Superficial thrombosis within 3 cm of the saphenofemoral\n"
    "    junction (SFJ) = risk of extension into the deep system.\n"
    "  - No DVT: state clearly and move on.\n\n"
    "STEP 2 — REFLUX / INSUFFICIENCY:\n"
    "  - Abnormal reflux: >0.5 seconds in superficial veins, >1.0 seconds\n"
    "    in deep veins.\n"
    "  - GSV (great saphenous vein) diameter >5-6 mm = dilated.\n"
    "  - Note which segments have reflux and the reflux duration.\n"
    "  - If no reflux testing was performed, skip this step.\n\n"
    "STEP 3 — VEIN MAPPING (if performed):\n"
    "  - GSV diameters at key points (SFJ, thigh, knee, calf).\n"
    "  - SFJ and SPJ (saphenopopliteal junction) competence.\n"
    "  - Perforator veins: note if incompetent.\n"
    "  - If no mapping data, skip this step.\n\n"
    "STEP 4 — BILATERAL COMPARISON:\n"
    "  - Compare findings between right and left legs.\n"
    "  - Note if disease is unilateral or bilateral.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Leg swelling → DVT assessment is primary.\n"
    "  - Leg pain → DVT if acute; reflux/insufficiency if chronic.\n"
    "  - Varicose veins → reflux pattern and GSV diameter.\n"
    "  - Post-thrombotic → chronic DVT changes, collaterals.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "GUARDRAILS:\n"
    "  - No DVT + no reflux: keep concise. 'No blood clots and normal\n"
    "    venous flow in both legs' is sufficient.\n"
    "  - Mild GSV reflux: Do NOT alarm. Mild saphenous reflux is found\n"
    "    in ~20%% of adults and is very common.\n"
    "  - Acute DVT: frame clearly and seriously but without panic.\n"
    "    'A blood clot was found — we'll discuss treatment\n"
    "    options with you.'\n"
    "  - Chronic DVT: distinguish from acute. 'Evidence of a previous\n"
    "    blood clot that has organized over time.'\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class VenousDopplerHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "venous_duplex"

    @property
    def display_name(self) -> str:
        return "Lower Extremity Venous Duplex Scan"

    @property
    def keywords(self) -> list[str]:
        return [
            "venous duplex",
            "venous ultrasound",
            "venous color duplex",
            "dvt",
            "deep vein thrombosis",
            "venous reflux",
            "saphenous vein",
            "gsv",
            "greater saphenous",
            "lesser saphenous",
            "compressibility",
            "augmentation",
            "reflux time",
            "93970",
            "93971",
        ]

    @property
    def category(self) -> str:
        return "vascular"

    def detect(self, extraction_result: ExtractionResult) -> float:
        text = extraction_result.full_text.lower()

        strong_keywords = [
            "venous color duplex",
            "venous duplex scan",
            "lower extremity venous",
            "venous ultrasound",
            "duplex scan of extremity veins",
        ]
        moderate_keywords = [
            "deep vein thrombosis",
            "dvt",
            "venous reflux",
            "greater saphenous vein",
            "gsv prox",
            "gsv mid",
            "gsv dist",
            "reflux time",
            "compressibility",
            "augmentation",
            "93970",
            "93971",
            "saphenous",
        ]
        weak_keywords = [
            "venous",
            "vein",
            "reflux",
            "phasic",
            "spontaneous flow",
            "compression",
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
        return VENOUS_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "vascular medicine / cardiology",
            "test_type": "venous_duplex",
            "category": "vascular",
            "guidelines": "SVS/AVF Clinical Practice Guidelines",
            "explanation_style": _VENOUS_DUPLEX_STYLE,
            "interpretation_rules": _VENOUS_DUPLEX_RULES,
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        section_headers = [
            r"(?:FINDINGS?:?\s*)?RIGHT\s+LEG",
            r"(?:FINDINGS?:?\s*)?LEFT\s+LEG",
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
                    ReportSection(name=section_name.upper(), content=content)
                )

        return sections

    def _extract_findings(self, text: str) -> list[str]:
        findings: list[str] = []
        findings_re = re.compile(
            r"(?:CONCLUSION[S]?|IMPRESSION[S]?|SUMMARY|INTERPRETATION)"
            r"\s*[:\-]?\s*\n([\s\S]*?)(?:\n\s*\n|\Z)",
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
