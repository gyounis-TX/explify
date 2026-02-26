"""
Diastolic function grade extraction and computation for echocardiogram reports.

Priority: extract the grade from report text first (most reports state it
explicitly). Only fall back to computing from raw measurements when the
report doesn't state a grade.
"""

from __future__ import annotations

import re
from typing import Optional

from api.analysis_models import ParsedMeasurement


# ---------------------------------------------------------------------------
# Text extraction patterns — most reports state the grade directly
# ---------------------------------------------------------------------------

_DIASTOLIC_GRADE_MAP: list[tuple[re.Pattern, str, str]] = [
    # Grade III patterns (check before Grade I/II to avoid partial matches)
    (
        re.compile(
            r"(?:grade|gr)\.?\s*(?:III|3)\s+(?:diastolic\s+)?dysfunction",
            re.IGNORECASE,
        ),
        "grade_iii",
        "Grade III (Restrictive Filling)",
    ),
    (
        re.compile(r"restrictive\s+(?:filling|pattern)", re.IGNORECASE),
        "grade_iii",
        "Grade III (Restrictive Filling)",
    ),
    # Grade II patterns
    (
        re.compile(
            r"(?:grade|gr)\.?\s*(?:II|2)\s+(?:diastolic\s+)?dysfunction",
            re.IGNORECASE,
        ),
        "grade_ii",
        "Grade II (Pseudonormal)",
    ),
    (
        re.compile(r"pseudonormal(?:ized|ization)?", re.IGNORECASE),
        "grade_ii",
        "Grade II (Pseudonormal)",
    ),
    # Grade I patterns
    (
        re.compile(
            r"(?:grade|gr)\.?\s*(?:I|1)\s+(?:diastolic\s+)?dysfunction",
            re.IGNORECASE,
        ),
        "grade_i",
        "Grade I (Impaired Relaxation)",
    ),
    (
        re.compile(r"impaired\s+relaxation", re.IGNORECASE),
        "grade_i",
        "Grade I (Impaired Relaxation)",
    ),
    # Normal
    (
        re.compile(r"normal\s+diastolic\s+function", re.IGNORECASE),
        "normal",
        "Normal Diastolic Function",
    ),
    (
        re.compile(r"diastolic\s+function\s+is\s+normal", re.IGNORECASE),
        "normal",
        "Normal Diastolic Function",
    ),
    # Indeterminate
    (
        re.compile(r"indeterminate\s+diastolic", re.IGNORECASE),
        "indeterminate",
        "Indeterminate",
    ),
]


def _extract_diastolic_from_text(full_text: str) -> Optional[dict[str, str]]:
    """Try to extract a stated diastolic function grade from report text."""
    for pattern, grade, label in _DIASTOLIC_GRADE_MAP:
        if pattern.search(full_text):
            filling = _filling_pressure_from_grade(grade)
            return {
                "grade": grade,
                "label": label,
                "filling_pressures": filling,
                "source": "report",
                "confidence": "high",
            }
    return None


def _filling_pressure_from_grade(grade: str) -> str:
    """Map diastolic grade to expected filling pressure status."""
    return {
        "normal": "normal",
        "grade_i": "normal",
        "grade_ii": "elevated",
        "grade_iii": "elevated",
        "indeterminate": "indeterminate",
    }.get(grade, "indeterminate")


# ---------------------------------------------------------------------------
# Computation fallback — ASE/EACVI 2016 algorithm
# ---------------------------------------------------------------------------


