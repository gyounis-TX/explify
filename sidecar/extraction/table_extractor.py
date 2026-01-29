import pdfplumber

from api.models import ExtractedTable


class TableExtractor:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def extract_tables(self, page_numbers: list[int]) -> list[ExtractedTable]:
        results: list[ExtractedTable] = []

        with pdfplumber.open(self.file_path) as pdf:
            for page_num in page_numbers:
                idx = page_num - 1
                if idx < 0 or idx >= len(pdf.pages):
                    continue
                page = pdf.pages[idx]
                tables = page.extract_tables() or []

                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue

                    headers = [str(cell or "").strip() for cell in table[0]]
                    rows = [
                        [str(cell or "").strip() for cell in row]
                        for row in table[1:]
                    ]
                    rows = [row for row in rows if any(cell for cell in row)]

                    if rows:
                        results.append(ExtractedTable(
                            page_number=page_num,
                            table_index=table_idx,
                            headers=headers,
                            rows=rows,
                        ))

        return results
