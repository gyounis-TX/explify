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
    # Date of birth — labeled: "DOB: 01/15/1980", "Date of Birth: January 15, 1980"
    # Also handles "D.O.B.", "Birth Date", "Birthdate", "Born: ..."
    (
        "dob",
        re.compile(
            r"(?i)(?:DOB|D\.O\.B\.|date\s+of\s+birth|birth\s*date|born)\s*[:=]\s*"
            r"(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
            r"[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|"
            r"\d{4}[/\-]\d{1,2}[/\-]\d{1,2})"
        ),
        "[DOB REDACTED]",
    ),
    # MRN / Medical Record Number — many label variants
    (
        "mrn",
        re.compile(
            r"(?i)(?:MRN|M\.R\.N\.|medical\s+record\s*(?:number|#|no\.?)"
            r"|med\s*rec\s*(?:number|#|no\.?)"
            r"|record\s*(?:number|#|no\.?))"
            r"\s*[:=#]\s*"
            r"[A-Z0-9\-]{4,20}"
        ),
        "[MRN REDACTED]",
    ),
    # SSN: "123-45-6789" or labeled "SSN: 123-45-6789"
    (
        "ssn",
        re.compile(
            r"(?i)(?:SSN|social\s+security(?:\s+(?:number|#|no\.?))?)\s*[:=]?\s*"
            r"\d{3}-\d{2}-\d{4}"
        ),
        "[SSN REDACTED]",
    ),
    # SSN: bare pattern without label
    (
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN REDACTED]",
    ),
    # Phone: "(555) 123-4567", "555-123-4567", "555.123.4567"
    # Also handles labeled: "Phone: ...", "Tel: ...", "Fax: ..."
    (
        "phone",
        re.compile(
            r"(?i)(?:(?:phone|telephone|tel|fax|cell|mobile|contact)\s*"
            r"(?:number|#|no\.?)?\s*[:=]\s*)?"
            r"(?<!\d)(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"
        ),
        "[PHONE REDACTED]",
    ),
    # Email address
    (
        "email",
        re.compile(
            r"(?i)(?:e-?mail\s*[:=]\s*)?[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        ),
        "[EMAIL REDACTED]",
    ),
    # Address: street number + name + suffix (with optional apt/suite/unit)
    (
        "address",
        re.compile(
            r"\b\d{1,5}\s+(?:[A-Za-z][a-z]+\s+){1,4}"
            r"(?:St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Dr(?:ive)?|Ln|Lane|"
            r"Rd|Road|Way|Ct|Court|Pl(?:ace)?|Cir(?:cle)?|Pkwy|Parkway|"
            r"Ter(?:race)?|Trl|Trail|Hwy|Highway)"
            r"\.?"
            r"(?:\s*,?\s*(?:Apt|Suite|Ste|Unit|#)\s*\.?\s*[A-Za-z0-9\-]+)?"
            r"\b"
        ),
        "[ADDRESS REDACTED]",
    ),
    # Labeled address: "Address: ..." — catch full line after label
    (
        "address",
        re.compile(
            r"(?i)(?:address|addr|mailing\s+address|home\s+address|"
            r"street\s+address)\s*[:=]\s*[^\n]+"
        ),
        "[ADDRESS REDACTED]",
    ),
    # City, State ZIP — "Springfield, IL 62704" or "New York, NY 10001-1234"
    (
        "address",
        re.compile(
            r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*"
            r"[A-Z]{2}\s+\d{5}(?:-\d{4})?"
        ),
        "[ADDRESS REDACTED]",
    ),
    # Standalone ZIP code labeled: "Zip: 62704"
    (
        "zip_code",
        re.compile(
            r"(?i)(?:zip\s*(?:code)?|postal\s*code)\s*[:=]\s*\d{5}(?:-\d{4})?"
        ),
        "[ZIP REDACTED]",
    ),
    # Insurance / Policy / Group numbers (before account pattern to match first)
    (
        "insurance",
        re.compile(
            r"(?i)(?:insurance|policy|group|member|subscriber|plan)\s*"
            r"(?:number|#|no\.?|ID)?\s*[:=]\s*"
            r"[A-Z0-9\-]{4,20}"
        ),
        "[INSURANCE REDACTED]",
    ),
    # Account/ID number: "Account #: 123456789", "Visit #: ...", "Encounter: ..."
    (
        "account_number",
        re.compile(
            r"(?i)(?:account|acct|visit|encounter|case)\s*"
            r"(?:number|#|no\.?|ID)?\s*[:=]\s*"
            r"[A-Z0-9\-]{4,20}"
        ),
        "[ACCOUNT REDACTED]",
    ),
    # Physician names: "Ordering Physician: Dr. John Smith"
    (
        "physician_name",
        re.compile(
            r"(?i)(?:Referred\s+by|Referring\s+Physician|Ordering\s+Physician"
            r"|Ordered\s+by|Referring\s+Provider|Attending\s+Physician"
            r"|Requesting\s+Physician|Primary\s+Care\s+Physician|Clinician"
            r"|Interpreting\s+Physician|Interpreted\s+by|Read\s+by"
            r"|Supervising\s+Physician|Sonographer|Technologist"
            r"|Practice\s+Provider|Provider)"
            r"\s*[:\-]?\s*"
            r"(?:Dr\.?\s*)?"
            r"[A-Za-z][A-Za-z\s.\-']+?"
            r"(?=\s*(?:\n|$|(?:,\s*(?:MD|DO|NP|PA|Ph\.?D|FACC|FACS))|"
            r"(?:\s+(?:MD|DO|NP|PA|Ph\.?D|FACC|FACS))))"
        ),
        "[PHYSICIAN REDACTED]",
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
