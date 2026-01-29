import pdfplumber

from api.models import DetectionResult, PageDetection, PageType

TEXT_CHAR_THRESHOLD = 50


class PDFDetector:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def detect(self) -> DetectionResult:
        pages: list[PageDetection] = []

        with pdfplumber.open(self.file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                char_count = len(text.strip())

                if char_count >= TEXT_CHAR_THRESHOLD:
                    page_type = PageType.TEXT
                    confidence = min(1.0, char_count / 200)
                else:
                    page_type = PageType.SCANNED
                    confidence = 1.0 - (char_count / TEXT_CHAR_THRESHOLD) if TEXT_CHAR_THRESHOLD > 0 else 1.0

                pages.append(PageDetection(
                    page_number=i + 1,
                    page_type=page_type,
                    char_count=char_count,
                    confidence=round(confidence, 3),
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
