"""Tests for text_table_parser — detect tabular structure in pasted EMR text."""

from extraction.text_table_parser import parse_text_tables
from test_types.labs.measurements import extract_measurements
from api.models import PageExtractionResult


class TestPipeDelimited:
    """Epic-style pipe-delimited tables."""

    EPIC_CMP = (
        "Component | Value | Units | Range | Flag\n"
        "Sodium    | 138   | mEq/L | 136-145 |\n"
        "Potassium | 5.8   | mEq/L | 3.5-5.1 | H\n"
        "Glucose   | 95    | mg/dL | 70-100  |\n"
        "BUN       | 18    | mg/dL | 7-20    |\n"
        "Creatinine| 1.1   | mg/dL | 0.7-1.3 |\n"
    )

    def test_detects_pipe_table(self):
        tables = parse_text_tables(self.EPIC_CMP)
        assert len(tables) == 1
        assert tables[0].headers[0] == "Component"
        assert len(tables[0].rows) == 5

    def test_extracts_measurements_from_pipe_table(self):
        tables = parse_text_tables(self.EPIC_CMP)
        pages = [PageExtractionResult(
            page_number=1, text=self.EPIC_CMP,
            extraction_method="direct_input", confidence=1.0,
            char_count=len(self.EPIC_CMP),
        )]
        results = extract_measurements(self.EPIC_CMP, pages, tables)
        abbrs = {m.abbreviation for m in results}
        assert "NA" in abbrs, f"Expected NA in {abbrs}"
        assert "K" in abbrs, f"Expected K in {abbrs}"
        assert "GLU" in abbrs, f"Expected GLU in {abbrs}"
        assert "BUN" in abbrs, f"Expected BUN in {abbrs}"
        assert "CREAT" in abbrs, f"Expected CREAT in {abbrs}"

    def test_correct_values(self):
        tables = parse_text_tables(self.EPIC_CMP)
        pages = [PageExtractionResult(
            page_number=1, text=self.EPIC_CMP,
            extraction_method="direct_input", confidence=1.0,
            char_count=len(self.EPIC_CMP),
        )]
        results = extract_measurements(self.EPIC_CMP, pages, tables)
        by_abbr = {m.abbreviation: m.value for m in results}
        assert by_abbr["NA"] == 138.0
        assert by_abbr["K"] == 5.8
        assert by_abbr["GLU"] == 95.0
        assert by_abbr["BUN"] == 18.0
        assert by_abbr["CREAT"] == 1.1

    def test_epic_emr_hint(self):
        tables = parse_text_tables(self.EPIC_CMP, emr_source="epic")
        assert len(tables) == 1


class TestTabDelimited:
    """Tab-delimited tables (Cerner, Excel copy-paste)."""

    TAB_TEXT = (
        "Glucose\t95\tmg/dL\t70-100\n"
        "BUN\t18\tmg/dL\t7-20\n"
        "Creatinine\t1.1\tmg/dL\t0.7-1.3\n"
    )

    def test_detects_tab_table(self):
        tables = parse_text_tables(self.TAB_TEXT)
        assert len(tables) == 1
        assert len(tables[0].rows) >= 2  # 3 data rows, first may be header

    def test_extracts_measurements_from_tab_table(self):
        tables = parse_text_tables(self.TAB_TEXT)
        pages = [PageExtractionResult(
            page_number=1, text=self.TAB_TEXT,
            extraction_method="direct_input", confidence=1.0,
            char_count=len(self.TAB_TEXT),
        )]
        results = extract_measurements(self.TAB_TEXT, pages, tables)
        abbrs = {m.abbreviation for m in results}
        assert "GLU" in abbrs, f"Expected GLU in {abbrs}"
        assert "BUN" in abbrs, f"Expected BUN in {abbrs}"

    def test_tab_with_headers(self):
        text = (
            "Test\tResult\tUnits\tRange\n"
            "Glucose\t95\tmg/dL\t70-100\n"
            "BUN\t18\tmg/dL\t7-20\n"
        )
        tables = parse_text_tables(text)
        assert len(tables) == 1
        assert tables[0].headers[0] == "Test"
        assert tables[0].headers[1] == "Result"


class TestFixedWidth:
    """Fixed-width / column-aligned tables (Meditech, plain-text printouts)."""

    FIXED_TEXT = (
        "Hemoglobin     14.2  g/dL    12.0-16.0\n"
        "Hematocrit     42.1  %       36.0-46.0\n"
        "WBC            7.5   K/uL    4.5-11.0\n"
    )

    def test_detects_fixed_width_table(self):
        tables = parse_text_tables(self.FIXED_TEXT)
        assert len(tables) == 1

    def test_extracts_measurements_from_fixed_width(self):
        tables = parse_text_tables(self.FIXED_TEXT)
        pages = [PageExtractionResult(
            page_number=1, text=self.FIXED_TEXT,
            extraction_method="direct_input", confidence=1.0,
            char_count=len(self.FIXED_TEXT),
        )]
        results = extract_measurements(self.FIXED_TEXT, pages, tables)
        abbrs = {m.abbreviation for m in results}
        assert "HGB" in abbrs, f"Expected HGB in {abbrs}"
        assert "HCT" in abbrs, f"Expected HCT in {abbrs}"

    def test_correct_fixed_width_values(self):
        tables = parse_text_tables(self.FIXED_TEXT)
        pages = [PageExtractionResult(
            page_number=1, text=self.FIXED_TEXT,
            extraction_method="direct_input", confidence=1.0,
            char_count=len(self.FIXED_TEXT),
        )]
        results = extract_measurements(self.FIXED_TEXT, pages, tables)
        by_abbr = {m.abbreviation: m.value for m in results}
        assert by_abbr["HGB"] == 14.2
        assert by_abbr["HCT"] == 42.1

    def test_meditech_emr_hint(self):
        tables = parse_text_tables(self.FIXED_TEXT, emr_source="meditech")
        assert len(tables) == 1


class TestEdgeCases:
    """Edge cases and empty inputs."""

    def test_empty_text(self):
        assert parse_text_tables("") == []

    def test_whitespace_only(self):
        assert parse_text_tables("   \n  \n  ") == []

    def test_no_tabular_structure(self):
        text = "This is just a plain paragraph of text with no tabular data."
        assert parse_text_tables(text) == []

    def test_separator_lines_skipped(self):
        text = (
            "Component | Value | Units\n"
            "----------|-------|------\n"
            "Sodium    | 138   | mEq/L\n"
            "Potassium | 5.8   | mEq/L\n"
        )
        tables = parse_text_tables(text)
        assert len(tables) == 1
        # Separator line should not appear as a data row
        for row in tables[0].rows:
            assert "---" not in row[0]


class TestFullPipeline:
    """Integration tests via the ExtractionPipeline."""

    EPIC_CBC = (
        "Component | Value | Units | Reference Range\n"
        "WBC       | 7.5   | K/uL  | 4.5-11.0\n"
        "RBC       | 4.8   | M/uL  | 4.2-5.9\n"
        "Hemoglobin| 14.2  | g/dL  | 12.0-16.0\n"
        "Hematocrit| 42.1  | %     | 36.0-46.0\n"
        "Platelets | 250   | K/uL  | 150-400\n"
    )

    def test_pipeline_extract_from_text(self):
        from extraction.pipeline import ExtractionPipeline

        pipeline = ExtractionPipeline()
        result = pipeline.extract_from_text(self.EPIC_CBC)

        assert len(result.tables) > 0, "Pipeline should detect tables in pasted text"
        assert result.tables[0].headers[0] == "Component"
