"""
Regex-based measurement extraction for echocardiogram reports.

Uses a data-driven approach: each measurement is defined with multiple
regex patterns, sanity bounds, and metadata. Patterns use named capture
groups (?P<value>...) for the numeric value.
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
    # --- LV Dimensions ---
    MeasurementDef(
        name="LV Internal Diameter, Diastole",
        abbreviation="LVIDd",
        unit="cm",
        patterns=[
            rf"(?i)LVIDd{_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)LV\s*\(D\){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)LV\s+(?:internal\s+)?(?:diameter|dimension)[\s,]*(?:diastol|end[- ]?diastol){_SEP}{_NUM}\s*(?:cm|mm)?",
        ],
        value_min=1.0,
        value_max=10.0,
    ),
    MeasurementDef(
        name="LV Internal Diameter, Systole",
        abbreviation="LVIDs",
        unit="cm",
        patterns=[
            rf"(?i)LVIDs{_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)LV\s*\(S\){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)LV\s+(?:internal\s+)?(?:diameter|dimension)[\s,]*(?:systol|end[- ]?systol){_SEP}{_NUM}\s*(?:cm|mm)?",
        ],
        value_min=1.0,
        value_max=8.0,
    ),
    MeasurementDef(
        name="Interventricular Septum, Diastole",
        abbreviation="IVSd",
        unit="cm",
        patterns=[
            rf"(?i)IVSd{_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)IVS\s*\(D\){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)(?:interventricular|IV)\s+sept(?:um|al)[\s,]*(?:diastol|d\.?){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)septal\s+(?:wall\s+)?thickness{_SEP}{_NUM}\s*(?:cm|mm)?",
        ],
        value_min=0.3,
        value_max=3.0,
    ),
    MeasurementDef(
        name="LV Posterior Wall, Diastole",
        abbreviation="LVPWd",
        unit="cm",
        patterns=[
            rf"(?i)LVPWd{_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)LVPW\s*\(D\){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)(?:LV\s+)?(?:posterior|post)\s+wall[\s,]*(?:diastol|d\.?){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)PW\s*d{_SEP}{_NUM}\s*(?:cm|mm)?",
        ],
        value_min=0.3,
        value_max=3.0,
    ),
    # --- LV Function ---
    MeasurementDef(
        name="Left Ventricular Ejection Fraction",
        abbreviation="LVEF",
        unit="%",
        patterns=[
            rf"(?i)(?:LVEF|EF){_SEP}{_NUM}\s*%?",
            rf"(?i)ejection\s+fraction{_SEP}{_NUM}\s*%?",
            rf"(?i)(?:LVEF|EF|ejection\s+fraction)\s+(?:is\s+|of\s+|estimated\s+(?:at\s+)?)?{_NUM}\s*%?",
        ],
        value_min=5.0,
        value_max=95.0,
    ),
    MeasurementDef(
        name="Fractional Shortening",
        abbreviation="FS",
        unit="%",
        patterns=[
            rf"(?i)(?:fractional\s+shortening|FS){_SEP}{_NUM}\s*%?",
        ],
        value_min=5.0,
        value_max=60.0,
    ),
    # --- Left Atrium ---
    MeasurementDef(
        name="Left Atrial Diameter",
        abbreviation="LA",
        unit="cm",
        patterns=[
            rf"(?i)(?:LA|left\s+atri(?:um|al))\s+(?:diam(?:eter)?|dimension|size){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)LA{_SEP}{_NUM}\s*cm",
        ],
        value_min=1.0,
        value_max=8.0,
    ),
    MeasurementDef(
        name="LA Volume Index",
        abbreviation="LAVI",
        unit="mL/m2",
        patterns=[
            rf"(?i)(?:LA\s+volume\s+index|LAVI){_SEP}{_NUM}\s*(?:ml\/m2|mL\/m2|ml\/m\u00b2)?",
            rf"(?i)left\s+atrial\s+volume\s+index{_SEP}{_NUM}",
        ],
        value_min=10.0,
        value_max=80.0,
    ),
    # --- Right Side ---
    MeasurementDef(
        name="RV Basal Diameter",
        abbreviation="RVD",
        unit="cm",
        patterns=[
            rf"(?i)(?:RV|right\s+ventricl(?:e|ar))\s+(?:basal\s+)?(?:diameter|dimension){_SEP}{_NUM}\s*(?:cm|mm)?",
        ],
        value_min=1.0,
        value_max=6.0,
    ),
    MeasurementDef(
        name="RA Area",
        abbreviation="RAA",
        unit="cm2",
        patterns=[
            rf"(?i)(?:RA|right\s+atri(?:um|al))\s+area{_SEP}{_NUM}\s*(?:cm2|cm\u00b2)?",
        ],
        value_min=5.0,
        value_max=40.0,
    ),
    # --- Aortic Root ---
    MeasurementDef(
        name="Aortic Root Diameter",
        abbreviation="AoRoot",
        unit="cm",
        patterns=[
            rf"(?i)aort(?:a|ic)\s+(?:root|sinus){_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)sinus\s+(?:of\s+)?valsalva{_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)Ao\s+root{_SEP}{_NUM}\s*(?:cm|mm)?",
        ],
        value_min=1.0,
        value_max=6.0,
    ),
    # --- Valvular ---
    MeasurementDef(
        name="Aortic Valve Area",
        abbreviation="AVA",
        unit="cm2",
        patterns=[
            rf"(?i)(?:aortic\s+valve\s+area|AVA){_SEP}{_NUM}\s*(?:cm2|cm\u00b2)?",
        ],
        value_min=0.3,
        value_max=5.0,
    ),
    MeasurementDef(
        name="Mitral Valve E/A Ratio",
        abbreviation="E/A",
        unit="",
        patterns=[
            rf"(?i)E\/A\s*(?:ratio)?{_SEP}{_NUM}",
            rf"(?i)mitral\s+(?:inflow\s+)?E\/A{_SEP}{_NUM}",
        ],
        value_min=0.3,
        value_max=4.0,
    ),
    MeasurementDef(
        name="E/e' Ratio",
        abbreviation="E/e'",
        unit="",
        patterns=[
            rf"(?i)E\/e['\u2019]\s*(?:ratio)?{_SEP}{_NUM}",
            rf"(?i)E\/e['\u2019]\s*(?:\(average\))?\s*{_SEP}{_NUM}",
        ],
        value_min=2.0,
        value_max=30.0,
    ),
    MeasurementDef(
        name="Tricuspid Regurgitation Velocity",
        abbreviation="TRV",
        unit="m/s",
        patterns=[
            rf"(?i)(?:TR|tricuspid\s+regurgit(?:ation|ant))\s+(?:peak\s+)?velocity{_SEP}{_NUM}\s*(?:m\/s)?",
            rf"(?i)TR\s+(?:Vmax|jet\s+velocity){_SEP}{_NUM}\s*(?:m\/s)?",
        ],
        value_min=1.0,
        value_max=6.0,
    ),
    # --- Hemodynamics ---
    MeasurementDef(
        name="RV Systolic Pressure",
        abbreviation="RVSP",
        unit="mmHg",
        patterns=[
            rf"(?i)RVSP{_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)(?:RV|right\s+ventricular)\s+systolic\s+pressure{_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)(?:PA|pulmonary\s+artery)\s+systolic\s+pressure{_SEP}{_NUM}\s*(?:mmHg)?",
            rf"(?i)PASP{_SEP}{_NUM}\s*(?:mmHg)?",
        ],
        value_min=10.0,
        value_max=120.0,
    ),
    # --- Diastolic Function ---
    MeasurementDef(
        name="Mitral E Velocity",
        abbreviation="MV_E",
        unit="cm/s",
        patterns=[
            rf"(?i)(?:mitral\s+)?E\s+(?:wave\s+)?velocity{_SEP}{_NUM}\s*(?:cm\/s|m\/s)?",
            rf"(?i)E\s+vel(?:ocity)?{_SEP}{_NUM}\s*(?:cm\/s|m\/s)?",
        ],
        value_min=20.0,
        value_max=200.0,
    ),
    MeasurementDef(
        name="Mitral A Velocity",
        abbreviation="MV_A",
        unit="cm/s",
        patterns=[
            rf"(?i)(?:mitral\s+)?A\s+(?:wave\s+)?velocity{_SEP}{_NUM}\s*(?:cm\/s|m\/s)?",
            rf"(?i)A\s+vel(?:ocity)?{_SEP}{_NUM}\s*(?:cm\/s|m\/s)?",
        ],
        value_min=20.0,
        value_max=200.0,
    ),
    MeasurementDef(
        name="Deceleration Time",
        abbreviation="DT",
        unit="ms",
        patterns=[
            rf"(?i)(?:deceleration|decel)\s+time{_SEP}{_NUM}\s*(?:ms|msec)?",
            rf"(?i)DT{_SEP}{_NUM}\s*(?:ms|msec)?",
        ],
        value_min=50.0,
        value_max=500.0,
    ),
    MeasurementDef(
        name="IVRT",
        abbreviation="IVRT",
        unit="ms",
        patterns=[
            rf"(?i)IVRT{_SEP}{_NUM}\s*(?:ms|msec)?",
            rf"(?i)isovolumic\s+relaxation\s+time{_SEP}{_NUM}\s*(?:ms|msec)?",
        ],
        value_min=30.0,
        value_max=200.0,
    ),
    MeasurementDef(
        name="e' Septal",
        abbreviation="e'_septal",
        unit="cm/s",
        patterns=[
            rf"(?i)e['\u2019]\s*(?:\()?septal(?:\))?{_SEP}{_NUM}\s*(?:cm\/s)?",
            rf"(?i)septal\s+e['\u2019]{_SEP}{_NUM}\s*(?:cm\/s)?",
            rf"(?i)medial\s+e['\u2019]{_SEP}{_NUM}\s*(?:cm\/s)?",
        ],
        value_min=2.0,
        value_max=20.0,
    ),
    MeasurementDef(
        name="e' Lateral",
        abbreviation="e'_lateral",
        unit="cm/s",
        patterns=[
            rf"(?i)e['\u2019]\s*(?:\()?lateral(?:\))?{_SEP}{_NUM}\s*(?:cm\/s)?",
            rf"(?i)lateral\s+e['\u2019]{_SEP}{_NUM}\s*(?:cm\/s)?",
        ],
        value_min=2.0,
        value_max=25.0,
    ),
    MeasurementDef(
        name="TAPSE",
        abbreviation="TAPSE",
        unit="cm",
        patterns=[
            rf"(?i)TAPSE{_SEP}{_NUM}\s*(?:cm|mm)?",
            rf"(?i)tricuspid\s+annular\s+plane\s+systolic\s+excursion{_SEP}{_NUM}",
        ],
        value_min=0.5,
        value_max=4.0,
    ),
]

# EF range pattern: "LVEF 55-60%" or "EF: 55 - 60 %"
_EF_RANGE_RE = re.compile(
    r"(?i)(?:LVEF|EF|ejection\s+fraction)"
    r"[\s:=]+\s*"
    r"(\d+\.?\d*)\s*[-\u2013to]+\s*(\d+\.?\d*)\s*%?",
)


def extract_measurements(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """Extract all recognized measurements from the report text."""
    results: list[RawMeasurement] = []
    seen: set[str] = set()

    # Special case: EF range ("LVEF 55-60%") -> take midpoint
    ef_range_match = _EF_RANGE_RE.search(full_text)
    if ef_range_match:
        low = float(ef_range_match.group(1))
        high = float(ef_range_match.group(2))
        if 5.0 <= low <= 95.0 and 5.0 <= high <= 95.0 and low < high:
            midpoint = (low + high) / 2.0
            page_num = _find_page(ef_range_match.group(), pages)
            results.append(
                RawMeasurement(
                    name="Left Ventricular Ejection Fraction",
                    abbreviation="LVEF",
                    value=round(midpoint, 1),
                    unit="%",
                    raw_text=ef_range_match.group().strip(),
                    page_number=page_num,
                )
            )
            seen.add("LVEF")

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

    return results


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
