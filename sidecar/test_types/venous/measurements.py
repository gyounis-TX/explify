"""
Regex-based measurement extraction for lower extremity venous duplex
scan reports.

Handles tabular format with Right/Left columns containing reflux time
and diameter for GSV segments, plus inline measurements.
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


# GSV segments in typical report order
_GSV_SEGMENTS = [
    (r"GSV\s+Prox", "GSV_Prox"),
    (r"GSV\s+Mid", "GSV_Mid"),
    (r"GSV\s+Dist", "GSV_Dist"),
]


def _extract_gsv_table(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """
    Extract reflux time and diameter from GSV table:
        Right                    Leg         Left
        Reflux Time  Diameter   Mapping    Reflux Time  Diameter
        0 ms         0.48 mm    GSV Prox   131 ms       0.46 mm
    """
    results: list[RawMeasurement] = []

    for seg_pattern, seg_abbr in _GSV_SEGMENTS:
        # Pattern: R_reflux ms  R_diameter mm  <Segment>  L_reflux ms  L_diameter mm
        pattern = (
            r"(\d+)\s*ms\s+(\d+\.?\d*)\s*mm\s+"
            + seg_pattern
            + r"\s+(\d+)\s*ms\s+(\d+\.?\d*)\s*mm"
        )
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            r_reflux = float(match.group(1))
            r_diameter = float(match.group(2))
            l_reflux = float(match.group(3))
            l_diameter = float(match.group(4))
            page_num = _find_page(match.group(), pages)

            results.append(RawMeasurement(
                name=f"Right {seg_abbr} Reflux Time",
                abbreviation=f"R_{seg_abbr}_Reflux",
                value=r_reflux,
                unit="ms",
                raw_text=match.group().strip(),
                page_number=page_num,
            ))
            results.append(RawMeasurement(
                name=f"Right {seg_abbr} Diameter",
                abbreviation=f"R_{seg_abbr}_Diam",
                value=r_diameter,
                unit="mm",
                raw_text=match.group().strip(),
                page_number=page_num,
            ))
            results.append(RawMeasurement(
                name=f"Left {seg_abbr} Reflux Time",
                abbreviation=f"L_{seg_abbr}_Reflux",
                value=l_reflux,
                unit="ms",
                raw_text=match.group().strip(),
                page_number=page_num,
            ))
            results.append(RawMeasurement(
                name=f"Left {seg_abbr} Diameter",
                abbreviation=f"L_{seg_abbr}_Diam",
                value=l_diameter,
                unit="mm",
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

    for m in _extract_gsv_table(full_text, pages):
        if m.abbreviation not in seen:
            results.append(m)
            seen.add(m.abbreviation)

    return results


def _find_page(
    snippet: str,
    pages: list[PageExtractionResult],
) -> Optional[int]:
    normalized = " ".join(snippet.split())
    for page in pages:
        page_normalized = " ".join(page.text.split())
        if normalized in page_normalized:
            return page.page_number
    return None
