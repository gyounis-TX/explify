"""
Regex-based measurement extraction for lower extremity arterial
doppler / ultrasound reports.

Handles tabular format with Right/Left columns containing velocity,
waveform, and lumen status, plus ABI measurements.
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


# Arterial segments in typical report order
_SEGMENTS = [
    (r"CFA", "CFA"),
    (r"PFA", "PFA"),
    (r"Prox\s+Femoral", "Prox_Fem"),
    (r"Mid\s+Femoral", "Mid_Fem"),
    (r"Dist\s+Femoral", "Dist_Fem"),
    (r"Pop\s*A", "Pop_A"),
    (r"PTA", "PTA"),
    (r"ATA", "ATA"),
    (r"DPA", "DPA"),
    (r"Peroneal", "Peroneal"),
]


def _extract_tabular_velocities(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """
    Extract velocity values from the tabular layout:
        CFA    90.91 cm/s  Triphasic  Patent    86.03 cm/s  Triphasic  Patent
    """
    results: list[RawMeasurement] = []

    for seg_pattern, seg_abbr in _SEGMENTS:
        # Pattern: Segment  R_velocity cm/s  Waveform  Lumen  L_velocity cm/s  Waveform  Lumen
        pattern = (
            r"(?i)" + seg_pattern
            + r"\s+(\d+\.?\d*)\s*(?:cm/s)?\s+(?:Triphasic|Biphasic|Monophasic)\s+(?:Patent|Occluded|Stenosed)"
            + r"\s+(\d+\.?\d*)\s*(?:cm/s)?"
        )
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            r_vel = float(match.group(1))
            l_vel = float(match.group(2))
            page_num = _find_page(match.group(), pages)

            if 5.0 <= r_vel <= 600.0:
                results.append(RawMeasurement(
                    name=f"Right {seg_abbr} Velocity",
                    abbreviation=f"R_{seg_abbr}_Vel",
                    value=r_vel,
                    unit="cm/s",
                    raw_text=match.group().strip(),
                    page_number=page_num,
                ))
            if 5.0 <= l_vel <= 600.0:
                results.append(RawMeasurement(
                    name=f"Left {seg_abbr} Velocity",
                    abbreviation=f"L_{seg_abbr}_Vel",
                    value=l_vel,
                    unit="cm/s",
                    raw_text=match.group().strip(),
                    page_number=page_num,
                ))

    return results


def _extract_abi(
    full_text: str,
    pages: list[PageExtractionResult],
) -> list[RawMeasurement]:
    """Extract Ankle-Brachial Index values."""
    results: list[RawMeasurement] = []

    # Brachial pressure
    bp_match = re.search(
        r"(?i)brachial\s+artery\s+pressure\s+(\d+)\s*(?:mmHg)?",
        full_text,
    )
    if bp_match:
        val = float(bp_match.group(1))
        if 50 <= val <= 300:
            results.append(RawMeasurement(
                name="Brachial Artery Pressure",
                abbreviation="Brachial_BP",
                value=val,
                unit="mmHg",
                raw_text=bp_match.group().strip(),
                page_number=_find_page(bp_match.group(), pages),
            ))

    # ABI — look for two values (right and left) on the same line
    abi_pattern = r"(?i)ankle[- ]brachial\s+index(?:\s+PT)?\s+(\d+\.?\d*)\s+(\d+\.?\d*)"
    abi_match = re.search(abi_pattern, full_text)
    if abi_match:
        r_abi = float(abi_match.group(1))
        l_abi = float(abi_match.group(2))
        page_num = _find_page(abi_match.group(), pages)

        if 0.1 <= r_abi <= 2.0:
            results.append(RawMeasurement(
                name="Right Ankle-Brachial Index",
                abbreviation="R_ABI",
                value=r_abi,
                unit="",
                raw_text=abi_match.group().strip(),
                page_number=page_num,
            ))
        if 0.1 <= l_abi <= 2.0:
            results.append(RawMeasurement(
                name="Left Ankle-Brachial Index",
                abbreviation="L_ABI",
                value=l_abi,
                unit="",
                raw_text=abi_match.group().strip(),
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

    for m in _extract_tabular_velocities(full_text, pages):
        if m.abbreviation not in seen:
            results.append(m)
            seen.add(m.abbreviation)

    for m in _extract_abi(full_text, pages):
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
