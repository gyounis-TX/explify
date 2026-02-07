"""Extract patient demographics (age, gender) from medical report text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Demographics:
    age: Optional[int] = None
    gender: Optional[str] = None
    report_date: Optional[str] = None  # e.g. "01/15/2024" or "January 15, 2024"


# Age patterns
_AGE_PATTERNS = [
    # "Age: 45" or "Age 45" or "Age/Sex: 45/M"
    re.compile(r"(?i)\bage\s*(?:/\s*sex)?\s*[:=]?\s*(\d{1,3})\b"),
    # "45 yo" or "45 y/o" or "45 y.o."
    re.compile(r"\b(\d{1,3})\s*(?:yo|y\.?o\.?|y/o)\b", re.IGNORECASE),
    # "45 year old" or "45-year-old" or "45 years old"
    re.compile(r"\b(\d{1,3})\s*[-]?\s*year[s]?\s*[-]?\s*old\b", re.IGNORECASE),
    # Patient header: "Patient: John Doe, 45M" or "45 M" or "45/M"
    re.compile(r"\b(\d{1,3})\s*[/]?\s*[MF]\b", re.IGNORECASE),
]

# DOB pattern to calculate age
_DOB_PATTERN = re.compile(
    r"(?i)(?:DOB|date\s+of\s+birth|birth\s*date)\s*[:=]\s*"
    r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})"
)

# Gender patterns
_GENDER_PATTERNS = [
    # "Sex: M" or "Sex: F" or "Gender: Male"
    re.compile(
        r"(?i)(?:sex|gender)\s*[:=]\s*(male|female|m|f)\b"
    ),
    # "45 yo male" or "45 y/o female"
    re.compile(
        r"(?i)\b\d{1,3}\s*(?:yo|y\.?o\.?|y/o|year[s]?\s*[-]?\s*old)\s+"
        r"(male|female|man|woman|m|f)\b"
    ),
    # "45M" or "45 M" or "45/M" or "45/F" (common report header format)
    re.compile(r"\b\d{1,3}\s*[/]?\s*(M|F)\b"),
    # "Age/Sex: 45/M" pattern
    re.compile(r"(?i)age\s*/\s*sex\s*[:=]?\s*\d{1,3}\s*[/]?\s*(M|F)\b"),
]

_GENDER_MAP = {
    "m": "Male",
    "male": "Male",
    "man": "Male",
    "f": "Female",
    "female": "Female",
    "woman": "Female",
}


def _calculate_age_from_dob(month: int, day: int, year: int) -> Optional[int]:
    """Calculate age from DOB components."""
    if year < 100:
        year += 1900 if year > 30 else 2000
    try:
        dob = datetime(year, month, day)
        today = datetime.now()
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        if 0 <= age <= 120:
            return age
    except (ValueError, OverflowError):
        pass
    return None


_REPORT_DATE_PATTERNS = [
    # "Study Date: 01/15/2024" or "Date of Study: 1-15-2024"
    re.compile(
        r"(?i)(?:study\s+date|date\s+of\s+(?:study|exam(?:ination)?|procedure|report|service|test)"
        r"|exam(?:ination)?\s+date|procedure\s+date|report\s+date|service\s+date"
        r"|test\s+date|date\s+performed|performed\s+(?:on|date))"
        r"\s*[:=]\s*"
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"
    ),
    # "Study Date: January 15, 2024" or "Date of Exam: Jan 15, 2024"
    re.compile(
        r"(?i)(?:study\s+date|date\s+of\s+(?:study|exam(?:ination)?|procedure|report|service|test)"
        r"|exam(?:ination)?\s+date|procedure\s+date|report\s+date|service\s+date"
        r"|test\s+date|date\s+performed|performed\s+(?:on|date))"
        r"\s*[:=]\s*"
        r"([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})"
    ),
    # "Date: 01/15/2024" — generic "Date:" label (only in first ~500 chars of report)
    re.compile(
        r"(?i)\bdate\s*[:=]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"
    ),
    # "Date: January 15, 2024"
    re.compile(
        r"(?i)\bdate\s*[:=]\s*([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})"
    ),
]


def extract_demographics(text: str) -> Demographics:
    """Extract age, gender, and report date from medical report text."""
    if not text:
        return Demographics()

    result = Demographics()

    # Extract age
    for pattern in _AGE_PATTERNS:
        match = pattern.search(text)
        if match:
            age = int(match.group(1))
            if 0 <= age <= 120:
                result.age = age
                break

    # Try DOB if no age found
    if result.age is None:
        dob_match = _DOB_PATTERN.search(text)
        if dob_match:
            month = int(dob_match.group(1))
            day = int(dob_match.group(2))
            year = int(dob_match.group(3))
            result.age = _calculate_age_from_dob(month, day, year)

    # Extract gender
    for pattern in _GENDER_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).lower()
            result.gender = _GENDER_MAP.get(raw)
            if result.gender:
                break

    # Extract report date — use header area first (first 500 chars), then full text
    header_text = text[:500]
    for i, pattern in enumerate(_REPORT_DATE_PATTERNS):
        # Generic "Date:" patterns (last two) only search header area
        search_text = header_text if i >= 2 else text
        match = pattern.search(search_text)
        if match:
            result.report_date = match.group(1).strip()
            break

    return result
