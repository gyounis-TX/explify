from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType, split_text_zones, keyword_zone_weight
from .glossary import CORONARY_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement


class CoronaryDiagramHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "coronary_diagram"

    @property
    def display_name(self) -> str:
        return "Coronary Diagram"

    @property
    def keywords(self) -> list[str]:
        return [
            "coronary diagram",
            "coronary angiogram",
            "cath lab",
            "cardiac catheterization",
            "hemodynamics",
            "rca",
            "lad",
            "lcx",
            "left main",
            "stenosis",
            "ivus",
            "lvedp",
            "guide catheter",
            "guide wire",
            "angiogram",
            "ventriculogram",
            "pci",
            "pcwp",
            "pcp",
            "coronary artery",
        ]

    @property
    def category(self) -> str:
        return "cardiac"

    def detect(self, extraction_result: ExtractionResult) -> float:
        """Keyword-based detection with positional weighting.

        Keywords in the title/header count more; keywords in comparison
        sections are discounted.  CMR-specific terms suppress the score
        since cardiac MRI reports share some keywords (e.g. hemodynamics).
        """
        title, comparison, body = split_text_zones(extraction_result.full_text)

        strong_keywords = [
            "coronary diagram",
            "coronary angiogram",
            "cardiac catheterization",
            "cath lab",
            "hemodynamics",
            "coronary angiography",
        ]
        moderate_keywords = [
            "lvedp",
            "ivus",
            "guide catheter",
            "guide wire",
            "ventriculogram",
            "pcwp",
            "pcp",
            "pci",
            "left main",
            "non-obstructive cad",
            "obstructive cad",
            "xb4",
            "xb3.5",
            "jr4",
            "jl4",
            "jl4.5",
            "sion blue",
            "edp",
        ]
        weak_keywords = [
            "rca",
            "lad",
            "lcx",
            "stenosis",
            "angiogram",
            "coronary artery",
            "catheter",
            "stent",
            "large root",
            "0.014",
            "phillips",
            "medical rx",
            "findings",
            "diagnosis",
        ]

        # CMR-specific terms — if present, this is likely a cardiac MRI.
        cmr_negatives = [
            "cardiac mri", "cardiac magnetic", "cmr", "mr cardiac",
            "mri cardiac", "mri heart", "late gadolinium", "t1 mapping",
            "t2 mapping", "delayed enhancement", "gadolinium",
            "cine imaging", "t2 stir",
        ]

        strong_title_or_body = 0
        for k in strong_keywords:
            w = keyword_zone_weight(k, title, comparison, body)
            if w >= 1.0:
                strong_title_or_body += 1

        moderate_count = sum(1 for k in moderate_keywords
                            if keyword_zone_weight(k, title, comparison, body) >= 1.0)
        weak_count = sum(1 for k in weak_keywords
                         if keyword_zone_weight(k, title, comparison, body) >= 1.0)

        if strong_title_or_body > 0:
            base = 0.7
        elif moderate_count >= 3:
            base = 0.4
        elif moderate_count >= 1:
            base = 0.2
        else:
            base = 0.0

        bonus = min(0.3, moderate_count * 0.05 + weak_count * 0.02)
        score = min(1.0, base + bonus)

        # Suppress when CMR terms are present in title/body
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
            # Use stenosis_pct reference range for all stenosis measurements
            ref_abbr = m.abbreviation
            if ref_abbr.startswith("stenosis_"):
                ref_abbr = "stenosis_pct"

            classification = classify_measurement(ref_abbr, m.value, gender)
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
        return CORONARY_GLOSSARY

    def get_vision_hints(self) -> str:
        return (
            "This is a CORONARY ANGIOGRAM DIAGRAM -- a hand-drawn cath lab report form.\n\n"
            "VESSEL LABELS ON THE DIAGRAM:\n"
            "Arteries are often labeled directly with abbreviations: RCA, LAD, LCX "
            "(or LCx), D1, D2, OM, OM1, OM2, PDA, Left Main (or LM). These labels "
            "identify which vessel is which. Transcribe all vessel labels exactly.\n\n"
            "CRITICAL HANDWRITTEN ELEMENTS TO IDENTIFY:\n"
            "1. STENOSIS PERCENTAGES: Numbers with % signs written along artery lines "
            "(e.g., '50%', '70-80%', '100%'). These indicate the degree of blockage.\n"
            "2. TOTAL OCCLUSION: An artery drawn as completely blocked/filled in or "
            "with a thick line through it = 100% occlusion. Transcribe as '[vessel] 100%'.\n"
            "3. BYPASS GRAFTS: New vessel lines drawn connecting to arteries PAST a "
            "blockage point. These are surgical bypasses (SVG = saphenous vein graft, "
            "LIMA = left internal mammary artery). They often connect from the aortic "
            "root to a point beyond the blockage.\n"
            "4. OCCLUDED BYPASS GRAFT STUMPS: Short lines coming off the aortic root "
            "that end abruptly = a blocked bypass graft. Transcribe as 'SVG to [vessel] "
            "occluded' or 'graft stump'.\n"
            "5. GRAFT STENOSIS: Bypass grafts can have their own percentage stenosis "
            "annotations, just like native vessels.\n"
            "6. CALCIFICATION: Plus signs (+, ++, +++) drawn along an artery indicate "
            "calcification. More plus signs = heavier calcification.\n"
            "7. HEMODYNAMICS TABLE: Handwritten pressure values in a table with rows "
            "for RA, RV, PA, PCP/PCWP, AO, LV. Values are systolic/diastolic "
            "(e.g., '25/12') or mean (e.g., 'm=8'). Also look for LVEDP/EDP.\n"
            "8. EQUIPMENT: Catheter names (JR4, JL4.5, XB4, XB3.5, AL1, AL2, "
            "Amplatz), wire names (Sion Blue, Pilot 200, BMW), and IVUS details.\n"
            "9. VENTRICULOGRAM: Two circle/oval shapes with X marks -- note wall "
            "motion descriptions if handwritten nearby.\n"
            "10. DIAGNOSIS LINE: Often handwritten at bottom (e.g., 'Non-obstructive "
            "CAD', '3-vessel disease', 'Normal coronaries').\n\n"
            "For EACH artery transcribed, include the vessel name and any associated "
            "annotation (stenosis %, calcification, occlusion, graft status)."
        )

    def get_prompt_context(self, extraction_result: ExtractionResult | None = None) -> dict:
        return {
            "specialty": "interventional cardiology",
            "test_type": "coronary angiogram diagram",
            "category": "cardiac",
            "guidelines": "ACC/AHA Coronary Revascularization Guidelines",
            "explanation_style": (
                "Explain each finding in plain language. "
                "Compare hemodynamic pressures to normal ranges. "
                "Describe stenosis severity and its clinical significance. "
                "Avoid medical jargon where possible."
            ),
            "interpretation_rules": (
                "This is a hand-drawn cath lab coronary angiogram report form. "
                "The coronary artery tree is drawn over a heart silhouette.\n\n"
                "ANATOMY LAYOUT:\n"
                "- The large vessel on the LEFT side of the diagram is the AORTA.\n"
                "- The first small artery branching off the aorta to the RIGHT is "
                "the LEFT MAIN, which splits into two branches:\n"
                "  - LAD (Left Anterior Descending): branches off horizontally "
                "to the right.\n"
                "  - LCx (Left Circumflex): continues downward toward the bottom "
                "of the page.\n"
                "- The RCA (Right Coronary Artery) is a separate vessel.\n"
                "- Two oval/circle shapes with X marks represent the "
                "ventriculogram views (normal wall motion if X is centered).\n\n"
                "DIAGRAM MARKINGS:\n"
                "- Plus signs (+) drawn along an artery indicate CALCIFICATION "
                "of that vessel segment.\n"
                "- Percentage numbers written near an artery (e.g. '50%', "
                "'40-50%') indicate the degree of STENOSIS (blockage) at that "
                "location.\n"
                "- 'Large root' or similar notation near the aorta indicates an "
                "enlarged aortic root.\n\n"
                "TOTAL OCCLUSION:\n"
                "- A vessel drawn as completely blocked/filled in indicates 100% "
                "occlusion (no blood flow through the native artery at that point).\n"
                "- May be referred to as CTO (Chronic Total Occlusion) if present "
                "for more than 3 months.\n\n"
                "BYPASS GRAFTS:\n"
                "- New vessel lines drawn from the aortic root to a point on a native "
                "artery PAST a blockage represent surgical bypass grafts.\n"
                "- SVG (Saphenous Vein Graft) and LIMA/RIMA (Internal Mammary Artery) "
                "are common graft types.\n"
                "- Grafts can have their own stenosis percentages annotated.\n"
                "- A short line/stump coming off the aortic root that ends abruptly "
                "represents a completely occluded (blocked) bypass graft.\n\n"
                "HEMODYNAMICS TABLE:\n"
                "- Pressures are recorded as systolic/diastolic with optional "
                "mean (m) values in mmHg.\n"
                "- Rows: RA (right atrium), RV (right ventricle), PA (pulmonary "
                "artery), PCP/PCWP (pulmonary capillary wedge pressure), "
                "AO (aorta), LV (left ventricle).\n"
                "- EDP = end-diastolic pressure (LVEDP).\n"
                "- SAT% column may show oxygen saturations.\n\n"
                "EQUIPMENT NOTATION:\n"
                "- Guide catheters: JR4 (Judkins Right 4, for RCA), JL4.5 "
                "(Judkins Left 4.5, diagnostic for left system), XB4 (extra "
                "backup 4, guide catheter for left system intervention).\n"
                "- Coronary wires: e.g. 'Sion Blue 0.014\"' -- a workhorse "
                "0.014-inch guidewire used in PCI.\n"
                "- IVUS brand: e.g. 'Phillips IVUS' -- intravascular ultrasound "
                "probe used during the procedure.\n\n"
                "IVUS FINDINGS:\n"
                "- Written near the diagram when intravascular ultrasound was "
                "performed during the procedure.\n"
                "- Key values: calcium arc (degrees), MLA (minimum lumen area "
                "in mm\u00b2), obstruction percentage.\n\n"
                "ORGANIZE findings in this order: coronary anatomy and stenosis "
                "(left main, LAD, LCx, RCA), then hemodynamic pressures, "
                "then IVUS findings if present, then equipment used, then "
                "ventriculogram findings, then diagnosis."
            ),
        }

    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"HEMODYNAMICS?",
            r"CORONARY\s+(?:ANATOMY|ANGIOGRAPH?Y|FINDINGS?)",
            r"LEFT\s+(?:CORONARY|MAIN|SYSTEM)",
            r"RIGHT\s+(?:CORONARY|SYSTEM)",
            r"VENTRICULOGRA(?:M|PHY)",
            r"IVUS(?:\s+FINDINGS?)?",
            r"FINDINGS?",
            r"DIAGNOSIS|DX",
            r"EQUIPMENT|CATHETERS?",
            r"PROCEDURE",
            r"CONCLUSION|IMPRESSION|SUMMARY",
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
        """Extract diagnosis/conclusion/findings lines."""
        findings: list[str] = []
        findings_re = re.compile(
            r"(?:DIAGNOSIS|DX|CONCLUSION|IMPRESSION|SUMMARY|FINDINGS)\s*[:\-]?\s*\n"
            r"([\s\S]*?)(?:\n\s*\n|\Z)",
            re.IGNORECASE,
        )
        for match in findings_re.finditer(text):
            block = match.group(1).strip()
            lines = re.split(r"\n\s*(?:\d+[\.\)]\s*|[-*]\s*)", block)
            for line in lines:
                line = line.strip()
                if line and len(line) > 5:
                    findings.append(line)

        return findings
