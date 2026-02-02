"""
Reference ranges for exercise stress test measurements.

Sources:
- ACC/AHA 2002 Guideline Update for Exercise Testing
- Fletcher GF, et al. Circulation 2013;128:873-934
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
    source: str = "ACC/AHA Exercise Testing Guidelines"


REFERENCE_RANGES: dict[str, RangeThresholds] = {
    # METs: >= 10 excellent, 7-9 good, 5-6 fair, < 5 poor
    "METs": RangeThresholds(
        normal_min=7.0,
        mild_min=5.0,
        moderate_min=3.0,
        severe_low=3.0,
        unit="METs",
    ),
    # % Max Predicted Heart Rate: target >= 85%
    "MPHR%": RangeThresholds(
        normal_min=85.0,
        mild_min=75.0,
        moderate_min=65.0,
        severe_low=65.0,
        unit="%",
    ),
    # Peak Heart Rate (wide range, mainly informational)
    "Peak_HR": RangeThresholds(
        normal_min=100.0,
        normal_max=220.0,
        unit="bpm",
    ),
    # Resting Heart Rate
    "Rest_HR": RangeThresholds(
        normal_min=50.0,
        normal_max=100.0,
        unit="bpm",
    ),
    # Peak Systolic BP: normal rise; > 250 is excessive
    "Peak_SBP": RangeThresholds(
        normal_max=210.0,
        mild_max=230.0,
        moderate_max=250.0,
        severe_high=250.0,
        unit="mmHg",
    ),
    # ST Depression: < 1mm normal
    "ST_Depression": RangeThresholds(
        normal_max=0.5,
        mild_max=1.0,
        moderate_max=2.0,
        severe_high=2.0,
        unit="mm",
    ),
    # Exercise Duration (Bruce protocol): >= 9 min is good
    "Exercise_Duration": RangeThresholds(
        normal_min=9.0,
        mild_min=6.0,
        moderate_min=3.0,
        severe_low=3.0,
        unit="min",
    ),
    # Duke Treadmill Score: >= 5 low risk, -10 to 4 moderate, < -10 high risk
    "Duke_Score": RangeThresholds(
        normal_min=5.0,
        mild_min=-10.0,
        severe_low=-10.0,
        unit="",
    ),
    # Rate-Pressure Product: normal peak 20000-35000
    "RPP": RangeThresholds(
        normal_min=20000.0,
        normal_max=35000.0,
        unit="",
    ),
}


def _format_reference_range(rr: RangeThresholds) -> str:
    """Format reference range as a human-readable string."""
    unit = f" {rr.unit}" if rr.unit else ""
    if rr.normal_min is not None and rr.normal_max is not None:
        return f"{rr.normal_min}-{rr.normal_max}{unit}"
    elif rr.normal_min is not None:
        return f">= {rr.normal_min}{unit}"
    elif rr.normal_max is not None:
        return f"<= {rr.normal_max}{unit}"
    return "N/A"


def classify_measurement(abbreviation: str, value: float) -> ClassificationResult:
    """Classify a stress test measurement against reference ranges."""
    rr = REFERENCE_RANGES.get(abbreviation)
    if rr is None:
        return ClassificationResult(
            status=SeverityStatus.UNDETERMINED,
            direction=AbnormalityDirection.NORMAL,
            reference_range_str="No reference range available",
        )

    ref_str = _format_reference_range(rr)

    # Check above normal
    if rr.normal_max is not None and value > rr.normal_max:
        direction = AbnormalityDirection.ABOVE_NORMAL
        status = _classify_above(value, rr)
        return ClassificationResult(
            status=status, direction=direction, reference_range_str=ref_str
        )

    # Check below normal
    if rr.normal_min is not None and value < rr.normal_min:
        direction = AbnormalityDirection.BELOW_NORMAL
        status = _classify_below(value, rr)
        return ClassificationResult(
            status=status, direction=direction, reference_range_str=ref_str
        )

    return ClassificationResult(
        status=SeverityStatus.NORMAL,
        direction=AbnormalityDirection.NORMAL,
        reference_range_str=ref_str,
    )


def _classify_above(value: float, rr: RangeThresholds) -> SeverityStatus:
    if rr.severe_high is not None and value >= rr.severe_high:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.moderate_max is not None and value > rr.moderate_max:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.mild_max is not None and value > rr.mild_max:
        return SeverityStatus.MODERATELY_ABNORMAL
    return SeverityStatus.MILDLY_ABNORMAL


def _classify_below(value: float, rr: RangeThresholds) -> SeverityStatus:
    if rr.severe_low is not None and value <= rr.severe_low:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.moderate_min is not None and value < rr.moderate_min:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.mild_min is not None and value < rr.mild_min:
        return SeverityStatus.MODERATELY_ABNORMAL
    return SeverityStatus.MILDLY_ABNORMAL
