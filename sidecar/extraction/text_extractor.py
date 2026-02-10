import re
import string

import fitz  # PyMuPDF
import pdfplumber

from api.models import PageExtractionResult

FALLBACK_CHAR_THRESHOLD = 20

# Printable ASCII ratio below this → likely garbled/corrupted text
_MIN_PRINTABLE_RATIO = 0.75

# Minimum average word length for "real" text (very short = encoding garbage)
_MIN_AVG_WORD_LEN = 2.0

# Common medical terms used as a positive signal for text quality
_MEDICAL_TERMS = frozenset({
    "patient", "date", "age", "sex", "dob", "mrn",
    "results", "reference", "range", "units", "flag",
    "normal", "abnormal", "high", "low", "critical",
    "test", "lab", "specimen", "collected",
    "hemoglobin", "hematocrit", "glucose", "cholesterol",
    "sodium", "potassium", "creatinine", "bun",
    "wbc", "rbc", "platelet", "calcium",
    "impression", "findings", "conclusion", "history",
    "diagnosis", "report", "physician", "ordered",
    "echocardiogram", "ejection", "fraction", "ventricle",
    "systolic", "diastolic", "blood", "pressure",
    "electrocardiogram", "rhythm", "sinus", "rate",
})


def _score_text_quality(text: str) -> float:
    """Score extracted text quality on a 0.0–1.0 scale.

    Uses three signals:
    1. Printable character ratio (chars that are normal ASCII/Unicode text)
    2. Average word length (garbled text tends toward very short tokens)
    3. Medical term hits (bonus for recognisable medical vocabulary)
    """
    if not text or not text.strip():
        return 0.0

    stripped = text.strip()

    # 1. Printable ratio: fraction of chars that are printable ASCII or common Unicode
    printable = sum(1 for c in stripped if c in string.printable or ord(c) > 127)
    printable_ratio = printable / len(stripped) if stripped else 0.0

    if printable_ratio < _MIN_PRINTABLE_RATIO:
        # Heavily penalise garbled text
        return round(max(0.1, printable_ratio * 0.5), 3)

    # 2. Word quality: average word length (split on whitespace)
    words = stripped.split()
    if not words:
        return round(printable_ratio * 0.5, 3)

    avg_word_len = sum(len(w) for w in words) / len(words)
    word_score = min(1.0, avg_word_len / 4.0)  # 4+ chars avg → 1.0

    if avg_word_len < _MIN_AVG_WORD_LEN:
        word_score *= 0.5  # Penalise very short average

    # 3. Medical term bonus
    lower_words = {w.lower().strip(string.punctuation) for w in words}
    term_hits = len(lower_words & _MEDICAL_TERMS)
    # Scale: 0 hits = 0, 3+ hits = 0.1 bonus
    term_bonus = min(0.1, term_hits * 0.033)

    # Combine: base from printable ratio, weighted by word quality, plus term bonus
    score = printable_ratio * 0.6 + word_score * 0.3 + term_bonus
    return round(min(1.0, max(0.0, score)), 3)


class TextExtractor:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def extract_pages(self, page_numbers: list[int]) -> list[PageExtractionResult]:
        results: list[PageExtractionResult] = []

        pdfplumber_results = self._extract_with_pdfplumber(page_numbers)

        fallback_pages = [
            r.page_number for r in pdfplumber_results
            if r.char_count < FALLBACK_CHAR_THRESHOLD
        ]

        pymupdf_results: dict[int, PageExtractionResult] = {}
        if fallback_pages:
            pymupdf_results = {
                r.page_number: r
                for r in self._extract_with_pymupdf(fallback_pages)
            }

        for plumber_result in pdfplumber_results:
            page_num = plumber_result.page_number
            if page_num in pymupdf_results:
                mu_result = pymupdf_results[page_num]
                if mu_result.char_count > plumber_result.char_count:
                    results.append(mu_result)
                    continue
            results.append(plumber_result)

        return results

    def _extract_with_pdfplumber(
        self, page_numbers: list[int]
    ) -> list[PageExtractionResult]:
        results = []
        with pdfplumber.open(self.file_path) as pdf:
            for page_num in page_numbers:
                idx = page_num - 1
                if idx < 0 or idx >= len(pdf.pages):
                    continue
                page = pdf.pages[idx]
                text = page.extract_text() or ""
                confidence = _score_text_quality(text)
                results.append(PageExtractionResult(
                    page_number=page_num,
                    text=text,
                    extraction_method="pdfplumber",
                    confidence=confidence,
                    char_count=len(text),
                ))
        return results

    def _extract_with_pymupdf(
        self, page_numbers: list[int]
    ) -> list[PageExtractionResult]:
        results = []
        doc = fitz.open(self.file_path)
        try:
            for page_num in page_numbers:
                idx = page_num - 1
                if idx < 0 or idx >= len(doc):
                    continue
                page = doc[idx]
                text = page.get_text("text") or ""
                confidence = _score_text_quality(text)
                results.append(PageExtractionResult(
                    page_number=page_num,
                    text=text,
                    extraction_method="pymupdf",
                    confidence=confidence,
                    char_count=len(text),
                ))
        finally:
            doc.close()
        return results
