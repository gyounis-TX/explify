import pytesseract
from pdf2image import convert_from_path

from api.models import PageExtractionResult
from .preprocessor import ImagePreprocessor


class OCRExtractor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.preprocessor = ImagePreprocessor()

    def extract_pages(self, page_numbers: list[int]) -> list[PageExtractionResult]:
        results: list[PageExtractionResult] = []

        for page_num in page_numbers:
            try:
                images = convert_from_path(
                    self.file_path,
                    first_page=page_num,
                    last_page=page_num,
                    dpi=300,
                )
                if not images:
                    results.append(self._empty_result(page_num))
                    continue

                image = images[0]
                processed = self.preprocessor.preprocess(image, source_dpi=300)

                # Get word-level data for confidence scoring
                data = pytesseract.image_to_data(
                    processed,
                    output_type=pytesseract.Output.DICT,
                    config="--psm 6",
                )

                text = pytesseract.image_to_string(
                    processed,
                    config="--psm 6",
                )

                confidences = [
                    int(c) for c in data["conf"]
                    if str(c).lstrip("-").isdigit() and int(c) > 0
                ]
                avg_confidence = (
                    sum(confidences) / len(confidences) / 100.0
                    if confidences
                    else 0.0
                )

                text = text.strip()
                results.append(PageExtractionResult(
                    page_number=page_num,
                    text=text,
                    extraction_method="ocr",
                    confidence=round(avg_confidence, 3),
                    char_count=len(text),
                ))

            except Exception:
                results.append(self._empty_result(page_num))

        return results

    def _empty_result(self, page_num: int) -> PageExtractionResult:
        return PageExtractionResult(
            page_number=page_num,
            text="",
            extraction_method="ocr",
            confidence=0.0,
            char_count=0,
        )