def _compute_diastolic_grade(
    e_a: Optional[float],
    e_e_prime: Optional[float],
    lavi: Optional[float],
    e_prime_septal: Optional[float],
    e_prime_lateral: Optional[float],
    trv: Optional[float],
) -> Optional[dict[str, str]]:
    """Compute diastolic function grade from measurements using ASE 2016.

    Step 1: Average e' (septal + lateral / 2). If avg e' < 7 (or septal < 7
            or lateral < 10) -> abnormal relaxation.
    Step 2: If relaxation abnormal, evaluate 3 criteria:
            - E/e' average > 14
            - LAVI > 34 mL/m2
            - TRV > 2.8 m/s
            If >= 2 of 3 positive -> elevated filling pressures
            If 0-1 of 3 -> normal filling pressures or indeterminate
    Step 3: Combine E/A with filling pressure assessment:
            - E/A < 0.8 + normal pressures -> Grade I
            - E/A 0.8-2.0 + elevated pressures -> Grade II
            - E/A > 2.0 + elevated pressures -> Grade III
            - Mixed signals -> Indeterminate

    Returns dict or None if insufficient data.
    """
    # Need at least E/A and one e' measurement to attempt computation
    if e_a is None:
        return None
    if e_prime_septal is None and e_prime_lateral is None and e_e_prime is None:
        return None

    # Count how many measurements we have for confidence assessment
    available = sum(1 for v in [e_a, e_e_prime, lavi, e_prime_septal,
                                e_prime_lateral, trv] if v is not None)
    confidence = "high" if available >= 4 else "low"

    # Step 1: Assess relaxation
    avg_e_prime = None
    if e_prime_septal is not None and e_prime_lateral is not None:
        avg_e_prime = (e_prime_septal + e_prime_lateral) / 2.0
    elif e_prime_septal is not None:
        avg_e_prime = e_prime_septal
    elif e_prime_lateral is not None:
        avg_e_prime = e_prime_lateral

    relaxation_abnormal = False
    if avg_e_prime is not None:
        # Abnormal if avg e' < 7, or septal < 7, or lateral < 10
        if avg_e_prime < 7:
            relaxation_abnormal = True
        elif e_prime_septal is not None and e_prime_septal < 7:
            relaxation_abnormal = True
        elif e_prime_lateral is not None and e_prime_lateral < 10:
            relaxation_abnormal = True

    if not relaxation_abnormal:
        # Normal relaxation -> likely normal diastolic function
        return {
            "grade": "normal",
            "label": "Normal Diastolic Function",
            "filling_pressures": "normal",
            "source": "computed",
            "confidence": confidence,
        }

    # Step 2: Evaluate filling pressure criteria
    criteria_met = 0
    criteria_available = 0

    if e_e_prime is not None:
        criteria_available += 1
        if e_e_prime > 14:
            criteria_met += 1
    if lavi is not None:
        criteria_available += 1
        if lavi > 34:
            criteria_met += 1
    if trv is not None:
        criteria_available += 1
        if trv > 2.8:
            criteria_met += 1

    if criteria_available == 0:
        # Can't assess filling pressures — indeterminate
        return {
            "grade": "indeterminate",
            "label": "Indeterminate",
            "filling_pressures": "indeterminate",
            "source": "computed",
            "confidence": "low",
        }

    elevated_pressures = criteria_met >= 2

    # Step 3: Combine with E/A ratio
    if e_a < 0.8 and not elevated_pressures:
        return {
            "grade": "grade_i",
            "label": "Grade I (Impaired Relaxation)",
            "filling_pressures": "normal",
            "source": "computed",
            "confidence": confidence,
        }
    elif 0.8 <= e_a <= 2.0 and elevated_pressures:
        return {
            "grade": "grade_ii",
            "label": "Grade II (Pseudonormal)",
            "filling_pressures": "elevated",
            "source": "computed",
            "confidence": confidence,
        }
    elif e_a > 2.0 and elevated_pressures:
        return {
            "grade": "grade_iii",
            "label": "Grade III (Restrictive Filling)",
            "filling_pressures": "elevated",
            "source": "computed",
            "confidence": confidence,
        }
    elif e_a < 0.8 and elevated_pressures:
        # E/A suggests grade I but pressures elevated — could be grade II
        return {
            "grade": "indeterminate",
            "label": "Indeterminate",
            "filling_pressures": "indeterminate",
            "source": "computed",
            "confidence": "low",
        }
    else:
        return {
            "grade": "indeterminate",
            "label": "Indeterminate",
            "filling_pressures": "indeterminate",
            "source": "computed",
            "confidence": "low",
        }


# ---------------------------------------------------------------------------
# Unified function — extract first, compute as fallback
# ---------------------------------------------------------------------------


def get_diastolic_grade(
    full_text: str,
    measurements: list[ParsedMeasurement],
) -> Optional[dict[str, str]]:
    """Get diastolic function grade: extract from text first, compute as fallback.

    Returns dict like:
    {
        "grade": "grade_i",
        "label": "Grade I (Impaired Relaxation)",
        "filling_pressures": "normal",
        "source": "report" or "computed",
        "confidence": "high" or "low",
    }
    """
    # Priority 1: Extract from report text
    result = _extract_diastolic_from_text(full_text)
    if result is not None:
        return result

    # Priority 2: Compute from extracted measurements
    meas_map: dict[str, float] = {m.abbreviation: m.value for m in measurements}

    return _compute_diastolic_grade(
        e_a=meas_map.get("E/A"),
        e_e_prime=meas_map.get("E/e'"),
        lavi=meas_map.get("LAVI"),
        e_prime_septal=meas_map.get("e'_septal"),
        e_prime_lateral=meas_map.get("e'_lateral"),
        trv=meas_map.get("TRV"),
    )
