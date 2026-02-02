"""
Regex-based measurement extraction for carotid doppler / cerebrovascular
duplex reports.

Handles the tabular format commonly seen in carotid reports where
Right and Left measurements are listed side-by-side for each segment
(Dist CCA, Prox ICA, Mid ICA, Dist ICA).
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


# --- Inline / labeled measurements (non-tabular) ---
MEASUREMENT_DEFS: list[MeasurementDef] = [
    # ICA/CCA velocity ratio
    MeasurementDef(
        name="Right ICA/CCA Velocity Ratio",
        abbreviation="R_ICA_CCA_Ratio",
        unit="",
        patterns=[
            r"(?i)(?:right|rt\.?)\s+.*?ICA[/\\]CCA\s+(?:velocity\s+)?ratio\s*[:\s=]*(?P<value>\d+\.?\d*)",
            r"(?P<value>\d+\.?\d*)\s+ICA[/\\]CCA\s+velocity\s+ratio\s+(?:\d+\.?\d*)",
        ],
        value_min=0.3,
        value_max=10.0,
    ),
    MeasurementDef(
        name="Left ICA/CCA Velocity Ratio",
        abbreviation="L_ICA_CCA_Ratio",
        unit="",
        patterns=[
            r"(?i)(?:left|lt\.?)\s+.*?ICA[/\\]CCA\s+(?:velocity\s+)?ratio\s*[:\s=]*(?P<value>\d+\.?\d*)",
            r"ICA[/\\]CCA\s+velocity\s+ratio\s+(?P<value>\d+\.?\d*)",
        ],
        value_min=0.3,
        value_max=10.0,
    ),
    # Intima-media thickness
    MeasurementDef(
        name="Right IMT",
        abbreviation="R_IMT",
        unit="mm",
        patterns=[
            rf"(?i)(?:right|rt\.?)\s+(?:CCA\s+)?(?:intima[- ]media\s+thickness|IMT){_SEP}{_NUM}\s*(?:mm)?",
        ],
        value_min=0.2,
        value_max=3.0,
    ),
    MeasurementDef(
        name="Left IMT",
        abbreviation="L_IMT",
        unit="mm",
        patterns=[
            rf"(?i)(?:left|lt\.?)\s+(?:CCA\s+)?(?:intima[- ]media\s+thickness|IMT){_SEP}{_NUM}\s*(?:mm)?",
        ],
        value_min=0.2,
        value_max=3.0,
    ),
]


# Tabular segment definitions: (segment label regex, abbreviation prefix)
_SEGMENTS = [
    (r"Dist\s+CCA", "Dist_CCA"),
    (r"Prox\s+ICA", "Prox_ICA"),
    (r"Mid\s+ICA", "Mid_ICA"),
    (r"Dist\s+ICA", "Dist_ICA"),
    (r"(?:Prox\s+)?CCA", "CCA"),
    (r"Bulb|Bifurcation", "Bulb"),
    (r"(?:Prox\s+)?ECA", "ECA"),
]


def _extract_tabular_velocities(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """
    Extract PSV and EDV values from the tabular layout commonly seen in
    carotid reports. The table typically has the format:

        Right               Carotid             Left
        PSV      EDV                       PSV      EDV
        63.8     4.0    Dist CCA          66.9     7.4
        82.0    16.8    Prox ICA          96.6    14.9
        ...

    We look for each segment label and capture the surrounding numbers.
    """
    results: list[RawMeasurement] = []

    for seg_pattern, seg_abbr in _SEGMENTS:
        # Pattern: numbers before the segment label (Right side) and after (Left side)
        # Right PSV, Right EDV, <Segment>, Left PSV, Left EDV
        pattern = (
            r"(\d+\.?\d*)\s+(?:cm/s\s+)?(\d+\.?\d*)\s+(?:cm/s\s+)?"
            + seg_pattern
            + r"\s+(\d+\.?\d*)\s+(?:cm/s\s+)?(\d+\.?\d*)"
        )
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            r_psv = float(match.group(1))
            r_edv = float(match.group(2))
            l_psv = float(match.group(3))
            l_edv = float(match.group(4))
            page_num = _find_page(match.group(), pages)

            if 5.0 <= r_psv <= 500.0:
                results.append(RawMeasurement(
                    name=f"Right {seg_abbr} PSV",
                    abbreviation=f"R_{seg_abbr}_PSV",
                    value=r_psv,
                    unit="cm/s",
                    raw_text=match.group().strip(),
                    page_number=page_num,
                ))
            if 0.0 <= r_edv <= 200.0:
                results.append(RawMeasurement(
                    name=f"Right {seg_abbr} EDV",
                    abbreviation=f"R_{seg_abbr}_EDV",
                    value=r_edv,
                    unit="cm/s",
                    raw_text=match.group().strip(),
                    page_number=page_num,
                ))
            if 5.0 <= l_psv <= 500.0:
                results.append(RawMeasurement(
                    name=f"Left {seg_abbr} PSV",
                    abbreviation=f"L_{seg_abbr}_PSV",
                    value=l_psv,
                    unit="cm/s",
                    raw_text=match.group().strip(),
                    page_number=page_num,
                ))
            if 0.0 <= l_edv <= 200.0:
                results.append(RawMeasurement(
                    name=f"Left {seg_abbr} EDV",
                    abbreviation=f"L_{seg_abbr}_EDV",
                    value=l_edv,
                    unit="cm/s",
                    raw_text=match.group().strip(),
                    page_number=page_num,
                ))

    return results


def _extract_ratio_from_table(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """Extract ICA/CCA velocity ratio from tabular layout."""
    results: list[RawMeasurement] = []

    pattern = r"(\d+\.?\d*)\s+ICA[/\\]CCA\s+velocity\s+ratio\s+(\d+\.?\d*)"
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        r_ratio = float(match.group(1))
        l_ratio = float(match.group(2))
        page_num = _find_page(match.group(), pages)

        if 0.3 <= r_ratio <= 10.0:
            results.append(RawMeasurement(
                name="Right ICA/CCA Velocity Ratio",
                abbreviation="R_ICA_CCA_Ratio",
                value=r_ratio,
                unit="",
                raw_text=match.group().strip(),
                page_number=page_num,
            ))
        if 0.3 <= l_ratio <= 10.0:
            results.append(RawMeasurement(
                name="Left ICA/CCA Velocity Ratio",
                abbreviation="L_ICA_CCA_Ratio",
                value=l_ratio,
                unit="",
                raw_text=match.group().strip(),
                page_number=page_num,
            ))

    return results


def extract_measurements(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """Extract all recognized measurements from the report text."""
    results: list[RawMeasurement] = []
    seen: set[str] = set()

    # 1. Tabular velocities (primary extraction for carotid reports)
    tabular = _extract_tabular_velocities(full_text, pages)
    for m in tabular:
        if m.abbreviation not in seen:
            results.append(m)
            seen.add(m.abbreviation)

    # 2. Tabular ratio
    ratios = _extract_ratio_from_table(full_text, pages)
    for m in ratios:
        if m.abbreviation not in seen:
            results.append(m)
            seen.add(m.abbreviation)

    # 3. Inline / labeled measurements
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
