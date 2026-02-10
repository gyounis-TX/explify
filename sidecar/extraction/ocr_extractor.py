import re

import pytesseract
from pdf2image import convert_from_path

from api.models import PageExtractionResult
from .preprocessor import ImagePreprocessor


_PSM_MODES = [6, 3, 4]  # Block of text, fully auto, single column

# Common Tesseract OCR misreads in medical documents.
# Each entry: (compiled regex pattern, replacement string).
# Applied in order — word-boundary-safe where possible.
_MEDICAL_OCR_CORRECTIONS: list[tuple[re.Pattern, str]] = [
    # Digit/letter confusion
    (re.compile(r"\bHbAlc\b", re.IGNORECASE), "HbA1c"),
    (re.compile(r"\bHbALC\b"), "HbA1c"),
    (re.compile(r"\bAlC\b"), "A1C"),
    (re.compile(r"\bAlc\b(?=\s*[\d:.])"), "A1c"),  # only before a value
    (re.compile(r"\bTSll\b", re.IGNORECASE), "TSH"),
    (re.compile(r"\bTSl-l\b", re.IGNORECASE), "TSH"),

    # rn → m (Tesseract merges r+n into m or vice versa)
    (re.compile(r"\bCreatirline\b", re.IGNORECASE), "Creatinine"),
    (re.compile(r"\bHernoglobin\b", re.IGNORECASE), "Hemoglobin"),
    (re.compile(r"\bHernatocrit\b", re.IGNORECASE), "Hematocrit"),
    (re.compile(r"\bAlburnin\b", re.IGNORECASE), "Albumin"),
    (re.compile(r"\bBiliruhln\b", re.IGNORECASE), "Bilirubin"),
    (re.compile(r"\bBilirubln\b", re.IGNORECASE), "Bilirubin"),
    (re.compile(r"\bTriglycerldes\b", re.IGNORECASE), "Triglycerides"),
    (re.compile(r"\bTriglycendes\b", re.IGNORECASE), "Triglycerides"),

    # O/0 confusion in units and values
    (re.compile(r"\bmg/dI\b"), "mg/dL"),
    (re.compile(r"\bmg/dl\b"), "mg/dL"),
    (re.compile(r"\bml\b(?=/min)"), "mL"),
    (re.compile(r"\bmEq/I\b"), "mEq/L"),
    (re.compile(r"\bmmol/I\b"), "mmol/L"),
    (re.compile(r"\bg/dI\b"), "g/dL"),
    (re.compile(r"\bng/dI\b"), "ng/dL"),
    (re.compile(r"\bng/rnL\b"), "ng/mL"),
    (re.compile(r"\bug/dI\b"), "ug/dL"),
    (re.compile(r"\bpg/rnL\b"), "pg/mL"),
    (re.compile(r"\bIU/rnL\b"), "IU/mL"),
    (re.compile(r"\bU/I\b"), "U/L"),

    # cl → d confusion
    (re.compile(r"\bBlood\b", re.IGNORECASE), "Blood"),  # no-op anchor
    (re.compile(r"\bReci\b"), "Red"),
    (re.compile(r"\bWhlte\b", re.IGNORECASE), "White"),

    # l/1 confusion in common lab names
    (re.compile(r"\bP1atelet\b", re.IGNORECASE), "Platelet"),
    (re.compile(r"\bGlucose\b", re.IGNORECASE), "Glucose"),  # anchor
    (re.compile(r"\bG1ucose\b", re.IGNORECASE), "Glucose"),
    (re.compile(r"\bCa1cium\b", re.IGNORECASE), "Calcium"),
    (re.compile(r"\bPotassiurn\b", re.IGNORECASE), "Potassium"),
    (re.compile(r"\bMagnesiurn\b", re.IGNORECASE), "Magnesium"),
    (re.compile(r"\bSodiurn\b", re.IGNORECASE), "Sodium"),
    (re.compile(r"\bChloricle\b", re.IGNORECASE), "Chloride"),
    (re.compile(r"\bCholestero1\b", re.IGNORECASE), "Cholesterol"),
    (re.compile(r"\bProthrornbin\b", re.IGNORECASE), "Prothrombin"),
]


def _apply_medical_corrections(text: str) -> str:
    """Apply common medical OCR corrections to extracted text."""
    for pattern, replacement in _MEDICAL_OCR_CORRECTIONS:
        text = pattern.sub(replacement, text)
    return text


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

            if avg_conf >= 0.6:  # Good enough, stop trying
                break

        # Apply medical spell corrections to best result
        if best_text:
            best_text = _apply_medical_corrections(best_text)

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
