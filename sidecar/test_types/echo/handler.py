from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType, split_text_zones, keyword_zone_weight
from .glossary import ECHO_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement

# ---------------------------------------------------------------------------
# TTE prompt rule constants — decision tree style (mirrors PET pattern)
# ---------------------------------------------------------------------------

_TTE_STYLE = (
    "This is a transthoracic echocardiogram (TTE).\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(LV systolic -> diastolic -> valvular -> right heart -> pericardium).\n"
    "At Grade 12 literacy: explain what each finding means in context. Define "
    "terms before using them (e.g., 'ejection fraction, which measures how "
    "strongly your heart pumps...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Lead with the most clinically significant finding. If everything "
    "is normal, say so clearly and concisely up front."
)

_TTE_RULES = (
    "TRANSTHORACIC ECHOCARDIOGRAM — DECISION TREE:\n\n"
    "STEP 1 — LV SYSTOLIC FUNCTION (always first):\n"
    "  - Report LVEF with severity classification (normal/mild/moderate/severe).\n"
    "  - If LVEF is normal (>=52% male, >=54% female): state clearly, then move on.\n"
    "    Do NOT celebrate or overemphasize a normal EF.\n"
    "  - If LVEF is reduced: this is the headline finding. State the degree of\n"
    "    reduction and what it means for pump function.\n"
    "  - Wall motion abnormalities: if present, map to coronary territories\n"
    "    (anterior/septal -> LAD, inferior -> RCA, lateral -> LCx).\n"
    "    Focal WMA + reduced EF suggests ischemic etiology.\n"
    "    Global hypokinesis suggests non-ischemic cardiomyopathy.\n\n"
    "STEP 2 — DIASTOLIC FUNCTION:\n"
    "  - State the diastolic function grade (Normal / Grade I / II / III /\n"
    "    Indeterminate) — use the pre-computed grade if provided.\n"
    "  - Grade I (impaired relaxation): most common, age-related, usually benign.\n"
    "    Do NOT alarm. 'Very common with age' is appropriate context.\n"
    "  - Grade II (pseudonormal): moderate — filling pressures are elevated\n"
    "    despite a normal-appearing E/A ratio. Explain that deeper measurements\n"
    "    reveal the heart is working harder to fill.\n"
    "  - Grade III (restrictive): most severe — significantly elevated filling\n"
    "    pressures. Frame as important but avoid panic language.\n"
    "  - Indeterminate: when measurements disagree, say so honestly. Suggest\n"
    "    clinical correlation.\n"
    "  - If diastolic dysfunction is the ONLY abnormality on the echo,\n"
    "    contextualize with age and comorbidities (hypertension, diabetes).\n\n"
    "STEP 3 — CHAMBER SIZES:\n"
    "  - LV dimensions (LVIDd/LVIDs): note if dilated. LV dilation + reduced\n"
    "    EF = dilated cardiomyopathy pattern.\n"
    "  - LA size (LAVI): enlarged LA (>34 mL/m2) is a marker of chronically\n"
    "    elevated filling pressures and atrial fibrillation risk.\n"
    "  - RV size: note if dilated. Correlate with TAPSE and RVSP.\n"
    "  - Wall thickness (IVSd/LVPWd): >1.1 cm suggests LVH. Note pattern\n"
    "    (concentric vs asymmetric).\n\n"
    "STEP 4 — VALVULAR FINDINGS:\n"
    "  - For each abnormal valve, state: which valve, type of lesion\n"
    "    (regurgitation vs stenosis), and severity (trace/mild/moderate/severe).\n"
    "  - Aortic stenosis: classify by AVA (>1.5 mild, 1.0-1.5 moderate,\n"
    "    <1.0 severe). Cross-check with gradient if available.\n"
    "  - Trace/mild regurgitation: do NOT alarm. Prevalence context:\n"
    "    'Trace mitral or tricuspid regurgitation is found in ~70%% of\n"
    "    healthy hearts and is considered a normal finding.'\n"
    "  - Moderate or severe regurgitation: frame as a significant finding\n"
    "    an important finding we'll want to discuss. Do not minimize.\n"
    "  - Aortic sclerosis (thickening without significant stenosis): common\n"
    "    age-related finding. 'Similar to how arteries can develop mild\n"
    "    plaque buildup with age.'\n\n"
    "STEP 5 — RIGHT HEART & PULMONARY PRESSURES:\n"
    "  - RVSP: classify (normal <35, mild PH 36-50, moderate 51-70,\n"
    "    severe >70 mmHg).\n"
    "  - TAPSE: <1.7 cm suggests RV systolic dysfunction.\n"
    "  - Correlate: elevated RVSP + normal TAPSE = RV coping under pressure.\n"
    "    Elevated RVSP + reduced TAPSE = RV failing under pressure.\n\n"
    "STEP 6 — PERICARDIUM & OTHER:\n"
    "  - Pericardial effusion: classify size (trace/small/moderate/large).\n"
    "  - Trace effusion: 'present in about 10%% of echocardiograms' — normalize.\n"
    "  - Aortic root: note if dilated (>4.0 cm).\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Dyspnea → diastolic dysfunction, elevated filling pressures, reduced EF,\n"
    "    significant valvular disease, pulmonary hypertension.\n"
    "  - Chest pain → wall motion abnormalities (ischemia pattern), pericardial\n"
    "    effusion.\n"
    "  - Palpitations → chamber enlargement (especially LA), valvular disease.\n"
    "  - Edema / weight gain → RV dysfunction, elevated RVSP, TR, reduced EF.\n"
    "  - Syncope → severe AS, LVOT obstruction, severely reduced EF.\n"
    "  When the indication includes a symptom, explicitly connect: 'This finding\n"
    "  may help explain the [symptom] you've been experiencing.'\n\n"
    "RISK CONTEXT:\n"
    "  - Normal echo: very reassuring.\n"
    "  - Trace/mild regurgitation: prevalence ~70%% — normalize.\n"
    "  - Grade I diastolic dysfunction: prevalence ~30%% over 60 — normalize.\n\n"
    "GUARDRAILS:\n"
    "  - Trace/mild TR or MR: Do NOT flag as concerning. State it is a normal\n"
    "    variant seen in most healthy hearts. Do NOT recommend follow-up for\n"
    "    trace regurgitation alone.\n"
    "  - Grade I diastolic dysfunction in patients over 60: Do NOT alarm.\n"
    "    Context: 'found in about 30%% of people over 60.'\n"
    "  - Mild LVH with normal EF: Do NOT dramatize. Context: 'commonly seen\n"
    "    with longstanding high blood pressure.'\n"
    "  - LVEF above normal range: Do NOT flag, caution, or comment on an EF\n"
    "    above the upper limit of normal. An EF of 65-75%% is not clinically\n"
    "    concerning and should simply be stated as normal. Do NOT use terms\n"
    "    like 'above normal', 'supranormal', or 'hyperdynamic' UNLESS the\n"
    "    report specifically raises concern for HCM.\n"
    "  - Aortic sclerosis without stenosis: Do NOT call it 'aortic valve\n"
    "    disease.' It is age-related thickening, not a disease state.\n"
    "  - Do NOT restate clinical indications at the end. If findings correlate\n"
    "    with an indication, weave it into the relevant finding.\n"
    "  - Do NOT mention who interpreted/read the study or comment on\n"
    "    availability of prior studies.\n"
    "  - Normal echo: When ALL findings are normal, keep the explanation\n"
    "    concise. Do NOT pad with unnecessary detail about each normal\n"
    "    measurement. A 2-3 sentence summary is sufficient for a completely\n"
    "    normal study."
)


class EchocardiogramHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "echocardiogram"

    @property
    def display_name(self) -> str:
        return "Echocardiogram"

    @property
    def keywords(self) -> list[str]:
        return [
            "echocardiogram",
            "echocardiography",
            "transthoracic",
            "transesophageal",
            "2d echo",
            "doppler",
            "ejection fraction",
            "lvef",
            "left ventricle",
            "left ventricular",
            "mitral valve",
            "aortic valve",
            "tricuspid",
            "diastolic function",
            "wall motion",
            "lvidd",
            "lvids",
            "ivsd",
            "lvpwd",
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
            "echocardiogram",
            "echocardiography",
            "transthoracic echocardiogram",
            "transesophageal echocardiogram",
            "2d echo",
        ]
        moderate_keywords = [
            "ejection fraction",
            "lvef",
            "left ventricular",
            "diastolic function",
            "wall motion",
            "lvidd",
            "lvids",
            "mitral valve",
            "aortic valve",
            "tricuspid valve",
            "e/a ratio",
            "e/e'",
            "rvsp",
        ]
        weak_keywords = [
            "left ventricle",
            "right ventricle",
            "left atrium",
            "pericardial",
            "doppler",
            "regurgitation",
            "stenosis",
        ]

        # CMR-specific terms — if these appear in title/body, this is likely
        # a cardiac MRI, not an echo.
        cmr_negatives = [
            "cardiac mri", "cardiac magnetic", "cmr", "mr cardiac",
            "mri cardiac", "mri heart", "late gadolinium", "t1 mapping",
            "t2 mapping", "myocardial perfusion mri",
            "delayed enhancement", "gadolinium", "cine imaging",
            "t2 stir",
        ]

        # Positional weighting: strong keywords in comparison-only don't
        # count as strong (e.g. "Comparison: Echocardiogram on ...").
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
            # "echocardiogram" only in comparison — very weak signal
            base = 0.15
        else:
            base = 0.0

        bonus = min(0.3, moderate_count * 0.05 + weak_count * 0.02)
        score = min(1.0, base + bonus)

        # CMR negative penalty — only count CMR terms in title/body
        cmr_count = sum(1 for k in cmr_negatives
                        if keyword_zone_weight(k, title, comparison, body) >= 1.0)
        if cmr_count > 0:
            score *= max(0.0, 1.0 - cmr_count * 0.3)

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
        return ECHO_GLOSSARY

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        base = {
            "specialty": "cardiology",
            "test_type": "echocardiogram",
            "category": "cardiac",
            "guidelines": "ASE 2015 Chamber Quantification Guidelines",
            "explanation_style": _TTE_STYLE,
            "interpretation_rules": _TTE_RULES,
        }
        if extraction_result:
            self._inject_diastolic_grade(base, extraction_result)
        return base

    def _inject_diastolic_grade(
        self, base: dict, extraction_result: ExtractionResult
    ) -> None:
        """Compute diastolic function grade and inject into prompt context."""
        text = extraction_result.full_text
        # Re-extract measurements for diastolic grade computation
        raw_measurements = extract_measurements(text, extraction_result.pages)
        parsed: list[ParsedMeasurement] = []
        for m in raw_measurements:
            classification = classify_measurement(m.abbreviation, m.value)
            parsed.append(
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
        from test_types.extractors.echo import get_diastolic_grade

        grade_info = get_diastolic_grade(text, parsed)
        if grade_info:
            base["diastolic_grade"] = grade_info

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"LEFT\s+VENTRICLE|LV\s+DIMENSIONS?",
            r"RIGHT\s+VENTRICLE|RV\b",
            r"LEFT\s+ATRIUM|LA\b",
            r"RIGHT\s+ATRIUM|RA\b",
            r"AORTIC\s+(?:ROOT|VALVE)",
            r"MITRAL\s+VALVE",
            r"TRICUSPID\s+VALVE",
            r"PULMON(?:ARY|IC)\s+VALVE",
            r"PERICARDI(?:UM|AL)",
            r"DIASTOLIC\s+FUNCTION",
            r"WALL\s+MOTION",
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
