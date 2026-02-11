"""
Hemodynamic reference ranges for cardiac catheterization.

Sources:
- Kern MJ, et al. "The Cardiac Catheterization Handbook" 6th ed.
- Baim DS. "Grossman's Cardiac Catheterization, Angiography, and Intervention."
- ACC/AHA hemodynamic guidelines.
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
    source: str = "Cardiac Catheterization Handbook"


# Hemodynamic pressure reference ranges
REFERENCE_RANGES: dict[str, RangeThresholds] = {
    # --- Right Atrium ---
    # RA mean: 0-8 mmHg
    "RA_mean": RangeThresholds(
        normal_min=0.0,
        normal_max=8.0,
        mild_max=12.0,
        moderate_max=16.0,
        severe_high=16.0,
        unit="mmHg",
    ),
    # --- Right Ventricle ---
    # RV systolic: 15-30 mmHg
    "RV_systolic": RangeThresholds(
        normal_min=15.0,
        normal_max=30.0,
        mild_max=40.0,
        moderate_max=55.0,
        severe_high=55.0,
        unit="mmHg",
    ),
    # RV diastolic (end-diastolic): 0-8 mmHg
    "RV_diastolic": RangeThresholds(
        normal_min=0.0,
        normal_max=8.0,
        mild_max=12.0,
        moderate_max=16.0,
        severe_high=16.0,
        unit="mmHg",
    ),
    # --- Pulmonary Artery ---
    # PA systolic: 15-30 mmHg
    "PA_systolic": RangeThresholds(
        normal_min=15.0,
        normal_max=30.0,
        mild_max=40.0,
        moderate_max=55.0,
        severe_high=55.0,
        unit="mmHg",
    ),
    # PA diastolic: 4-12 mmHg
    "PA_diastolic": RangeThresholds(
        normal_min=4.0,
        normal_max=12.0,
        mild_max=18.0,
        moderate_max=25.0,
        severe_high=25.0,
        unit="mmHg",
    ),
    # PA mean: 9-18 mmHg
    "PA_mean": RangeThresholds(
        normal_min=9.0,
        normal_max=18.0,
        mild_max=25.0,
        moderate_max=35.0,
        severe_high=35.0,
        unit="mmHg",
    ),
    # --- Pulmonary Capillary Wedge Pressure ---
    # PCWP/PCP: 4-12 mmHg
    "PCWP": RangeThresholds(
        normal_min=4.0,
        normal_max=12.0,
        mild_max=18.0,
        moderate_max=25.0,
        severe_high=25.0,
        unit="mmHg",
    ),
    # --- Aorta ---
    # AO systolic: 90-140 mmHg
    "AO_systolic": RangeThresholds(
        normal_min=90.0,
        normal_max=140.0,
        mild_max=160.0,
        moderate_max=180.0,
        severe_high=180.0,
        mild_min=80.0,
        moderate_min=70.0,
        severe_low=70.0,
        unit="mmHg",
    ),
    # AO diastolic: 60-90 mmHg
    "AO_diastolic": RangeThresholds(
        normal_min=60.0,
        normal_max=90.0,
        mild_max=100.0,
        moderate_max=110.0,
        severe_high=110.0,
        mild_min=50.0,
        moderate_min=40.0,
        severe_low=40.0,
        unit="mmHg",
    ),
    # --- Left Ventricle ---
    # LV systolic: 90-140 mmHg
    "LV_systolic": RangeThresholds(
        normal_min=90.0,
        normal_max=140.0,
        mild_max=160.0,
        moderate_max=180.0,
        severe_high=180.0,
        mild_min=80.0,
        moderate_min=70.0,
        severe_low=70.0,
        unit="mmHg",
    ),
    # LV diastolic (end-diastolic): 0-12 mmHg
    "LV_diastolic": RangeThresholds(
        normal_min=0.0,
        normal_max=12.0,
        mild_max=18.0,
        moderate_max=25.0,
        severe_high=25.0,
        unit="mmHg",
    ),
    # --- LVEDP ---
    # LVEDP: 4-12 mmHg
    "LVEDP": RangeThresholds(
        normal_min=4.0,
        normal_max=12.0,
        mild_max=18.0,
        moderate_max=25.0,
        severe_high=25.0,
        unit="mmHg",
    ),
    # --- Stenosis Percentage ---
    # Normal: 0%, clinically significant >= 70% (>= 50% for left main)
    "stenosis_pct": RangeThresholds(
        normal_min=0.0,
        normal_max=29.0,
        mild_max=49.0,
        moderate_max=69.0,
        severe_high=70.0,
        unit="%",
        source="ACC/AHA Revascularization Guidelines",
    ),
    # --- IVUS ---
    # MLA: significant if < 4.0 mm2 (left main < 6.0 mm2)
    "MLA": RangeThresholds(
        normal_min=4.0,
        mild_min=3.0,
        moderate_min=2.0,
        severe_low=2.0,
        unit="mm\u00b2",
        source="IVUS Consensus Guidelines",
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


def classify_measurement(
    abbreviation: str, value: float, gender: Optional[str] = None
) -> ClassificationResult:
    """Classify a measurement value against catheterization reference ranges."""
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
