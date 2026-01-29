import fitz  # PyMuPDF
import pdfplumber

from api.models import PageExtractionResult

FALLBACK_CHAR_THRESHOLD = 20


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
                results.append(PageExtractionResult(
                    page_number=page_num,
                    text=text,
                    extraction_method="pdfplumber",
                    confidence=0.95 if len(text.strip()) > 0 else 0.0,
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
                results.append(PageExtractionResult(
                    page_number=page_num,
                    text=text,
                    extraction_method="pymupdf",
                    confidence=0.90 if len(text.strip()) > 0 else 0.0,
                    char_count=len(text),
                ))
        finally:
            doc.close()
        return results
