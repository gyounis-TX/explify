from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType
from .glossary import STRESS_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement

# Lazy import to avoid circular dependency at module level
_pet_extractor = None
_pet_ref_ranges = None
_pet_glossary = None


def _load_pet():
    global _pet_extractor, _pet_ref_ranges, _pet_glossary
    if _pet_extractor is None:
        from test_types.extractors.cardiac_pet import (
            extract_cardiac_pet_measurements,
            CARDIAC_PET_REFERENCE_RANGES,
            CARDIAC_PET_GLOSSARY,
        )
        _pet_extractor = extract_cardiac_pet_measurements
        _pet_ref_ranges = CARDIAC_PET_REFERENCE_RANGES
        _pet_glossary = CARDIAC_PET_GLOSSARY


# ---------------------------------------------------------------------------
# Subtype definitions
# ---------------------------------------------------------------------------
_SUBTYPES = {
    # (is_pharma, modality) -> (type_id, display_name)
    (False, "ecg"):   ("exercise_treadmill_test", "Exercise Treadmill Test"),
    (True,  "ecg"):   ("pharma_spect_stress", "Pharmacologic SPECT Nuclear Stress"),  # pharma without imaging → default to SPECT
    (True,  "spect"): ("pharma_spect_stress", "Pharmacologic SPECT Nuclear Stress"),
    (False, "spect"): ("exercise_spect_stress", "Exercise SPECT Nuclear Stress"),
    (True,  "pet"):   ("pharma_pet_stress", "Pharmacologic PET/PET-CT Stress"),
    (False, "pet"):   ("exercise_pet_stress", "Exercise PET/PET-CT Stress"),
    (False, "echo"):  ("exercise_stress_echo", "Exercise Stress Echocardiogram"),
    (True,  "echo"):  ("pharma_stress_echo", "Pharmacologic Stress Echocardiogram"),
}

# Pharmacologic agents (vasodilators + dobutamine)
_PHARMA_AGENTS = [
    "lexiscan", "regadenoson", "adenosine", "dipyridamole",
    "persantine", "dobutamine",
    "pharmacologic stress test", "pharmacological stress test",
    "pharmacologic stress was", "pharmacological stress was",
    "pharmacologic stress protocol",
]

# Modality keyword sets (checked in priority order: PET > SPECT > Echo > ECG)
_PET_KEYWORDS = [
    "pet/ct", "pet-ct", "pet ct", "rb-82", "rubidium",
    "n-13", "ammonia pet", "positron emission", "cardiac pet",
    "myocardial blood flow", "mbf", "coronary flow reserve", "cfr",
    "positron", "n-13 ammonia",
]

_SPECT_KEYWORDS = [
    "spect", "sestamibi", "technetium", "tc-99m", "myoview",
    "cardiolite", "thallium", "nuclear stress", "myocardial perfusion imaging",
    "nuclear cardiology", "mpi",
]

_ECHO_KEYWORDS = [
    "stress echo", "stress echocardiogram", "dobutamine echo",
    "dobutamine stress echo", "exercise echo", "bicycle stress",
    "wall motion at stress", "exercise echocardiogram",
    "treadmill echo", "dobutamine echocardiogram",
]


class StressTestHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "stress_test"

    @property
    def display_name(self) -> str:
        return "Stress Test"

    @property
    def keywords(self) -> list[str]:
        return [
            "stress test",
            "exercise stress",
            "treadmill test",
            "exercise tolerance test",
            "bruce protocol",
            "modified bruce",
            "exercise treadmill",
            "cardiac stress",
            "exercise ecg",
            "exercise ekg",
            "exercise electrocardiogram",
            "graded exercise test",
            "mets",
            "peak heart rate",
            "target heart rate",
            "st depression",
            "st segment",
            "duke treadmill",
            "chronotropic",
            "rate pressure product",
            "exercise capacity",
            # Nuclear / SPECT
            "nuclear stress",
            "myocardial perfusion",
            "spect",
            "sestamibi",
            # PET
            "cardiac pet",
            "pet/ct",
            "pet-ct",
            "rb-82",
            "rubidium",
            "mbf",
            "coronary flow reserve",
            # Pharmacologic
            "lexiscan",
            "regadenoson",
            "adenosine stress",
            "pharmacologic stress",
            # Echo
            "stress echocardiogram",
            "stress echo",
            "dobutamine stress",
            "dobutamine echo",
            "bicycle stress",
        ]

    @property
    def category(self) -> str:
        return "cardiac"

    # ------------------------------------------------------------------
    # Subtype resolution (used by registry.detect)
    # ------------------------------------------------------------------
    def resolve_subtype(self, extraction_result: ExtractionResult) -> tuple[str, str] | None:
        """Return the resolved stress subtype for this report."""
        return self._classify_subtype(extraction_result.full_text)

    # ------------------------------------------------------------------
    # Subtype classification
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_subtype(text: str) -> tuple[str, str]:
        """Determine the specific stress test subtype.

        Returns (type_id, display_name).
        """
        lower = text.lower()

        # Axis 1: pharmacologic vs exercise
        is_pharma = any(agent in lower for agent in _PHARMA_AGENTS)

        # Axis 2: imaging modality (priority: PET > SPECT > Echo > ECG-only)
        if any(kw in lower for kw in _PET_KEYWORDS):
            modality = "pet"
        elif any(kw in lower for kw in _SPECT_KEYWORDS):
            modality = "spect"
        elif any(kw in lower for kw in _ECHO_KEYWORDS):
            modality = "echo"
        else:
            modality = "ecg"

        # Special dobutamine rule: if dobutamine is detected AND echo
        # keywords are present → pharma_stress_echo. If dobutamine is
        # detected WITHOUT echo keywords, it's still pharmacologic but
        # modality depends on other imaging keywords.
        if "dobutamine" in lower and modality != "echo":
            # Dobutamine without echo keywords — still pharmacologic,
            # modality determined by other keywords above
            pass

        return _SUBTYPES[(is_pharma, modality)]

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, extraction_result: ExtractionResult) -> float:
        """Keyword-based detection with tiered scoring."""
        text = extraction_result.full_text.lower()

        strong_keywords = [
            "stress test",
            "exercise stress test",
            "exercise treadmill test",
            "exercise tolerance test",
            "treadmill stress",
            "cardiac stress test",
            "exercise stress echocardiogram",
            "bruce protocol",
            "modified bruce protocol",
            "graded exercise test",
            "exercise ecg",
            "exercise ekg",
            "exercise electrocardiogram",
            "treadmill exercise test",
            # Nuclear / SPECT
            "nuclear stress test",
            "myocardial perfusion imaging",
            "pharmacologic stress",
            # PET
            "cardiac pet",
            "myocardial blood flow",
            "coronary flow reserve",
            # Echo
            "stress echocardiogram",
            "dobutamine stress",
        ]
        moderate_keywords = [
            "mets achieved",
            "mets attained",
            "metabolic equivalents",
            "peak heart rate",
            "target heart rate",
            "max predicted heart rate",
            "mphr",
            "% predicted",
            "st depression",
            "st elevation",
            "st segment changes",
            "st changes",
            "duke treadmill score",
            "rate pressure product",
            "double product",
            "chronotropic",
            "exercise capacity",
            "exercise duration",
            "treadmill time",
            "exercise stage",
            "recovery phase",
            "peak exercise",
            # Nuclear / SPECT
            "spect",
            "sestamibi",
            "technetium",
            "tc-99m",
            "myoview",
            "thallium",
            # PET
            "pet/ct",
            "pet-ct",
            "rb-82",
            "rubidium",
            "positron",
            # Pharmacologic agents
            "lexiscan",
            "regadenoson",
            "adenosine",
            "dipyridamole",
            "dobutamine",
            # Echo
            "wall motion at stress",
            "bicycle stress",
            "stress echo",
        ]
        weak_keywords = [
            "treadmill",
            "bruce",
            "angina",
            "chest pain during exercise",
            "dyspnea on exertion",
            "exercise",
            "mets",
            "arrhythmia",
            "pvcs",
            "perfusion",
            "ischemia",
            "nuclear",
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

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse(
        self,
        extraction_result: ExtractionResult,
        gender: str | None = None,
        age: int | None = None,
    ) -> ParsedReport:
        """Extract structured measurements, sections, and findings."""
        text = extraction_result.full_text
        warnings: list[str] = []

        subtype_id, subtype_display = self._classify_subtype(text)

        # Choose measurement extractor based on subtype
        parsed_measurements: list[ParsedMeasurement] = []
        if subtype_id in ("pharma_pet_stress", "exercise_pet_stress"):
            _load_pet()
            parsed_measurements = _pet_extractor(text, gender)
        else:
            # Use stress test measurements for treadmill/SPECT/echo subtypes
            raw_measurements = extract_measurements(text, extraction_result.pages)
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
            test_type=subtype_id,
            test_type_display=subtype_display,
            detection_confidence=detection_confidence,
            measurements=parsed_measurements,
            sections=sections,
            findings=findings,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Reference ranges & glossary
    # ------------------------------------------------------------------
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
        return STRESS_GLOSSARY

    # ------------------------------------------------------------------
    # Prompt context (subtype-specific)
    # ------------------------------------------------------------------
    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        text = extraction_result.full_text if extraction_result else ""
        subtype_id, _ = self._classify_subtype(text)

        base = {
            "specialty": "cardiology",
            "category": "cardiac",
            "guidelines": "ACC/AHA 2002 Guideline Update for Exercise Testing",
        }

        if subtype_id == "exercise_treadmill_test":
            base["test_type"] = "exercise_stress_test"
            base["explanation_style"] = (
                "Focus on exercise capacity (METs), heart rate response "
                "(% of max predicted), blood pressure response, ECG changes "
                "(ST depression/elevation), and overall interpretation "
                "(positive, negative, equivocal, non-diagnostic). "
                "Comment on whether the patient reached target heart rate "
                "only because they exercised on a treadmill. "
                "Explain what the results mean for the patient's heart health."
            )

        elif subtype_id == "pharma_spect_stress":
            base["test_type"] = "pharma_spect_stress"
            base["explanation_style"] = (
                "This is a pharmacologic SPECT nuclear stress test. "
                "The PRIMARY focus is the presence or absence of ISCHEMIA "
                "(reversible perfusion defects). ALWAYS discuss ischemia and "
                "perfusion findings FIRST, BEFORE mentioning ejection fraction "
                "or pump strength. Ejection fraction should be mentioned as a "
                "secondary data point later in the explanation — do not celebrate "
                "or emphasize a normal EF, simply note it.\n"
                "IMPORTANT pharmacological stress rules:\n"
                "- Do NOT mention heart rate response to stress AT ALL. "
                "Heart rate response to exercise is invalid with pharmacological "
                "stress. Do NOT say anything like 'your heart rate response was "
                "lower than expected' or 'reaching X% of predicted maximum'. "
                "Do NOT comment on target heart rate, predicted maximum "
                "heart rate, or % of max predicted heart rate. The predicted "
                "maximum heart rate calculation does not apply because heart "
                "rate does not increase significantly with pharmacological stress.\n"
                "- Do NOT state that the heart rate response may limit "
                "interpretation of the EKG stress test. That caveat only "
                "applies to exercise-based tests.\n"
                "- Focus on perfusion findings (fixed vs reversible defects), "
                "wall motion, and overall interpretation."
            )
            base["interpretation_rules"] = (
                "SPECT NUCLEAR STRESS INTERPRETATION PRIORITIES:\n"
                "STRUCTURAL ORDERING RULE: The explanation MUST discuss "
                "ischemia / perfusion findings BEFORE any mention of ejection "
                "fraction or pump strength. Do NOT lead with EF. If there is "
                "no ischemia, say so first, then mention EF afterward.\n"
                "1. ISCHEMIA is the primary focus. State clearly whether "
                "ischemia is present or absent. Describe the location, extent, "
                "and severity of any perfusion defects.\n"
                "2. Distinguish fixed defects (scar/infarct) from reversible "
                "defects (ischemia).\n"
                "3. Ejection fraction is secondary — mention it AFTER perfusion "
                "findings. Do not emphasize or celebrate a normal EF.\n"
                "4. Summed stress/rest/difference scores (SSS/SRS/SDS) quantify "
                "perfusion abnormality if present.\n"
                "5. Wall motion abnormalities at stress (stunning) are "
                "significant markers of ischemia."
            )

        elif subtype_id == "exercise_spect_stress":
            base["test_type"] = "exercise_spect_stress"
            base["explanation_style"] = (
                "This is an exercise SPECT nuclear stress test. "
                "The PRIMARY focus is the presence or absence of ISCHEMIA "
                "(reversible perfusion defects). ALWAYS discuss ischemia and "
                "perfusion findings FIRST, BEFORE mentioning ejection fraction "
                "or pump strength. Also comment on exercise capacity (METs), "
                "heart rate response (% of max predicted), and ECG changes. "
                "Ejection fraction should be mentioned as a secondary data "
                "point later in the explanation — do not celebrate or emphasize "
                "a normal EF, simply note it."
            )
            base["interpretation_rules"] = (
                "SPECT NUCLEAR STRESS INTERPRETATION PRIORITIES:\n"
                "STRUCTURAL ORDERING RULE: The explanation MUST discuss "
                "ischemia / perfusion findings BEFORE any mention of ejection "
                "fraction or pump strength. Do NOT lead with EF. If there is "
                "no ischemia, say so first, then mention EF afterward.\n"
                "1. ISCHEMIA is the primary focus. State clearly whether "
                "ischemia is present or absent. Describe the location, extent, "
                "and severity of any perfusion defects.\n"
                "2. Distinguish fixed defects (scar/infarct) from reversible "
                "defects (ischemia).\n"
                "3. Exercise capacity and heart rate response provide context "
                "for the adequacy of the test.\n"
                "4. Ejection fraction is secondary — mention it AFTER perfusion "
                "findings. Do not emphasize or celebrate a normal EF.\n"
                "5. Summed stress/rest/difference scores (SSS/SRS/SDS) quantify "
                "perfusion abnormality if present.\n"
                "6. Wall motion abnormalities at stress (stunning) are "
                "significant markers of ischemia."
            )

        elif subtype_id == "pharma_pet_stress":
            base["test_type"] = "pharma_pet_stress"
            base["guidelines"] = "ASNC 2016 PET Myocardial Perfusion Imaging Guidelines"
            base["explanation_style"] = (
                "This is a pharmacologic cardiac PET/PET-CT perfusion study. "
                "The PRIMARY focus is the presence or absence of ISCHEMIA "
                "(reversible perfusion defects). ALWAYS discuss ischemia and "
                "perfusion findings FIRST, BEFORE mentioning ejection fraction "
                "or pump strength. Ejection fraction should be mentioned as a "
                "secondary data point later in the explanation — do not celebrate "
                "or emphasize a normal EF, simply note it.\n"
                "For coronary flow reserve (CFR) and myocardial flow reserve "
                "(MFR): do NOT state 'we may make adjustments based on mild "
                "reductions in flow reserve.' Instead, only mention CFR/MFR "
                "if there are significant defects (CFR < 1.5 in a territory) "
                "that support or corroborate perfusion defect findings. Mildly "
                "reduced CFR (1.5-2.0) in the absence of perfusion defects "
                "should be noted briefly without alarm.\n"
                "IMPORTANT pharmacological stress rules:\n"
                "- Do NOT mention heart rate response to stress AT ALL. "
                "Heart rate response to exercise is invalid with pharmacological "
                "stress. Do NOT comment on target heart rate, predicted maximum "
                "heart rate, or % of max predicted heart rate.\n"
                "- Do NOT state that the heart rate response may limit "
                "interpretation of the EKG stress test."
            )
            base["interpretation_rules"] = (
                "CARDIAC PET/PET-CT INTERPRETATION PRIORITIES:\n"
                "STRUCTURAL ORDERING RULE: The explanation MUST discuss "
                "ischemia / perfusion findings BEFORE any mention of ejection "
                "fraction or pump strength. Do NOT lead with EF. If there is "
                "no ischemia, say so first, then mention EF afterward.\n"
                "1. ISCHEMIA is the primary focus. State clearly whether "
                "ischemia is present or absent. Describe the location, extent, "
                "and severity of any perfusion defects.\n"
                "2. Ejection fraction is secondary — mention it AFTER perfusion "
                "findings. Do not emphasize or celebrate a normal EF. Do not "
                "make EF the headline of the explanation.\n"
                "3. Coronary Flow Reserve (CFR) / Myocardial Flow Reserve (MFR):\n"
                "   - Do NOT say 'we may need to make adjustments based on "
                "mild reductions in flow reserve'\n"
                "   - If CFR is significantly reduced (< 1.5) in a territory "
                "AND there are corresponding perfusion defects, mention that "
                "the reduced flow reserve supports/corroborates the perfusion "
                "findings\n"
                "   - If CFR is mildly reduced (1.5-2.0) without perfusion "
                "defects, note it briefly as a finding without alarm (e.g., "
                "'flow reserve was mildly reduced in this territory')\n"
                "   - Globally reduced CFR without focal perfusion defects "
                "may suggest microvascular disease\n"
                "4. Wall motion abnormalities during stress (stunning) are "
                "significant markers of ischemia."
            )

        elif subtype_id == "exercise_pet_stress":
            base["test_type"] = "exercise_pet_stress"
            base["guidelines"] = "ASNC 2016 PET Myocardial Perfusion Imaging Guidelines"
            base["explanation_style"] = (
                "This is an exercise cardiac PET/PET-CT perfusion study. "
                "The PRIMARY focus is the presence or absence of ISCHEMIA "
                "(reversible perfusion defects). ALWAYS discuss ischemia and "
                "perfusion findings FIRST, BEFORE mentioning ejection fraction "
                "or pump strength. Also comment on exercise capacity (METs) "
                "and heart rate response. Ejection fraction should be mentioned "
                "as a secondary data point later in the explanation — do not "
                "celebrate or emphasize a normal EF, simply note it.\n"
                "For coronary flow reserve (CFR) and myocardial flow reserve "
                "(MFR): do NOT state 'we may make adjustments based on mild "
                "reductions in flow reserve.' Instead, only mention CFR/MFR "
                "if there are significant defects (CFR < 1.5 in a territory) "
                "that support or corroborate perfusion defect findings. Mildly "
                "reduced CFR (1.5-2.0) in the absence of perfusion defects "
                "should be noted briefly without alarm."
            )
            base["interpretation_rules"] = (
                "CARDIAC PET/PET-CT INTERPRETATION PRIORITIES:\n"
                "STRUCTURAL ORDERING RULE: The explanation MUST discuss "
                "ischemia / perfusion findings BEFORE any mention of ejection "
                "fraction or pump strength. Do NOT lead with EF. If there is "
                "no ischemia, say so first, then mention EF afterward.\n"
                "1. ISCHEMIA is the primary focus. State clearly whether "
                "ischemia is present or absent. Describe the location, extent, "
                "and severity of any perfusion defects.\n"
                "2. Exercise capacity and heart rate response provide context "
                "for the adequacy of the test.\n"
                "3. Ejection fraction is secondary — mention it AFTER perfusion "
                "findings. Do not emphasize or celebrate a normal EF.\n"
                "4. Coronary Flow Reserve (CFR) / Myocardial Flow Reserve (MFR):\n"
                "   - Do NOT say 'we may need to make adjustments based on "
                "mild reductions in flow reserve'\n"
                "   - If CFR is significantly reduced (< 1.5) in a territory "
                "AND there are corresponding perfusion defects, mention that "
                "the reduced flow reserve supports/corroborates the perfusion "
                "findings\n"
                "   - If CFR is mildly reduced (1.5-2.0) without perfusion "
                "defects, note it briefly without alarm\n"
                "   - Globally reduced CFR without focal perfusion defects "
                "may suggest microvascular disease\n"
                "5. Wall motion abnormalities during stress (stunning) are "
                "significant markers of ischemia."
            )

        elif subtype_id == "exercise_stress_echo":
            base["test_type"] = "exercise_stress_echo"
            base["explanation_style"] = (
                "This is an exercise stress echocardiogram. Focus on wall "
                "motion abnormalities at rest vs stress, new wall motion "
                "abnormalities induced by exercise, and EF change with stress. "
                "Also comment on exercise capacity (METs), heart rate response "
                "(% of max predicted), and overall interpretation. "
                "Explain what the results mean for the patient's heart health."
            )
            base["interpretation_rules"] = (
                "STRESS ECHOCARDIOGRAM INTERPRETATION PRIORITIES:\n"
                "1. Wall motion at rest vs stress is the primary comparison.\n"
                "2. New wall motion abnormalities at peak stress indicate "
                "inducible ischemia.\n"
                "3. EF change with stress: normally EF increases with exercise.\n"
                "4. Exercise capacity and heart rate response provide context.\n"
                "5. Valvular changes with exercise (e.g., dynamic mitral "
                "regurgitation) should be noted if present."
            )

        elif subtype_id == "pharma_stress_echo":
            base["test_type"] = "pharma_stress_echo"
            base["explanation_style"] = (
                "This is a pharmacologic (dobutamine) stress echocardiogram. "
                "Focus on wall motion abnormalities at rest vs stress, new "
                "wall motion abnormalities induced by dobutamine, and EF "
                "change with stress. Heart rate response IS relevant with "
                "dobutamine since it increases heart rate. "
                "Explain what the results mean for the patient's heart health."
            )
            base["interpretation_rules"] = (
                "DOBUTAMINE STRESS ECHO INTERPRETATION PRIORITIES:\n"
                "1. Wall motion at rest vs peak dobutamine is the primary "
                "comparison.\n"
                "2. New wall motion abnormalities at peak dose indicate "
                "inducible ischemia.\n"
                "3. Biphasic response (improvement at low dose, worsening at "
                "high dose) suggests viable but ischemic myocardium.\n"
                "4. Heart rate response to dobutamine IS relevant — adequate "
                "heart rate should be achieved for a diagnostic study.\n"
                "5. EF change with stress: normally EF increases.\n"
                "6. Valvular changes with dobutamine should be noted."
            )

        return base

    # ------------------------------------------------------------------
    # Section / findings extraction (unchanged)
    # ------------------------------------------------------------------
    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"INDICATION|REASON\s+FOR\s+(?:TEST|STUDY)",
            r"PROTOCOL|EXERCISE\s+PROTOCOL|PROCEDURE",
            r"BASELINE|RESTING|PRE[- ]?EXERCISE",
            r"EXERCISE\s+(?:DATA|RESPONSE|RESULTS|PHASE)",
            r"HEMODYNAMIC\s+(?:DATA|RESPONSE)",
            r"ECG\s+(?:FINDINGS|CHANGES|RESPONSE|INTERPRETATION)",
            r"EKG\s+(?:FINDINGS|CHANGES|RESPONSE|INTERPRETATION)",
            r"ELECTROCARDIOGRAPHIC\s+(?:FINDINGS|CHANGES|RESPONSE)",
            r"ST\s+(?:SEGMENT\s+)?(?:ANALYSIS|CHANGES)",
            r"SYMPTOMS|SYMPTOM\s+RESPONSE",
            r"ARRHYTHMIA|RHYTHM",
            r"RECOVERY|POST[- ]?EXERCISE",
            r"PERFUSION|PERFUSION\s+(?:FINDINGS|IMAGES|RESULTS)",
            r"GATED\s+(?:IMAGES|SPECT|DATA)",
            r"WALL\s+MOTION",
            r"STRESS\s+(?:IMAGES|DATA|RESULTS)",
            r"REST\s+(?:IMAGES|DATA|RESULTS)",
            r"FLOW\s+(?:DATA|QUANTIFICATION|RESERVE)",
            r"CONCLUSION|IMPRESSION|SUMMARY|INTERPRETATION|FINDINGS",
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
        """Extract conclusion/impression/interpretation lines."""
        findings: list[str] = []
        findings_re = re.compile(
            r"(?:CONCLUSION|IMPRESSION|SUMMARY|INTERPRETATION|FINDINGS)\s*[:\-]?\s*\n"
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
