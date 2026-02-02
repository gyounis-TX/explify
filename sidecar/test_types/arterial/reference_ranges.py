"""
Lower extremity arterial doppler reference ranges.

ABI classification (ACC/AHA 2016):
  Normal:           1.00 - 1.40
  Borderline:       0.91 - 0.99
  Mild PAD:         0.71 - 0.90
  Moderate PAD:     0.41 - 0.70
  Severe PAD:       <= 0.40
  Non-compressible: > 1.40
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
    source: str = "ACC/AHA 2016 PAD Guidelines"


_ABI_RANGE = RangeThresholds(
    normal_min=1.0,
    normal_max=1.4,
    mild_min=0.71,
    moderate_min=0.41,
    severe_low=0.40,
    unit="",
    source="ACC/AHA 2016 PAD Guidelines",
)

REFERENCE_RANGES: dict[str, RangeThresholds] = {
    "R_ABI": _ABI_RANGE,
    "L_ABI": _ABI_RANGE,
}


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
        return ClassificationResult(
            status=SeverityStatus.MILDLY_ABNORMAL,
            direction=AbnormalityDirection.ABOVE_NORMAL,
            reference_range_str=ref_str,
        )

    if rr.normal_min is not None and value < rr.normal_min:
        direction = AbnormalityDirection.BELOW_NORMAL
        if rr.severe_low is not None and value <= rr.severe_low:
            status = SeverityStatus.SEVERELY_ABNORMAL
        elif rr.moderate_min is not None and value < rr.moderate_min:
            status = SeverityStatus.SEVERELY_ABNORMAL
        elif rr.mild_min is not None and value < rr.mild_min:
            status = SeverityStatus.MODERATELY_ABNORMAL
        else:
            status = SeverityStatus.MILDLY_ABNORMAL
        return ClassificationResult(
            status=status, direction=direction, reference_range_str=ref_str
        )

    return ClassificationResult(
        status=SeverityStatus.NORMAL,
        direction=AbnormalityDirection.NORMAL,
        reference_range_str=ref_str,
    )
