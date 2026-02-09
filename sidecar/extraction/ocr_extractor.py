import pytesseract
from pdf2image import convert_from_path

from api.models import PageExtractionResult
from .preprocessor import ImagePreprocessor


_PSM_MODES = [6, 3, 4]  # Block of text, fully auto, single column


class OCRExtractor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.preprocessor = ImagePreprocessor()

    def _ocr_with_best_psm(self, processed_image) -> tuple[str, float]:
        """Try multiple PSM modes and return best result by confidence."""
        best_text = ""
        best_conf = 0.0

        for psm in _PSM_MODES:
            config = f"--psm {psm}"
            data = pytesseract.image_to_data(
                processed_image, output_type=pytesseract.Output.DICT, config=config,
            )
            text = pytesseract.image_to_string(processed_image, config=config).strip()

            confidences = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) > 0]
            avg_conf = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

            if avg_conf > best_conf:
                best_conf = avg_conf
                best_text = text

            if avg_conf >= 0.7:  # Good enough, stop trying
                break

        return best_text, best_conf

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

                text, avg_confidence = self._ocr_with_best_psm(processed)

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
