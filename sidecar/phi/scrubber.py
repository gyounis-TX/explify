"""
Regex-based PHI scrubber.

Removes common PHI patterns from medical report text before LLM API calls.
Only modifies the copy sent to the API -- never the original text stored locally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ScrubResult:
    scrubbed_text: str
    phi_found: list[str]
    redaction_count: int


_PHI_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Patient name: "Patient: John Doe" or "Name: Jane Smith"
    (
        "patient_name",
        re.compile(
            r"(?i)(?:patient|patient\s+name|name)\s*[:=]\s*"
            r"[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+"
            r"(?:\s+(?:Jr|Sr|II|III|IV)\.?)?"
        ),
        "[PATIENT NAME REDACTED]",
    ),
    # Date of birth: "DOB: 01/15/1980" or "Date of Birth: January 15, 1980"
    (
        "dob",
        re.compile(
            r"(?i)(?:DOB|date\s+of\s+birth|birth\s*date)\s*[:=]\s*"
            r"(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
            r"[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})"
        ),
        "[DOB REDACTED]",
    ),
    # MRN: "MRN: 12345678" or "Medical Record #: 12345678"
    (
        "mrn",
        re.compile(
            r"(?i)(?:MRN|medical\s+record\s*(?:number|#|no\.?))\s*[:=#]\s*"
            r"[A-Z0-9\-]{4,15}"
        ),
        "[MRN REDACTED]",
    ),
    # SSN: "123-45-6789"
    (
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN REDACTED]",
    ),
    # Phone: "(555) 123-4567" or "555-123-4567"
    (
        "phone",
        re.compile(
            r"(?<!\d)(?:\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})(?!\d)"
        ),
        "[PHONE REDACTED]",
    ),
    # Address: street number + name + suffix
    (
        "address",
        re.compile(
            r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}"
            r"(?:St(?:reet)?|Ave(?:nue)?|Blvd|Dr(?:ive)?|Ln|Lane|Rd|Road|"
            r"Way|Ct|Court|Pl(?:ace)?)"
            r"\.?\b"
        ),
        "[ADDRESS REDACTED]",
    ),
    # Account/ID number: "Account #: 123456789"
    (
        "account_number",
        re.compile(
            r"(?i)(?:account|acct|ID)\s*(?:number|#|no\.?)\s*[:=]\s*"
            r"[A-Z0-9\-]{4,20}"
        ),
        "[ACCOUNT REDACTED]",
    ),
]


def scrub_phi(text: str) -> ScrubResult:
    """Remove PHI patterns from text. Returns scrubbed copy."""
    scrubbed = text
    categories_found: set[str] = set()
    total_redactions = 0

    for category, pattern, replacement in _PHI_PATTERNS:
        matches = pattern.findall(scrubbed)
        if matches:
            categories_found.add(category)
            total_redactions += len(matches)
            scrubbed = pattern.sub(replacement, scrubbed)

    return ScrubResult(
        scrubbed_text=scrubbed,
        phi_found=sorted(categories_found),
        redaction_count=total_redactions,
    )
