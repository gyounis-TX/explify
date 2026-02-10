import string

import pdfplumber

from api.models import DetectionResult, PageDetection, PageType

TEXT_CHAR_THRESHOLD = 50

# If extracted text has fewer than this ratio of printable characters,
# treat as garbled/corrupted even if char count exceeds the threshold.
_MIN_PRINTABLE_RATIO = 0.70


def _printable_ratio(text: str) -> float:
    """Fraction of characters that are printable ASCII or common whitespace."""
    if not text:
        return 0.0
    printable = sum(1 for c in text if c in string.printable or ord(c) > 127)
    return printable / len(text)


class PDFDetector:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def detect(self) -> DetectionResult:
        pages: list[PageDetection] = []

        with pdfplumber.open(self.file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                char_count = len(text.strip())

                # A page is TEXT only if it has enough characters AND
                # those characters are mostly printable (not garbled)
                ratio = _printable_ratio(text.strip())
                is_real_text = (
                    char_count >= TEXT_CHAR_THRESHOLD
                    and ratio >= _MIN_PRINTABLE_RATIO
                )

                if is_real_text:
                    page_type = PageType.TEXT
                    confidence = min(1.0, char_count / 200) * min(1.0, ratio / 0.9)
                else:
                    page_type = PageType.SCANNED
                    # High confidence scanned when few chars or garbled
                    if char_count < TEXT_CHAR_THRESHOLD:
                        confidence = 1.0 - (char_count / TEXT_CHAR_THRESHOLD)
                    else:
                        # Had enough chars but they were garbled
                        confidence = 1.0 - ratio

                pages.append(PageDetection(
                    page_number=i + 1,
                    page_type=page_type,
                    char_count=char_count,
                    confidence=round(max(0.0, min(1.0, confidence)), 3),
                ))

        overall_type = self._classify_overall(pages)
        return DetectionResult(
            overall_type=overall_type,
            total_pages=len(pages),
            pages=pages,
        )

    def _classify_overall(self, pages: list[PageDetection]) -> PageType:
        if not pages:
            return PageType.SCANNED

        text_count = sum(1 for p in pages if p.page_type == PageType.TEXT)
        ratio = text_count / len(pages)

        if ratio >= 1.0:
            return PageType.TEXT
        elif ratio <= 0.0:
            return PageType.SCANNED
        else:
            return PageType.MIXED
