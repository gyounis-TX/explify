"""
Measurement extraction, reference ranges, and glossary for Cardiac PET / PET-CT reports.

Extracts myocardial blood flow (MBF), coronary flow reserve (CFR), and related metrics.
Includes severity grading, territory-level MBF, MFR aliases, and CFC extraction.
"""

from __future__ import annotations

import re
from typing import Optional

from api.analysis_models import (
    AbnormalityDirection,
    ParsedMeasurement,
    SeverityStatus,
)
from test_types.stress.reference_ranges import (
    ClassificationResult,
    RangeThresholds,
)


_NUM = r"(\d+\.?\d*)"
_SEP = r"[\s:=]+\s*"


# ---------------------------------------------------------------------------
# Severity-graded reference ranges (RangeThresholds)
# ---------------------------------------------------------------------------

PET_RANGE_THRESHOLDS: dict[str, RangeThresholds] = {
    # MBF Rest: normal 0.6-1.2, mild 0.5-0.6, moderate 0.3-0.5, severe <0.3
    "MBF_Rest": RangeThresholds(
        normal_min=0.6, normal_max=1.2,
        mild_min=0.5, moderate_min=0.3, severe_low=0.3,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "MBF_Rest_LAD": RangeThresholds(
        normal_min=0.6, normal_max=1.2,
        mild_min=0.5, moderate_min=0.3, severe_low=0.3,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "MBF_Rest_LCx": RangeThresholds(
        normal_min=0.6, normal_max=1.2,
        mild_min=0.5, moderate_min=0.3, severe_low=0.3,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "MBF_Rest_RCA": RangeThresholds(
        normal_min=0.6, normal_max=1.2,
        mild_min=0.5, moderate_min=0.3, severe_low=0.3,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    # MBF Stress: normal >=2.0, mild 1.5-2.0, moderate 1.0-1.5, severe <1.0
    "MBF_Stress": RangeThresholds(
        normal_min=2.0, normal_max=8.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "MBF_Stress_LAD": RangeThresholds(
        normal_min=2.0, normal_max=8.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "MBF_Stress_LCx": RangeThresholds(
        normal_min=2.0, normal_max=8.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "MBF_Stress_RCA": RangeThresholds(
        normal_min=2.0, normal_max=8.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="mL/min/g",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    # CFR: normal >=2.0, mild 1.5-2.0, moderate 1.0-1.5, severe <1.0
    "CFR_Global": RangeThresholds(
        normal_min=2.0, normal_max=6.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "CFR_LAD": RangeThresholds(
        normal_min=2.0, normal_max=6.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "CFR_LCx": RangeThresholds(
        normal_min=2.0, normal_max=6.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    "CFR_RCA": RangeThresholds(
        normal_min=2.0, normal_max=6.0,
        mild_min=1.5, moderate_min=1.0, severe_low=1.0,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    # LVEF: normal 55-75, mild 45-54, moderate 30-44, severe <30
    "LVEF": RangeThresholds(
        normal_min=55.0, normal_max=75.0,
        mild_min=45.0, moderate_min=30.0, severe_low=30.0,
        unit="%",
        source="ACC/AHA Heart Failure Guidelines",
    ),
    # SSS: normal 0-3, mild 4-8, moderate 9-13, severe >=14 (above)
    "SSS": RangeThresholds(
        normal_max=3.0,
        mild_max=8.0, moderate_max=13.0, severe_high=14.0,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    # SRS: normal 0-3, mild 4-8, moderate 9-13, severe >=14 (above)
    "SRS": RangeThresholds(
        normal_max=3.0,
        mild_max=8.0, moderate_max=13.0, severe_high=14.0,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    # SDS: normal 0-1, mild 2-4, moderate 5-7, severe >=8 (above)
    "SDS": RangeThresholds(
        normal_max=1.0,
        mild_max=4.0, moderate_max=7.0, severe_high=8.0,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
    # TID: normal 0.9-1.2, mild 1.2-1.3, moderate 1.3-1.5, severe >1.5 (above)
    "TID": RangeThresholds(
        normal_min=0.9, normal_max=1.2,
        mild_max=1.3, moderate_max=1.5, severe_high=1.5,
        unit="",
        source="ASNC 2016 PET Myocardial Perfusion Imaging Guidelines",
    ),
}


def classify_pet_measurement(abbr: str, value: float) -> ClassificationResult:
    """Classify a PET measurement against severity-graded reference ranges."""
    rr = PET_RANGE_THRESHOLDS.get(abbr)
    if rr is None:
        return ClassificationResult(
            status=SeverityStatus.UNDETERMINED,
            direction=AbnormalityDirection.NORMAL,
            reference_range_str="No reference range available",
        )

    ref_str = _format_pet_reference_range(rr)

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


def _format_pet_reference_range(rr: RangeThresholds) -> str:
    """Format reference range as a human-readable string."""
    unit = f" {rr.unit}" if rr.unit else ""
    if rr.normal_min is not None and rr.normal_max is not None:
        return f"{rr.normal_min}-{rr.normal_max}{unit}"
    elif rr.normal_min is not None:
        return f">= {rr.normal_min}{unit}"
    elif rr.normal_max is not None:
        return f"<= {rr.normal_max}{unit}"
    return "N/A"


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


# ---------------------------------------------------------------------------
# Backward-compatible flat reference ranges (used by _registry_data.py)
# ---------------------------------------------------------------------------

CARDIAC_PET_REFERENCE_RANGES: dict = {
    "MBF_Rest": {"normal": [0.6, 1.2], "unit": "mL/min/g"},
    "MBF_Stress": {"normal": [2.0, 4.0], "unit": "mL/min/g"},
    "MBF_Stress_LAD": {"normal": [2.0, 4.0], "unit": "mL/min/g"},
    "MBF_Stress_LCx": {"normal": [2.0, 4.0], "unit": "mL/min/g"},
    "MBF_Stress_RCA": {"normal": [2.0, 4.0], "unit": "mL/min/g"},
    "MBF_Rest_LAD": {"normal": [0.6, 1.2], "unit": "mL/min/g"},
    "MBF_Rest_LCx": {"normal": [0.6, 1.2], "unit": "mL/min/g"},
    "MBF_Rest_RCA": {"normal": [0.6, 1.2], "unit": "mL/min/g"},
    "CFR_Global": {"normal": [2.0, 5.0], "unit": ""},
    "CFR_LAD": {"normal": [2.0, 5.0], "unit": ""},
    "CFR_LCx": {"normal": [2.0, 5.0], "unit": ""},
    "CFR_RCA": {"normal": [2.0, 5.0], "unit": ""},
    "LVEF": {"normal": [55, 75], "unit": "%"},
    "SSS": {"normal": [0, 3], "unit": ""},
    "SRS": {"normal": [0, 3], "unit": ""},
    "SDS": {"normal": [0, 1], "unit": ""},
    "TID": {"normal": [0.9, 1.2], "unit": ""},
}


# ---------------------------------------------------------------------------
# Measurement extractor
# ---------------------------------------------------------------------------

def extract_cardiac_pet_measurements(
    full_text: str,
    gender: Optional[str] = None,
) -> list[ParsedMeasurement]:
    """Extract PET-specific measurements from report text."""
    results: list[ParsedMeasurement] = []
    seen: set[str] = set()

    for mdef in _PET_MEASUREMENTS:
        if mdef["abbr"] in seen:
            continue
        for pattern in mdef["patterns"]:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                except (ValueError, IndexError):
                    continue
                if not (mdef["min"] <= value <= mdef["max"]):
                    continue
                abbr = mdef["abbr"]
                classification = classify_pet_measurement(abbr, value)
                results.append(
                    ParsedMeasurement(
                        name=mdef["name"],
                        abbreviation=abbr,
                        value=value,
                        unit=mdef["unit"],
                        status=classification.status,
                        direction=classification.direction,
                        reference_range=classification.reference_range_str,
                        raw_text=match.group(0),
                    )
                )
                seen.add(abbr)
                break

    return results


# ---------------------------------------------------------------------------
# Measurement definitions (including territory MBF + MFR aliases)
# ---------------------------------------------------------------------------

_PET_MEASUREMENTS: list[dict] = [
    # --- Global MBF at Rest ---
    {
        "name": "Global MBF (Rest)",
        "abbr": "MBF_Rest",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 5.0,
        "patterns": [
            rf"(?:global|overall)\s+(?:rest(?:ing)?)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:rest(?:ing)?)\s+(?:global\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"MBF\s+rest{_SEP}{_NUM}",
        ],
    },
    # --- Global MBF at Stress ---
    {
        "name": "Global MBF (Stress)",
        "abbr": "MBF_Stress",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 8.0,
        "patterns": [
            rf"(?:global|overall)\s+(?:stress)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:stress)\s+(?:global\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"MBF\s+stress{_SEP}{_NUM}",
        ],
    },
    # --- Territory MBF at Stress ---
    {
        "name": "LAD Stress MBF",
        "abbr": "MBF_Stress_LAD",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 8.0,
        "patterns": [
            rf"LAD\s+(?:territory\s+)?(?:stress\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:stress)\s+(?:LAD|left\s+anterior\s+descending)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:left\s+anterior\s+descending)\s+(?:territory\s+)?(?:stress\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
        ],
    },
    {
        "name": "LCx Stress MBF",
        "abbr": "MBF_Stress_LCx",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 8.0,
        "patterns": [
            rf"(?:LCx|LCX|circumflex)\s+(?:territory\s+)?(?:stress\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:stress)\s+(?:LCx|LCX|circumflex)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
        ],
    },
    {
        "name": "RCA Stress MBF",
        "abbr": "MBF_Stress_RCA",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 8.0,
        "patterns": [
            rf"(?:RCA|right\s+coronary)\s+(?:territory\s+)?(?:stress\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:stress)\s+(?:RCA|right\s+coronary)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
        ],
    },
    # --- Territory MBF at Rest ---
    {
        "name": "LAD Rest MBF",
        "abbr": "MBF_Rest_LAD",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 5.0,
        "patterns": [
            rf"LAD\s+(?:territory\s+)?(?:rest(?:ing)?\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:rest(?:ing)?)\s+(?:LAD|left\s+anterior\s+descending)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
        ],
    },
    {
        "name": "LCx Rest MBF",
        "abbr": "MBF_Rest_LCx",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 5.0,
        "patterns": [
            rf"(?:LCx|LCX|circumflex)\s+(?:territory\s+)?(?:rest(?:ing)?\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:rest(?:ing)?)\s+(?:LCx|LCX|circumflex)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
        ],
    },
    {
        "name": "RCA Rest MBF",
        "abbr": "MBF_Rest_RCA",
        "unit": "mL/min/g",
        "min": 0.1,
        "max": 5.0,
        "patterns": [
            rf"(?:RCA|right\s+coronary)\s+(?:territory\s+)?(?:rest(?:ing)?\s+)?(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
            rf"(?:rest(?:ing)?)\s+(?:RCA|right\s+coronary)\s+(?:MBF|myocardial\s+blood\s+flow){_SEP}{_NUM}",
        ],
    },
    # --- Global CFR (with MFR aliases) ---
    {
        "name": "Global CFR",
        "abbr": "CFR_Global",
        "unit": "",
        "min": 0.5,
        "max": 6.0,
        "patterns": [
            rf"(?:global|overall)\s+(?:CFR|coronary\s+flow\s+(?:reserve|capacity)|MFR|myocardial\s+flow\s+reserve){_SEP}{_NUM}",
            rf"(?:CFR|coronary\s+flow\s+(?:reserve|capacity)|MFR|myocardial\s+flow\s+reserve){_SEP}{_NUM}",
        ],
    },
    # --- LAD CFR (with MFR aliases) ---
    {
        "name": "LAD CFR",
        "abbr": "CFR_LAD",
        "unit": "",
        "min": 0.5,
        "max": 6.0,
        "patterns": [
            rf"LAD\s+(?:territory\s+)?(?:CFR|coronary\s+flow\s+(?:reserve|capacity)|MFR|myocardial\s+flow\s+reserve){_SEP}{_NUM}",
            rf"(?:left\s+anterior\s+descending)\s+(?:CFR|flow\s+reserve|MFR|myocardial\s+flow\s+reserve){_SEP}{_NUM}",
        ],
    },
    # --- LCx CFR (with MFR aliases) ---
    {
        "name": "LCx CFR",
        "abbr": "CFR_LCx",
        "unit": "",
        "min": 0.5,
        "max": 6.0,
        "patterns": [
            rf"(?:LCx|LCX|circumflex)\s+(?:territory\s+)?(?:CFR|coronary\s+flow\s+(?:reserve|capacity)|MFR|myocardial\s+flow\s+reserve){_SEP}{_NUM}",
        ],
    },
    # --- RCA CFR (with MFR aliases) ---
    {
        "name": "RCA CFR",
        "abbr": "CFR_RCA",
        "unit": "",
        "min": 0.5,
        "max": 6.0,
        "patterns": [
            rf"(?:RCA|right\s+coronary)\s+(?:territory\s+)?(?:CFR|coronary\s+flow\s+(?:reserve|capacity)|MFR|myocardial\s+flow\s+reserve){_SEP}{_NUM}",
        ],
    },
    # --- LVEF ---
    {
        "name": "LVEF",
        "abbr": "LVEF",
        "unit": "%",
        "min": 5.0,
        "max": 85.0,
        "patterns": [
            rf"(?:LVEF|LV\s+ejection\s+fraction|ejection\s+fraction){_SEP}{_NUM}\s*%?",
            rf"{_NUM}\s*%\s*(?:LVEF|ejection\s+fraction)",
        ],
    },
    # --- Summed Stress Score ---
    {
        "name": "Summed Stress Score",
        "abbr": "SSS",
        "unit": "",
        "min": 0.0,
        "max": 80.0,
        "patterns": [
            rf"(?:summed\s+stress\s+score|SSS){_SEP}{_NUM}",
        ],
    },
    # --- Summed Rest Score ---
    {
        "name": "Summed Rest Score",
        "abbr": "SRS",
        "unit": "",
        "min": 0.0,
        "max": 80.0,
        "patterns": [
            rf"(?:summed\s+rest\s+score|SRS){_SEP}{_NUM}",
        ],
    },
    # --- Summed Difference Score ---
    {
        "name": "Summed Difference Score",
        "abbr": "SDS",
        "unit": "",
        "min": 0.0,
        "max": 80.0,
        "patterns": [
            rf"(?:summed\s+difference\s+score|SDS){_SEP}{_NUM}",
        ],
    },
    # --- Transient Ischemic Dilation ---
    {
        "name": "TID Ratio",
        "abbr": "TID",
        "unit": "",
        "min": 0.5,
        "max": 2.5,
        "patterns": [
            rf"(?:TID|transient\s+ischemic\s+dilation)\s+(?:ratio)?{_SEP}{_NUM}",
        ],
    },
]


# ---------------------------------------------------------------------------
# CFC (Coronary Flow Capacity) — extraction + computation fallback
# ---------------------------------------------------------------------------

_CFC_CATEGORIES = {"normal": 0, "mildly reduced": 1, "moderately reduced": 2, "severely reduced": 3}
_CFC_PATTERN = re.compile(
    r"(?:CFC|coronary\s+flow\s+capacity)"
    r"[\s:=]+\s*"
    r"(normal|mildly\s+reduced|moderately\s+reduced|severely\s+reduced)",
    re.IGNORECASE,
)
_CFC_TERRITORY_PATTERNS = {
    "CFC_LAD": re.compile(
        r"(?:LAD|left\s+anterior\s+descending)\s+(?:territory\s+)?"
        r"(?:CFC|coronary\s+flow\s+capacity)"
        r"[\s:=]+\s*"
        r"(normal|mildly\s+reduced|moderately\s+reduced|severely\s+reduced)",
        re.IGNORECASE,
    ),
    "CFC_LCx": re.compile(
        r"(?:LCx|LCX|circumflex)\s+(?:territory\s+)?"
        r"(?:CFC|coronary\s+flow\s+capacity)"
        r"[\s:=]+\s*"
        r"(normal|mildly\s+reduced|moderately\s+reduced|severely\s+reduced)",
        re.IGNORECASE,
    ),
    "CFC_RCA": re.compile(
        r"(?:RCA|right\s+coronary)\s+(?:territory\s+)?"
        r"(?:CFC|coronary\s+flow\s+capacity)"
        r"[\s:=]+\s*"
        r"(normal|mildly\s+reduced|moderately\s+reduced|severely\s+reduced)",
        re.IGNORECASE,
    ),
}


def _extract_cfc_classifications(full_text: str) -> dict[str, str]:
    """Extract CFC classifications from report text.

    Returns dict like {"CFC_Global": "normal", "CFC_LAD": "mildly_reduced", ...}
    """
    results: dict[str, str] = {}

    # Global CFC
    m = _CFC_PATTERN.search(full_text)
    if m:
        results["CFC_Global"] = m.group(1).strip().lower().replace(" ", "_")

    # Territory CFC
    for key, pat in _CFC_TERRITORY_PATTERNS.items():
        m = pat.search(full_text)
        if m:
            results[key] = m.group(1).strip().lower().replace(" ", "_")

    return results


def _compute_cfc(stress_mbf: float | None, cfr: float | None) -> str | None:
    """Compute CFC from stress MBF and CFR when not explicitly reported.

    Murthy/Johnson CFC framework:
    - Normal: stress MBF >= 2.0 AND CFR >= 2.0
    - Mildly reduced: worst component 1.5-2.0
    - Moderately reduced: worst component 1.0-1.5
    - Severely reduced: any component < 1.0
    """
    if stress_mbf is None and cfr is None:
        return None

    # Determine severity of each component individually
    def _component_severity(val: float | None) -> int:
        if val is None:
            return -1  # unknown
        if val >= 2.0:
            return 0  # normal
        if val >= 1.5:
            return 1  # mild
        if val >= 1.0:
            return 2  # moderate
        return 3  # severe

    mbf_sev = _component_severity(stress_mbf)
    cfr_sev = _component_severity(cfr)

    # Take the worst (highest severity) of the two known components
    known = [s for s in (mbf_sev, cfr_sev) if s >= 0]
    if not known:
        return None
    worst = max(known)

    return ["normal", "mildly_reduced", "moderately_reduced", "severely_reduced"][worst]


def get_cfc(
    full_text: str,
    measurements: list[ParsedMeasurement],
) -> dict[str, str]:
    """Get CFC classifications: extract from text first, compute from MBF+CFR as fallback.

    Returns dict like {"CFC_Global": "normal", "CFC_LAD": "mildly_reduced", ...}
    """
    # Step 1: Try extracting from report text
    result = _extract_cfc_classifications(full_text)

    # Step 2: Build lookup of extracted measurements for computation fallback
    meas_map: dict[str, float] = {m.abbreviation: m.value for m in measurements}

    # Compute global CFC if not extracted
    if "CFC_Global" not in result:
        computed = _compute_cfc(
            meas_map.get("MBF_Stress"),
            meas_map.get("CFR_Global"),
        )
        if computed:
            result["CFC_Global"] = computed

    # Compute territory CFC if not extracted
    territories = [("LAD", "CFC_LAD"), ("LCx", "CFC_LCx"), ("RCA", "CFC_RCA")]
    for terr, cfc_key in territories:
        if cfc_key not in result:
            computed = _compute_cfc(
                meas_map.get(f"MBF_Stress_{terr}"),
                meas_map.get(f"CFR_{terr}"),
            )
            if computed:
                result[cfc_key] = computed

    return result


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------

CARDIAC_PET_GLOSSARY: dict[str, str] = {
    "MBF": "Myocardial blood flow — the amount of blood flowing through the heart muscle, measured in mL/min/g. Higher values during stress indicate better blood supply.",
    "Myocardial Blood Flow": "The volume of blood delivered to the heart muscle per minute per gram of tissue. Measured at rest and during stress to assess coronary artery function.",
    "CFR": "Coronary flow reserve — the ratio of stress blood flow to resting blood flow. A CFR above 2.0 is generally normal. Below 2.0 suggests impaired blood supply, which may indicate coronary artery disease.",
    "Coronary Flow Reserve": "The heart's ability to increase blood flow during stress compared to rest. A normal heart can increase flow 2-4 times above resting levels.",
    "MFR": "Myocardial flow reserve — the ratio of stress to rest myocardial blood flow. Functionally identical to coronary flow reserve (CFR). MFR \u2265 2.0 is generally normal.",
    "Myocardial Flow Reserve": "The ratio of stress to rest myocardial blood flow, functionally identical to coronary flow reserve (CFR). A normal heart can at least double its blood flow during stress.",
    "Coronary Flow Capacity": "A composite metric combining stress myocardial blood flow (MBF) and coronary flow reserve (CFR) to classify coronary vasomotor function. Categorized as normal, mildly reduced, moderately reduced, or severely reduced. Provides stronger prognostic value than CFR alone.",
    "CFC": "Coronary flow capacity — a composite classification integrating stress MBF and CFR to assess overall coronary vasomotor function. Normal: stress MBF \u2265 2.0 AND CFR \u2265 2.0. Mildly reduced: worst component 1.5\u20132.0. Moderately reduced: worst component 1.0\u20131.5. Severely reduced: any component < 1.0.",
    "Microvascular Disease": "Dysfunction of the small blood vessels in the heart muscle (as opposed to the large coronary arteries). Can cause reduced blood flow and chest pain even when coronary angiography shows no significant blockages. More common in women, diabetics, and patients with hypertension.",
    "Microvascular Dysfunction": "Impaired function of the tiny blood vessels within the heart muscle. May be suggested by globally reduced coronary flow reserve without focal perfusion defects. Requires correlation with clinical findings and normal coronary angiography for definitive diagnosis.",
    "Epicardial CAD": "Coronary artery disease affecting the large arteries on the surface of the heart. Typically causes focal perfusion defects in specific coronary territories (LAD, LCx, RCA) and is the most common cause of reduced blood flow seen on PET imaging.",
    "Rb-82": "Rubidium-82, a radioactive tracer used in cardiac PET imaging. It is injected intravenously and taken up by the heart muscle in proportion to blood flow.",
    "Rubidium": "A radioactive tracer (Rb-82) used in PET scans to create images of blood flow to the heart muscle.",
    "N-13 Ammonia": "An alternative PET tracer used to measure myocardial blood flow, with a longer half-life than rubidium.",
    "PET": "Positron emission tomography — an advanced imaging technique that measures blood flow to the heart muscle with high accuracy.",
    "PET/CT": "A combined scan using PET (for blood flow) and CT (for anatomy). The CT component may also provide a coronary calcium score.",
    "Perfusion Defect": "An area of the heart that receives less blood than normal, suggesting a narrowed or blocked coronary artery.",
    "Reversible Defect": "A perfusion defect seen during stress but not at rest, indicating an area with reduced blood flow during exertion (ischemia) that still has living heart muscle.",
    "Fixed Defect": "A perfusion defect seen both at rest and during stress, which may indicate scarring from a prior heart attack.",
    "Ischemia": "Reduced blood flow to the heart muscle, often caused by narrowed coronary arteries. PET can detect ischemia by showing decreased blood flow during stress.",
    "SSS": "Summed stress score — a number summarizing perfusion abnormalities during stress. Higher scores indicate more widespread reduced blood flow. A score of 0-3 is normal.",
    "SRS": "Summed rest score — a number summarizing perfusion abnormalities at rest. Higher scores suggest scarring or prior heart damage.",
    "SDS": "Summed difference score — the difference between stress and rest scores. Higher values indicate more ischemia (reversible blood flow problems).",
    "TID": "Transient ischemic dilation — when the heart chamber appears larger during stress than at rest. A TID ratio above 1.2 may suggest widespread coronary artery disease.",
    "LVEF": "Left ventricular ejection fraction — the percentage of blood pumped out of the heart with each beat. Normal is 55-70%.",
    "Pharmacologic Stress": "Using a medication (like regadenoson or adenosine) instead of exercise to simulate stress on the heart during the test.",
    "Regadenoson": "A medication used to dilate coronary arteries during a pharmacologic stress test. Brand name Lexiscan.",
    "Adenosine": "A medication that dilates coronary arteries, used as an alternative to exercise during stress testing.",
    "Dipyridamole": "A medication (Persantine) used to stress the heart by dilating coronary arteries during PET imaging.",
    "LAD": "Left anterior descending artery — supplies blood to the front and part of the side of the heart.",
    "LCx": "Left circumflex artery — supplies blood to the side and back of the heart.",
    "RCA": "Right coronary artery — supplies blood to the bottom of the heart and often the back.",
    "Polar Map": "A bull's-eye diagram showing blood flow to all regions of the heart in a single image.",
    "Attenuation Correction": "A technique using CT to correct for tissue density differences that could affect the accuracy of PET images.",
}
