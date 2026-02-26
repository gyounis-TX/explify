from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType
from .glossary import ARTERIAL_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


# ---------------------------------------------------------------------------
# Arterial Doppler prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_ARTERIAL_DOPPLER_STYLE = (
    "This is a lower extremity arterial Doppler ultrasound.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(ABI -> waveform analysis -> vessel-by-vessel -> clinical correlation).\n"
    "At Grade 12 literacy: explain what each finding means in context. Define "
    "terms before using them (e.g., 'ankle-brachial index, which compares "
    "blood pressure in your ankle to your arm...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Lead with the most clinically significant finding. If ABI is "
    "normal and waveforms are triphasic, say so clearly and concisely."
)

_ARTERIAL_DOPPLER_RULES = (
    "LOWER EXTREMITY ARTERIAL DOPPLER — DECISION TREE:\n\n"
    "STEP 1 — ABI (Ankle-Brachial Index):\n"
    "  - >1.3 = non-compressible arteries (often diabetes or CKD). Cannot\n"
    "    rely on ABI alone — need TBI (toe-brachial index) for assessment.\n"
    "    Do NOT report >1.3 as 'normal.'\n"
    "  - 1.0-1.3 = normal.\n"
    "  - 0.91-0.99 = borderline. Do NOT diagnose PAD — say 'borderline'\n"
    "    and suggest clinical correlation.\n"
    "  - 0.70-0.90 = mild PAD.\n"
    "  - 0.40-0.69 = moderate PAD.\n"
    "  - <0.40 = severe / critical limb ischemia.\n"
    "  - Asymmetry: ABI difference >0.15 between legs suggests unilateral\n"
    "    disease — note which side is lower.\n\n"
    "STEP 2 — WAVEFORM ANALYSIS:\n"
    "  - Triphasic = normal arterial flow (forward-reverse-forward).\n"
    "  - Biphasic = mild arterial disease (loss of reverse component).\n"
    "  - Monophasic = significant arterial disease (continuous low-resistance\n"
    "    flow).\n"
    "  - The transition point from triphasic to monophasic helps localize\n"
    "    the level of disease.\n\n"
    "STEP 3 — VESSEL-BY-VESSEL:\n"
    "  - CFA (common femoral), SFA (superficial femoral), popliteal, tibial\n"
    "    vessels (ATA, PTA, peroneal).\n"
    "  - PSV ratio >2.0 across a lesion = >=50%% stenosis.\n"
    "  - Bypass graft patency if applicable (graft velocities, waveform\n"
    "    quality).\n"
    "  - Note occluded segments if present.\n\n"
    "STEP 4 — CLINICAL CORRELATION:\n"
    "  - Calf pain / claudication = SFA or popliteal disease.\n"
    "  - Thigh or buttock claudication = aortoiliac disease.\n"
    "  - Rest pain or tissue loss = critical limb ischemia.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Claudication (calf) → SFA / popliteal disease.\n"
    "  - Claudication (thigh/buttock) → aortoiliac disease.\n"
    "  - Rest pain → critical limb ischemia (ABI <0.40).\n"
    "  - Non-healing wound → distal perfusion assessment.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - Normal ABI + triphasic: very reassuring — no significant PAD.\n"
    "  - Mild PAD (ABI 0.70-0.90): commonly managed with exercise, risk factor\n"
    "    control, and monitoring.\n\n"
    "GUARDRAILS:\n"
    "  - Normal ABI + triphasic waveforms: keep concise. 'Normal arterial\n"
    "    blood flow to both legs' is sufficient.\n"
    "  - Borderline ABI (0.91-0.99): Do NOT diagnose PAD. 'Borderline'\n"
    "    with clinical correlation recommended.\n"
    "  - Non-compressible ABI (>1.3): Do NOT report as normal. Explain\n"
    "    that the arteries are calcified and ABI may underestimate disease.\n"
    "  - Mild PAD without symptoms: contextualize. Many patients with\n"
    "    mild PAD are asymptomatic and managed with risk factor control.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class ArterialDopplerHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "arterial_doppler"

    @property
    def display_name(self) -> str:
        return "Lower Extremity Arterial Ultrasound"

    @property
    def keywords(self) -> list[str]:
        return [
            "arterial ultrasound",
            "arterial doppler",
            "lower extremity arterial",
            "ankle-brachial index",
            "abi",
            "claudication",
            "peripheral arterial",
            "pad",
            "femoral artery",
            "popliteal",
            "triphasic",
            "biphasic",
            "monophasic",
            "cfa",
            "pfa",
            "pta",
            "pop a",
        ]

    @property
    def category(self) -> str:
        return "vascular"

    def detect(self, extraction_result: ExtractionResult) -> float:
        text = extraction_result.full_text.lower()

        strong_keywords = [
            "lower extremity arterial ultrasound",
            "lower extremity arterial",
            "arterial doppler",
            "arterial ultrasound report",
        ]
        moderate_keywords = [
            "ankle-brachial index",
            "ankle brachial index",
            "claudication",
            "peripheral arterial",
            "triphasic",
            "biphasic",
            "monophasic",
            "cfa",
            "pfa",
            "prox femoral",
            "mid femoral",
            "dist femoral",
            "pop a",
            "popliteal artery",
        ]
        weak_keywords = [
            "femoral",
            "artery",
            "arterial",
            "patent",
            "velocity",
            "waveform",
            "lumen",
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
        return ARTERIAL_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "vascular medicine / cardiology",
            "test_type": "lower_extremity_arterial",
            "category": "vascular",
            "guidelines": "ACC/AHA 2016 PAD Guidelines",
            "explanation_style": _ARTERIAL_DOPPLER_STYLE,
            "interpretation_rules": _ARTERIAL_DOPPLER_RULES,
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        section_headers = [
            r"RIGHT\s+(?:LEG|LOWER\s+EXTREMITY)",
            r"LEFT\s+(?:LEG|LOWER\s+EXTREMITY)",
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
            r"(?:CONCLUSION[S]?|IMPRESSION[S]?|SUMMARY|FINDINGS|INTERPRETATION)"
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
