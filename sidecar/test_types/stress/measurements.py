"""
Regex-based measurement extraction for exercise stress test reports.
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
    name: str
    abbreviation: str
    unit: str
    patterns: list[str]
    value_min: float = 0.0
    value_max: float = 999.0


_NUM = r"(?P<value>\d+\.?\d*)"
_SEP = r"[\s:=]+\s*"

MEASUREMENT_DEFS: list[MeasurementDef] = [
    # --- METs ---
    MeasurementDef(
        name="Metabolic Equivalents",
        abbreviation="METs",
        unit="METs",
        patterns=[
            rf"(?i)METs?{_SEP}{_NUM}",
            rf"(?i)metabolic\s+equivalents?{_SEP}{_NUM}",
            rf"(?i)exercise\s+capacity{_SEP}{_NUM}\s*METs?",
            rf"(?i)functional\s+capacity{_SEP}{_NUM}\s*METs?",
            rf"(?i){_NUM}\s*METs?\s+(?:achieved|attained|reached)",
        ],
        value_min=1.0,
        value_max=25.0,
    ),
    # --- Heart Rate ---
    MeasurementDef(
        name="Resting Heart Rate",
        abbreviation="Rest_HR",
        unit="bpm",
        patterns=[
            rf"(?i)resting\s+(?:heart\s+rate|HR|pulse){_SEP}{_NUM}\s*(?:bpm)?",
            rf"(?i)(?:baseline|pre[- ]?exercise)\s+(?:heart\s+rate|HR){_SEP}{_NUM}\s*(?:bpm)?",
            rf"(?i)rest(?:ing)?\s+HR{_SEP}{_NUM}\s*(?:bpm)?",
        ],
        value_min=30.0,
        value_max=150.0,
    ),
    MeasurementDef(
        name="Peak Heart Rate",
        abbreviation="Peak_HR",
        unit="bpm",
        patterns=[
            rf"(?i)peak\s+(?:heart\s+rate|HR|pulse){_SEP}{_NUM}\s*(?:bpm)?",
            rf"(?i)max(?:imum|imal)?\s+(?:heart\s+rate|HR){_SEP}{_NUM}\s*(?:bpm)?",
            rf"(?i)(?:heart\s+rate|HR)\s+(?:at\s+)?peak{_SEP}{_NUM}\s*(?:bpm)?",
        ],
        value_min=50.0,
        value_max=250.0,
    ),
    MeasurementDef(
        name="% Max Predicted Heart Rate",
        abbreviation="MPHR%",
        unit="%",
        patterns=[
            rf"(?i){_NUM}\s*%\s*(?:of\s+)?(?:MPHR|max(?:imum|imal)?\s+predicted)",
            rf"(?i)%\s*(?:MPHR|max\s+predicted){_SEP}{_NUM}",
            rf"(?i)(?:MPHR|max(?:imum)?\s+predicted\s+(?:heart\s+rate|HR)){_SEP}{_NUM}\s*%",
            rf"(?i)(?:achieved|attained|reached)\s+{_NUM}\s*%\s*(?:of\s+)?(?:max|MPHR|predicted)",
        ],
        value_min=30.0,
        value_max=120.0,
    ),
    # --- Blood Pressure ---
    MeasurementDef(
        name="Resting Systolic BP",
        abbreviation="Rest_SBP",
        unit="mmHg",
        patterns=[
            rf"(?i)resting\s+(?:blood\s+pressure|BP|SBP){_SEP}{_NUM}\s*/",
            rf"(?i)(?:baseline|pre[- ]?exercise)\s+(?:blood\s+pressure|BP){_SEP}{_NUM}\s*/",
            rf"(?i)rest(?:ing)?\s+SBP{_SEP}{_NUM}",
        ],
        value_min=60.0,
        value_max=250.0,
    ),
    MeasurementDef(
        name="Peak Systolic BP",
        abbreviation="Peak_SBP",
        unit="mmHg",
        patterns=[
            rf"(?i)peak\s+(?:blood\s+pressure|BP|SBP){_SEP}{_NUM}\s*/",
            rf"(?i)max(?:imum|imal)?\s+(?:blood\s+pressure|BP|SBP){_SEP}{_NUM}",
            rf"(?i)(?:blood\s+pressure|BP)\s+(?:at\s+)?peak{_SEP}{_NUM}\s*/",
            rf"(?i)peak\s+SBP{_SEP}{_NUM}",
        ],
        value_min=80.0,
        value_max=300.0,
    ),
    # --- Exercise Duration ---
    MeasurementDef(
        name="Exercise Duration",
        abbreviation="Exercise_Duration",
        unit="min",
        patterns=[
            rf"(?i)(?:exercise|total)\s+(?:duration|time){_SEP}{_NUM}\s*(?:min(?:utes?)?)?",
            rf"(?i)duration\s+of\s+exercise{_SEP}{_NUM}\s*(?:min(?:utes?)?)?",
            rf"(?i)exercised?\s+(?:for\s+)?{_NUM}\s*min(?:utes?)?",
            rf"(?i)treadmill\s+time{_SEP}{_NUM}\s*(?:min(?:utes?)?)?",
        ],
        value_min=0.5,
        value_max=30.0,
    ),
    # --- ST Changes ---
    MeasurementDef(
        name="ST Depression",
        abbreviation="ST_Depression",
        unit="mm",
        patterns=[
            rf"(?i)ST\s+(?:segment\s+)?depression{_SEP}{_NUM}\s*(?:mm)?",
            rf"(?i){_NUM}\s*mm\s+(?:of\s+)?ST\s+depression",
            rf"(?i)ST\s+(?:changes?\s+(?:of\s+)?)?{_NUM}\s*mm\s+depression",
        ],
        value_min=0.0,
        value_max=10.0,
    ),
    # --- Duke Treadmill Score ---
    MeasurementDef(
        name="Duke Treadmill Score",
        abbreviation="Duke_Score",
        unit="",
        patterns=[
            rf"(?i)duke\s+(?:treadmill\s+)?score{_SEP}(?P<value>-?\d+\.?\d*)",
            rf"(?i)DTS{_SEP}(?P<value>-?\d+\.?\d*)",
        ],
        value_min=-25.0,
        value_max=25.0,
    ),
    # --- Rate-Pressure Product ---
    MeasurementDef(
        name="Rate-Pressure Product",
        abbreviation="RPP",
        unit="",
        patterns=[
            rf"(?i)(?:rate[- ]?pressure\s+product|RPP|double\s+product){_SEP}{_NUM}",
        ],
        value_min=5000.0,
        value_max=50000.0,
    ),
]


def extract_measurements(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """Extract all recognized measurements from a stress test report."""
    results: list[RawMeasurement] = []
    seen: set[str] = set()

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
