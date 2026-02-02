"""
Lower extremity venous duplex reference ranges.

Reflux classification:
  GSV reflux time:
    Normal:   < 500 ms (some use < 1000 ms for superficial veins)
    Abnormal: >= 500 ms (or >= 1000 ms for superficial veins)

  Deep vein reflux time:
    Normal:   < 500 ms
    Abnormal: >= 500 ms

  GSV diameter:
    Normal:   < 4.0 mm (varies by segment and population)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from api.analysis_models import AbnormalityDirection, SeverityStatus


@dataclass
class ClassificationResult:
    status: SeverityStatus
    direction: AbnormalityDirection
    reference_range_str: str


@dataclass
class RangeThresholds:
    normal_min: Optional[float] = None
    normal_max: Optional[float] = None
    mild_min: Optional[float] = None
    mild_max: Optional[float] = None
    moderate_min: Optional[float] = None
    moderate_max: Optional[float] = None
    severe_low: Optional[float] = None
    severe_high: Optional[float] = None
    unit: str = ""
    source: str = "SVS/AVF Clinical Practice Guidelines"


# GSV reflux thresholds (superficial vein: 1000 ms cutoff)
_GSV_REFLUX = RangeThresholds(
    normal_max=500.0,
    mild_max=1000.0,
    moderate_max=2000.0,
    severe_high=2000.0,
    unit="ms",
)

# GSV diameter
_GSV_DIAMETER = RangeThresholds(
    normal_max=4.0,
    mild_max=6.0,
    moderate_max=8.0,
    severe_high=8.0,
    unit="mm",
)

REFERENCE_RANGES: dict[str, RangeThresholds] = {}

# Generate entries for each GSV segment
for _seg in ["GSV_Prox", "GSV_Mid", "GSV_Dist"]:
    for _side in ["R", "L"]:
        REFERENCE_RANGES[f"{_side}_{_seg}_Reflux"] = _GSV_REFLUX
        REFERENCE_RANGES[f"{_side}_{_seg}_Diam"] = _GSV_DIAMETER


def _format_reference_range(rr: RangeThresholds) -> str:
    unit = f" {rr.unit}" if rr.unit else ""
    if rr.normal_min is not None and rr.normal_max is not None:
        return f"{rr.normal_min}-{rr.normal_max}{unit}"
    elif rr.normal_min is not None:
        return f">= {rr.normal_min}{unit}"
    elif rr.normal_max is not None:
        return f"< {rr.normal_max}{unit}"
    return "N/A"


def classify_measurement(abbreviation: str, value: float) -> ClassificationResult:
    rr = REFERENCE_RANGES.get(abbreviation)
    if rr is None:
        return ClassificationResult(
            status=SeverityStatus.UNDETERMINED,
            direction=AbnormalityDirection.NORMAL,
            reference_range_str="No reference range available",
        )

    ref_str = _format_reference_range(rr)

    if rr.normal_max is not None and value > rr.normal_max:
        direction = AbnormalityDirection.ABOVE_NORMAL
        if rr.severe_high is not None and value >= rr.severe_high:
            status = SeverityStatus.SEVERELY_ABNORMAL
        elif rr.moderate_max is not None and value > rr.moderate_max:
            status = SeverityStatus.SEVERELY_ABNORMAL
        elif rr.mild_max is not None and value > rr.mild_max:
            status = SeverityStatus.MODERATELY_ABNORMAL
        else:
            status = SeverityStatus.MILDLY_ABNORMAL
        return ClassificationResult(
            status=status, direction=direction, reference_range_str=ref_str
        )

    if rr.normal_min is not None and value < rr.normal_min:
        return ClassificationResult(
            status=SeverityStatus.MILDLY_ABNORMAL,
            direction=AbnormalityDirection.BELOW_NORMAL,
            reference_range_str=ref_str,
        )

    return ClassificationResult(
        status=SeverityStatus.NORMAL,
        direction=AbnormalityDirection.NORMAL,
        reference_range_str=ref_str,
    )
