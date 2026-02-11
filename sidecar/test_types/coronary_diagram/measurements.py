"""
Regex-based measurement extraction for coronary angiogram / cath lab diagrams.

Extracts hemodynamic pressures (RA, RV, PA, PCP/PCWP, AO, LV, LVEDP),
coronary stenosis percentages, and IVUS findings from OCR'd text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from api.models import PageExtractionResult


@dataclass
class RawMeasurement:
    name: str
    abbreviation: str
    value: float
    unit: str
    raw_text: str
    page_number: Optional[int] = None


@dataclass
class MeasurementDef:
    """Definition of a measurement to extract."""

    name: str
    abbreviation: str
    unit: str
    patterns: list[str]
    value_min: float = 0.0
    value_max: float = 999.0


_NUM = r"(?P<value>\d+\.?\d*)"
_SEP = r"[\s:=]+\s*"

MEASUREMENT_DEFS: list[MeasurementDef] = [
    # --- Hemodynamic Pressures ---
    # RA mean
    MeasurementDef(
        name="RA Mean Pressure",
        abbreviation="RA_mean",
        unit="mmHg",
        patterns=[
            rf"(?i)RA\s+(?:mean|m){_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)(?:right\s+atri(?:um|al))\s+(?:mean\s+)?(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)RA{_SEP}{_NUM}\s*(?:mmHg)",
        ],
        value_min=0.0,
        value_max=40.0,
    ),
    # RV systolic
    MeasurementDef(
        name="RV Systolic Pressure",
        abbreviation="RV_systolic",
        unit="mmHg",
        patterns=[
            rf"(?i)RV{_SEP}{_NUM}\s*/",
            rf"(?i)(?:right\s+ventricl(?:e|ar))\s+(?:systolic\s+)?(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=10.0,
        value_max=120.0,
    ),
    # RV diastolic
    MeasurementDef(
        name="RV Diastolic Pressure",
        abbreviation="RV_diastolic",
        unit="mmHg",
        patterns=[
            rf"(?i)RV\s+\d+\s*/\s*{_NUM}",
            rf"(?i)(?:right\s+ventricl(?:e|ar))\s+(?:end[- ]?)?diastolic\s+(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=0.0,
        value_max=40.0,
    ),
    # PA systolic
    MeasurementDef(
        name="PA Systolic Pressure",
        abbreviation="PA_systolic",
        unit="mmHg",
        patterns=[
            rf"(?i)PA{_SEP}{_NUM}\s*/",
            rf"(?i)(?:pulmonary\s+artery)\s+(?:systolic\s+)?(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=10.0,
        value_max=120.0,
    ),
    # PA diastolic
    MeasurementDef(
        name="PA Diastolic Pressure",
        abbreviation="PA_diastolic",
        unit="mmHg",
        patterns=[
            rf"(?i)PA\s+\d+\s*/\s*{_NUM}",
            rf"(?i)(?:pulmonary\s+artery)\s+diastolic\s+(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=0.0,
        value_max=50.0,
    ),
    # PA mean
    MeasurementDef(
        name="PA Mean Pressure",
        abbreviation="PA_mean",
        unit="mmHg",
        patterns=[
            rf"(?i)PA\s+(?:mean|m){_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)(?:pulmonary\s+artery)\s+mean\s+(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)(?:mean\s+)?PA\s+(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=5.0,
        value_max=80.0,
    ),
    # PCWP / PCP
    MeasurementDef(
        name="Pulmonary Capillary Wedge Pressure",
        abbreviation="PCWP",
        unit="mmHg",
        patterns=[
            rf"(?i)(?:PCWP|PCP|PCW|wedge){_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)(?:pulmonary\s+capillary\s+wedge\s+pressure){_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=0.0,
        value_max=50.0,
    ),
    # AO systolic
    MeasurementDef(
        name="Aortic Systolic Pressure",
        abbreviation="AO_systolic",
        unit="mmHg",
        patterns=[
            rf"(?i)AO{_SEP}{_NUM}\s*/",
            rf"(?i)(?:aort(?:a|ic))\s+(?:systolic\s+)?(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=50.0,
        value_max=250.0,
    ),
    # AO diastolic
    MeasurementDef(
        name="Aortic Diastolic Pressure",
        abbreviation="AO_diastolic",
        unit="mmHg",
        patterns=[
            rf"(?i)AO\s+\d+\s*/\s*{_NUM}",
            rf"(?i)(?:aort(?:a|ic))\s+diastolic\s+(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=20.0,
        value_max=150.0,
    ),
    # LV systolic
    MeasurementDef(
        name="LV Systolic Pressure",
        abbreviation="LV_systolic",
        unit="mmHg",
        patterns=[
            rf"(?i)LV{_SEP}{_NUM}\s*/",
            rf"(?i)(?:left\s+ventricl(?:e|ar))\s+(?:systolic\s+)?(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=50.0,
        value_max=250.0,
    ),
    # LV diastolic
    MeasurementDef(
        name="LV Diastolic Pressure",
        abbreviation="LV_diastolic",
        unit="mmHg",
        patterns=[
            rf"(?i)LV\s+\d+\s*/\s*{_NUM}",
            rf"(?i)(?:left\s+ventricl(?:e|ar))\s+(?:end[- ]?)?diastolic\s+(?:pressure)?{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=0.0,
        value_max=50.0,
    ),
    # LVEDP
    MeasurementDef(
        name="LV End-Diastolic Pressure",
        abbreviation="LVEDP",
        unit="mmHg",
        patterns=[
            rf"(?i)LVEDP{_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)(?:LV|left\s+ventricl(?:e|ar))\s+end[- ]?diastolic\s+pressure{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=0.0,
        value_max=50.0,
    ),
    # --- IVUS ---
    # MLA
    MeasurementDef(
        name="Minimum Lumen Area",
        abbreviation="MLA",
        unit="mm\u00b2",
        patterns=[
            rf"(?i)MLA{_SEP}{_NUM}\s*(?:mm2|mm\u00b2)?",
            rf"(?i)(?:minimum|min)\s+lumen\s+area{_SEP}{_NUM}\s*(?:mm2|mm\u00b2)?",
        ],
        value_min=0.5,
        value_max=25.0,
    ),
]


# --- Stenosis patterns (multi-match, not single-value) ---

# Matches patterns like "LAD 50%", "RCA 70-80%", "LCx: 40%", "Left main 30%"
_STENOSIS_RE = re.compile(
    r"(?i)"
    r"(?P<vessel>(?:LAD|LCx|RCA|left\s+main|LM|"
    r"(?:left\s+anterior\s+descending)|"
    r"(?:left\s+circumflex)|"
    r"(?:right\s+coronary(?:\s+artery)?)|"
    r"(?:diagonal|D1|D2)|"
    r"(?:obtuse\s+marginal|OM|OM1|OM2)|"
    r"(?:ramus)|"
    r"(?:PDA|posterior\s+descending)|"
    r"(?:PLB|posterolateral)|"
    r"(?:SVG(?:\s+to\s+\w+)?)|"
    r"(?:LIMA(?:\s+to\s+\w+)?)|"
    r"(?:RIMA(?:\s+to\s+\w+)?)|"
    r"(?:graft(?:\s+to\s+\w+)?)))"
    r"\s*[:\-]?\s*"
    r"(?P<pct1>\d+)\s*(?:[-\u2013to]+\s*(?P<pct2>\d+)\s*)?%",
)

# Calcium arc pattern: "calcium arc 270 degrees" or "270° arc"
_CALCIUM_ARC_RE = re.compile(
    r"(?i)(?:calcium\s+arc|arc\s+(?:of\s+)?calcium)\s*[:\-]?\s*"
    r"(?P<value>\d+)\s*(?:degrees?|\u00b0)?",
)

# Obstruction percentage from IVUS: "obstruction 75%" or "area stenosis 80%"
_IVUS_OBSTRUCTION_RE = re.compile(
    r"(?i)(?:obstruction|area\s+stenosis)\s*[:\-=]?\s*"
    r"(?P<value>\d+\.?\d*)\s*%",
)


# Total occlusion pattern: "LAD total occlusion", "RCA CTO", "SVG to LAD occluded"
_TOTAL_OCCLUSION_RE = re.compile(
    r"(?i)(?P<vessel>"
    r"(?:LAD|LCx|RCA|left\s+main|LM|"
    r"(?:left\s+anterior\s+descending)|"
    r"(?:left\s+circumflex)|"
    r"(?:right\s+coronary(?:\s+artery)?)|"
    r"(?:SVG|LIMA|RIMA|graft)(?:\s+to\s+\w+)?)"
    r")\s*(?:[:\-]?\s*)"
    r"(?:total(?:ly)?\s+occlu(?:ded|sion)|100\s*%\s*(?:occlu(?:ded|sion))?|"
    r"CTO|completely?\s+(?:blocked|occluded))",
)


# --- Systolic/Diastolic pair pattern ---
# Matches "RV 30/8", "PA 25/12", "AO 120/80", "LV 130/12"
_SD_PAIR_RE = re.compile(
    r"(?i)(?P<chamber>RA|RV|PA|AO|LV)\s*[:\s=]+\s*"
    r"(?P<systolic>\d+)\s*/\s*(?P<diastolic>\d+)"
)


def _normalize_vessel(raw: str) -> str:
    """Normalize vessel name to standard abbreviation."""
    mapping = {
        "left anterior descending": "LAD",
        "left circumflex": "LCx",
        "right coronary artery": "RCA",
        "right coronary": "RCA",
        "left main": "Left Main",
        "lm": "Left Main",
        "diagonal": "Diagonal",
        "d1": "D1",
        "d2": "D2",
        "obtuse marginal": "OM",
        "om1": "OM1",
        "om2": "OM2",
        "ramus": "Ramus",
        "posterior descending": "PDA",
        "pda": "PDA",
        "posterolateral": "PLB",
        "plb": "PLB",
        "svg": "SVG",
        "lima": "LIMA",
        "rima": "RIMA",
        "graft": "Graft",
        "cabg": "CABG",
    }
    lower = raw.strip().lower()
    if lower in mapping:
        return mapping[lower]
    return raw.strip().upper()


def extract_measurements(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """Extract all recognized measurements from the report text."""
    results: list[RawMeasurement] = []
    seen: set[str] = set()

    # 1. Extract systolic/diastolic pairs first (e.g., "RV 30/8")
    for match in _SD_PAIR_RE.finditer(full_text):
        chamber = match.group("chamber").upper()
        systolic = float(match.group("systolic"))
        diastolic = float(match.group("diastolic"))
        page_num = _find_page(match.group(), pages)

        sys_abbr = f"{chamber}_systolic"
        dia_abbr = f"{chamber}_diastolic"

        if sys_abbr not in seen:
            # Look up the definition for sanity-check bounds
            sys_def = _find_def(sys_abbr)
            if sys_def is None or (sys_def.value_min <= systolic <= sys_def.value_max):
                results.append(
                    RawMeasurement(
                        name=f"{chamber} Systolic Pressure",
                        abbreviation=sys_abbr,
                        value=systolic,
                        unit="mmHg",
                        raw_text=match.group().strip(),
                        page_number=page_num,
                    )
                )
                seen.add(sys_abbr)

        if dia_abbr not in seen:
            dia_def = _find_def(dia_abbr)
            if dia_def is None or (dia_def.value_min <= diastolic <= dia_def.value_max):
                results.append(
                    RawMeasurement(
                        name=f"{chamber} Diastolic Pressure",
                        abbreviation=dia_abbr,
                        value=diastolic,
                        unit="mmHg",
                        raw_text=match.group().strip(),
                        page_number=page_num,
                    )
                )
                seen.add(dia_abbr)

    # 2. Extract individual measurements from MEASUREMENT_DEFS
    for mdef in MEASUREMENT_DEFS:
        if mdef.abbreviation in seen:
            continue

        for pattern in mdef.patterns:
            match = re.search(pattern, full_text)
            if match:
                try:
                    value = float(match.group("value"))
                except (ValueError, IndexError):
                    continue

                if not (mdef.value_min <= value <= mdef.value_max):
                    continue

                page_num = _find_page(match.group(), pages)
                results.append(
                    RawMeasurement(
                        name=mdef.name,
                        abbreviation=mdef.abbreviation,
                        value=value,
                        unit=mdef.unit,
                        raw_text=match.group().strip(),
                        page_number=page_num,
                    )
                )
                seen.add(mdef.abbreviation)
                break

    # 3. Extract stenosis percentages (can have multiple vessels)
    for match in _STENOSIS_RE.finditer(full_text):
        vessel = _normalize_vessel(match.group("vessel"))
        pct1 = int(match.group("pct1"))
        pct2_str = match.group("pct2")

        if pct2_str:
            # Range like "70-80%", take midpoint
            pct2 = int(pct2_str)
            value = (pct1 + pct2) / 2.0
        else:
            value = float(pct1)

        if not (0 <= value <= 100):
            continue

        abbr = f"stenosis_{vessel}"
        if abbr in seen:
            continue

        page_num = _find_page(match.group(), pages)
        results.append(
            RawMeasurement(
                name=f"{vessel} Stenosis",
                abbreviation=abbr,
                value=value,
                unit="%",
                raw_text=match.group().strip(),
                page_number=page_num,
            )
        )
        seen.add(abbr)

    # 4. Extract IVUS calcium arc (renumbered below: 5=total occlusion, 6=IVUS obstruction)
    arc_match = _CALCIUM_ARC_RE.search(full_text)
    if arc_match and "calcium_arc" not in seen:
        arc_val = float(arc_match.group("value"))
        if 0 <= arc_val <= 360:
            page_num = _find_page(arc_match.group(), pages)
            results.append(
                RawMeasurement(
                    name="Calcium Arc",
                    abbreviation="calcium_arc",
                    value=arc_val,
                    unit="\u00b0",
                    raw_text=arc_match.group().strip(),
                    page_number=page_num,
                )
            )
            seen.add("calcium_arc")

    # 5. Extract total occlusions
    for match in _TOTAL_OCCLUSION_RE.finditer(full_text):
        vessel = _normalize_vessel(match.group("vessel"))
        abbr = f"stenosis_{vessel}"
        if abbr in seen:
            continue
        page_num = _find_page(match.group(), pages)
        results.append(
            RawMeasurement(
                name=f"{vessel} Stenosis",
                abbreviation=abbr,
                value=100.0,
                unit="%",
                raw_text=match.group().strip(),
                page_number=page_num,
            )
        )
        seen.add(abbr)

    # 6. Extract IVUS obstruction percentage
    obs_match = _IVUS_OBSTRUCTION_RE.search(full_text)
    if obs_match and "ivus_obstruction" not in seen:
        obs_val = float(obs_match.group("value"))
        if 0 <= obs_val <= 100:
            page_num = _find_page(obs_match.group(), pages)
            results.append(
                RawMeasurement(
                    name="IVUS Obstruction",
                    abbreviation="ivus_obstruction",
                    value=obs_val,
                    unit="%",
                    raw_text=obs_match.group().strip(),
                    page_number=page_num,
                )
            )
            seen.add("ivus_obstruction")

    return results


def _find_def(abbreviation: str) -> Optional[MeasurementDef]:
    """Find a MeasurementDef by abbreviation."""
    for mdef in MEASUREMENT_DEFS:
        if mdef.abbreviation == abbreviation:
            return mdef
    return None


def _find_page(
    snippet: str,
    pages: list[PageExtractionResult],
) -> Optional[int]:
    """Find which page contains the matched text snippet."""
    normalized = " ".join(snippet.split())
    for page in pages:
        page_normalized = " ".join(page.text.split())
        if normalized in page_normalized:
            return page.page_number
    return None
