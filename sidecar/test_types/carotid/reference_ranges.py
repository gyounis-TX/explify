"""
Carotid Doppler reference ranges and stenosis classification.

Based on Society of Radiologists in Ultrasound (SRU) Consensus Criteria
and AAFP guidelines for carotid stenosis grading.

PSV thresholds for ICA stenosis:
  Normal (no stenosis):  PSV < 125 cm/s
  < 50% stenosis:        PSV < 125 cm/s
  50-69% stenosis:       PSV 125-230 cm/s
  >= 70% stenosis:       PSV > 230 cm/s
  Near occlusion:        Variable, may be low
  Total occlusion:       No detectable flow

ICA/CCA ratio thresholds:
  Normal:    < 2.0
  50-69%:    2.0-4.0
  >= 70%:    > 4.0
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
    source: str = "SRU Consensus Criteria"


# Reference ranges for ICA PSV (applies to all ICA segments)
_ICA_PSV_RANGE = RangeThresholds(
    normal_max=125.0,
    mild_max=125.0,
    moderate_min=125.0,
    moderate_max=230.0,
    severe_high=230.0,
    unit="cm/s",
    source="SRU Consensus Criteria",
)

# CCA PSV — normal range
_CCA_PSV_RANGE = RangeThresholds(
    normal_min=50.0,
    normal_max=120.0,
    unit="cm/s",
    source="SRU Consensus Criteria",
)

# EDV thresholds for ICA
_ICA_EDV_RANGE = RangeThresholds(
    normal_max=40.0,
    mild_max=40.0,
    moderate_min=40.0,
    moderate_max=100.0,
    severe_high=100.0,
    unit="cm/s",
    source="SRU Consensus Criteria",
)

# ICA/CCA velocity ratio
_RATIO_RANGE = RangeThresholds(
    normal_max=2.0,
    mild_max=2.0,
    moderate_min=2.0,
    moderate_max=4.0,
    severe_high=4.0,
    unit="",
    source="SRU Consensus Criteria",
)

# IMT
_IMT_RANGE = RangeThresholds(
    normal_max=0.9,
    mild_max=1.2,
    moderate_max=1.5,
    severe_high=1.5,
    unit="mm",
    source="ASE/AIUM Guidelines",
)


REFERENCE_RANGES: dict[str, RangeThresholds] = {
    # Right ICA PSV
    "R_Prox_ICA_PSV": _ICA_PSV_RANGE,
    "R_Mid_ICA_PSV": _ICA_PSV_RANGE,
    "R_Dist_ICA_PSV": _ICA_PSV_RANGE,
    # Left ICA PSV
    "L_Prox_ICA_PSV": _ICA_PSV_RANGE,
    "L_Mid_ICA_PSV": _ICA_PSV_RANGE,
    "L_Dist_ICA_PSV": _ICA_PSV_RANGE,
    # CCA PSV
    "R_Dist_CCA_PSV": _CCA_PSV_RANGE,
    "R_CCA_PSV": _CCA_PSV_RANGE,
    "L_Dist_CCA_PSV": _CCA_PSV_RANGE,
    "L_CCA_PSV": _CCA_PSV_RANGE,
    # ICA EDV
    "R_Prox_ICA_EDV": _ICA_EDV_RANGE,
    "R_Mid_ICA_EDV": _ICA_EDV_RANGE,
    "R_Dist_ICA_EDV": _ICA_EDV_RANGE,
    "L_Prox_ICA_EDV": _ICA_EDV_RANGE,
    "L_Mid_ICA_EDV": _ICA_EDV_RANGE,
    "L_Dist_ICA_EDV": _ICA_EDV_RANGE,
    # Ratios
    "R_ICA_CCA_Ratio": _RATIO_RANGE,
    "L_ICA_CCA_Ratio": _RATIO_RANGE,
    # IMT
    "R_IMT": _IMT_RANGE,
    "L_IMT": _IMT_RANGE,
}


def _format_reference_range(rr: RangeThresholds) -> str:
    """Format reference range as a human-readable string."""
    unit = f" {rr.unit}" if rr.unit else ""
    if rr.normal_min is not None and rr.normal_max is not None:
        return f"{rr.normal_min}-{rr.normal_max}{unit}"
    elif rr.normal_min is not None:
        return f">= {rr.normal_min}{unit}"
    elif rr.normal_max is not None:
        return f"< {rr.normal_max}{unit}"
    return "N/A"


def classify_measurement(abbreviation: str, value: float) -> ClassificationResult:
    """Classify a carotid measurement against reference ranges."""
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
    """Classify a value that is above the normal range."""
    if rr.severe_high is not None and value >= rr.severe_high:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.moderate_max is not None and value > rr.moderate_max:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.mild_max is not None and value > rr.mild_max:
        return SeverityStatus.MODERATELY_ABNORMAL
    return SeverityStatus.MILDLY_ABNORMAL


def _classify_below(value: float, rr: RangeThresholds) -> SeverityStatus:
    """Classify a value that is below the normal range."""
    if rr.severe_low is not None and value <= rr.severe_low:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.moderate_min is not None and value < rr.moderate_min:
        return SeverityStatus.SEVERELY_ABNORMAL
    if rr.mild_min is not None and value < rr.mild_min:
        return SeverityStatus.MODERATELY_ABNORMAL
    return SeverityStatus.MILDLY_ABNORMAL
