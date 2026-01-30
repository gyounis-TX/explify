"""Extract physician name from medical report text."""

from __future__ import annotations

import re

_PHYSICIAN_PATTERN = re.compile(
    r"(?:Referred\s+by|Referring\s+Physician|Ordering\s+Physician|Ordered\s+by"
    r"|Referring\s+Provider|Attending\s+Physician|Requesting\s+Physician"
    r"|Primary\s+Care\s+Physician|Clinician)"
    r"\s*[:\-]?\s*"
    r"(?:Dr\.?\s*)?"
    r"([A-Za-z][A-Za-z\s.\-']+)",
    re.IGNORECASE,
)

_SUFFIX_PATTERN = re.compile(
    r"\b(?:MD|DO|NP|PA|Ph\.?D|FACC|FACS|Jr|Sr|II|III|IV)\b\.?",
    re.IGNORECASE,
)

# Boundary words that signal the end of the physician name section.
# If any of these appear in the captured text, truncate before them.
_BOUNDARY_PATTERN = re.compile(
    r"\b(?:age|dob|date|patient|sex|gender|mrn|acct|account|location|dept)\b",
    re.IGNORECASE,
)


def extract_physician_name(text: str | None) -> str | None:
    """Extract physician name from report text and return 'Dr. LastName' or None."""
    if not text:
        return None

    match = _PHYSICIAN_PATTERN.search(text)
    if not match:
        return None

    raw_name = match.group(1).strip()

    # Truncate at boundary words (e.g. "Younis age 45" → "Younis")
    boundary = _BOUNDARY_PATTERN.search(raw_name)
    if boundary:
        raw_name = raw_name[: boundary.start()].strip()

    # Remove suffixes like MD, DO, NP, PA
    cleaned = _SUFFIX_PATTERN.sub("", raw_name).strip()
    # Remove trailing commas/periods/spaces left after suffix removal
    cleaned = re.sub(r"[,.\s]+$", "", cleaned).strip()

    if not cleaned:
        return None

    # Split into tokens to get the last name
    tokens = cleaned.split()
    last_name = tokens[-1].strip(".,")

    if not last_name:
        return None

    # Capitalize properly (handle all-lower or all-upper input, including hyphens)
    last_name = "-".join(part.capitalize() for part in last_name.split("-"))

    return f"Dr. {last_name}"
