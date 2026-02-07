"""
Measurement extractor wrapper for generic lab test types.

Matches the MeasurementExtractor signature (text, gender) -> list[ParsedMeasurement]
so it can be assigned to GenericTestType instances in the registry.
"""

from __future__ import annotations

from typing import Optional

from api.analysis_models import ParsedMeasurement, PriorValue
from .measurements import extract_measurements
from .reference_ranges import classify_measurement


def extract_lab_measurements(
    text: str, gender: Optional[str] = None
) -> list[ParsedMeasurement]:
    """Extract and classify lab measurements from raw text.

    Uses the comprehensive MEASUREMENT_DEFS regex patterns and reference
    ranges. Designed for text-paste inputs where no PDF tables are available.
    """
    raw = extract_measurements(text, [], [])

    parsed: list[ParsedMeasurement] = []
    for m in raw:
        c = classify_measurement(m.abbreviation, m.value, gender)
        parsed.append(
            ParsedMeasurement(
                name=m.name,
                abbreviation=m.abbreviation,
                value=m.value,
                unit=m.unit,
                status=c.status,
                direction=c.direction,
                reference_range=c.reference_range_str,
                prior_values=[
                    PriorValue(value=pv.value, time_label=pv.time_label)
                    for pv in m.prior_values
                ],
                raw_text=m.raw_text,
                page_number=m.page_number,
            )
        )
    return parsed
