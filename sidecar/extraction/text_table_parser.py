"""Detect and parse tabular structure from pasted text.

When physicians copy-paste lab results from EMRs (Epic, Cerner, Meditech),
the text often has tabular structure (pipe-delimited, tab-delimited, or
fixed-width columns). This module detects that structure and converts it
to ExtractedTable objects so the existing table-matching infrastructure
in measurements.py can extract values.

Detection priority:
1. Pipe-delimited  — e.g. "Component | Value | Units | Range"
2. Tab-delimited   — e.g. "Glucose\t95\tmg/dL\t70-100"
3. Fixed-width      — e.g. "Hemoglobin     14.2  g/dL    12.0-16.0"
"""

from __future__ import annotations

import re

from api.models import ExtractedTable


# Minimum columns to consider a line "tabular"
_MIN_COLS = 2

# Lines that are purely separators (dashes, equals, underscores)
_SEPARATOR_LINE = re.compile(r"^[\s\-=_|+]+$")

# Lines that are blank or only whitespace
_BLANK_LINE = re.compile(r"^\s*$")

# Common lab units — used to identify unit columns in headerless tables
_UNIT_PATTERNS = re.compile(
    r"^(?:"
    r"mg/dL|g/dL|ng/dL|ug/dL|pg/mL|ng/mL|IU/mL|"
    r"mmol/L|umol/L|mEq/L|"
    r"U/L|mU/L|IU/L|"
    r"cells/uL|cells/mcL|x10[Ee]?[369]/uL|10\^[369]/uL|K/uL|M/uL|"
    r"mL/min(?:/1\.73m2)?|"
    r"mm/hr|sec|seconds|%|fL|pg|g/L|ratio|index|"
    r"mIU/L|mIU/mL|uIU/mL|"
    r"mg/L|ug/L|ng/L|"
    r"mmHg|bpm|cm|mm|mL|L"
    r")$",
    re.IGNORECASE,
)


def parse_text_tables(
    text: str,
    emr_source: str | None = None,
) -> list[ExtractedTable]:
    """Detect and parse tabular structure from pasted text.

    Returns a list of ExtractedTable objects suitable for the existing
    _extract_from_tables() pipeline in measurements.py.
    """
    if not text or not text.strip():
        return []

    lines = text.splitlines()

    # Try detection strategies in priority order
    # EMR hints can bias priority but we always try all strategies

    if emr_source == "epic":
        # Epic strongly prefers pipe
        result = _try_pipe_delimited(lines)
        if result:
            return result
        result = _try_tab_delimited(lines)
        if result:
            return result
        return _try_fixed_width(lines)

    if emr_source == "meditech":
        # Meditech prefers fixed-width
        result = _try_fixed_width(lines)
        if result:
            return result
        result = _try_pipe_delimited(lines)
        if result:
            return result
        return _try_tab_delimited(lines)

    # Default order: pipe > tab > fixed-width
    result = _try_pipe_delimited(lines)
    if result:
        return result
    result = _try_tab_delimited(lines)
    if result:
        return result
    return _try_fixed_width(lines)


def _is_data_line(line: str) -> bool:
    """Return False for blank lines or separator lines."""
    return not _BLANK_LINE.match(line) and not _SEPARATOR_LINE.match(line)


def _try_pipe_delimited(lines: list[str]) -> list[ExtractedTable]:
    """Detect and parse pipe-delimited tables."""
    # Count lines with pipes (scan first 30 lines for detection)
    scan_lines = lines[:30]
    pipe_lines = [l for l in scan_lines if "|" in l and _is_data_line(l)]

    if len(pipe_lines) < 2:
        return []

    # Find header row: the first pipe-delimited line
    header_line_idx = None
    for i, line in enumerate(lines):
        if "|" in line and _is_data_line(line):
            header_line_idx = i
            break

    if header_line_idx is None:
        return []

    headers = _split_pipe(lines[header_line_idx])
    if len(headers) < _MIN_COLS:
        return []

    # Parse remaining lines as rows
    rows: list[list[str]] = []
    expected_cols = len(headers)

    for line in lines[header_line_idx + 1:]:
        if not _is_data_line(line):
            continue
        if "|" not in line:
            continue
        cells = _split_pipe(line)
        # Allow ±1 column mismatch
        if abs(len(cells) - expected_cols) <= 1:
            # Pad or trim to match header count
            while len(cells) < expected_cols:
                cells.append("")
            rows.append(cells[:expected_cols])

    if not rows:
        return []

    return [ExtractedTable(
        page_number=1,
        table_index=0,
        headers=headers,
        rows=rows,
    )]


def _split_pipe(line: str) -> list[str]:
    """Split a pipe-delimited line, stripping whitespace from cells."""
    parts = line.split("|")
    # Strip leading/trailing empty cells from outer pipes
    cells = [p.strip() for p in parts]
    # Remove empty leading/trailing cells (from lines like "| a | b |")
    while cells and not cells[0]:
        cells.pop(0)
    while cells and not cells[-1]:
        cells.pop()
    return cells


def _try_tab_delimited(lines: list[str]) -> list[ExtractedTable]:
    """Detect and parse tab-delimited tables."""
    scan_lines = lines[:30]
    tab_lines = [l for l in scan_lines if "\t" in l and _is_data_line(l)]

    if len(tab_lines) < 2:
        return []

    # Check if the first tab-delimited line looks like a header
    first_tab_idx = None
    for i, line in enumerate(lines):
        if "\t" in line and _is_data_line(line):
            first_tab_idx = i
            break

    if first_tab_idx is None:
        return []

    first_cells = lines[first_tab_idx].split("\t")
    first_cells = [c.strip() for c in first_cells]

    # Determine if first line is a header or data
    # If any cell in first line looks like a known header keyword, treat as header
    header_keywords = {"test", "result", "value", "units", "unit",
                       "reference", "range", "flag", "status", "analyte",
                       "component", "name", "investigation", "parameter",
                       "observed", "normal"}

    has_header = any(
        c.lower().strip() in header_keywords for c in first_cells
    )

    if has_header:
        headers = first_cells
        data_start = first_tab_idx + 1
    else:
        data_start = first_tab_idx

    expected_cols = len(first_cells)
    if expected_cols < _MIN_COLS:
        return []

    rows: list[list[str]] = []

    for line in lines[data_start:]:
        if not _is_data_line(line):
            continue
        if "\t" not in line:
            continue
        cells = [c.strip() for c in line.split("\t")]
        if abs(len(cells) - expected_cols) <= 1:
            while len(cells) < expected_cols:
                cells.append("")
            rows.append(cells[:expected_cols])

    if not rows:
        return []

    if not has_header:
        # Synthesize headers using content analysis of the parsed rows
        headers = _synthesize_headers(expected_cols, sample_rows=rows[:10])

    return [ExtractedTable(
        page_number=1,
        table_index=0,
        headers=headers,
        rows=rows,
    )]


def _try_fixed_width(lines: list[str]) -> list[ExtractedTable]:
    """Detect and parse fixed-width / column-aligned tables.

    Detects columns by finding consistent multi-space gaps across lines.
    """
    data_lines = [l for l in lines if _is_data_line(l)]

    if len(data_lines) < 2:
        return []

    # Check that lines have multi-space gaps (at least 2 spaces between tokens)
    multi_space_lines = [
        l for l in data_lines[:30]
        if re.search(r"\S\s{2,}\S", l)
    ]

    if len(multi_space_lines) < 2:
        return []

    # Split each line on 2+ spaces to get cells
    parsed_lines: list[list[str]] = []
    for line in data_lines:
        cells = re.split(r"\s{2,}", line.strip())
        cells = [c.strip() for c in cells if c.strip()]
        if len(cells) >= _MIN_COLS:
            parsed_lines.append(cells)

    if len(parsed_lines) < 2:
        return []

    # Use modal column count
    col_counts = [len(row) for row in parsed_lines]
    modal_cols = max(set(col_counts), key=col_counts.count)

    # Filter to lines matching modal column count (±1)
    filtered = [row for row in parsed_lines if abs(len(row) - modal_cols) <= 1]

    if len(filtered) < 2:
        return []

    # Check if first row is a header
    header_keywords = {"test", "result", "value", "units", "unit",
                       "reference", "range", "flag", "status", "analyte",
                       "component", "name", "investigation", "parameter"}

    first_row = filtered[0]
    has_header = any(
        c.lower().strip() in header_keywords for c in first_row
    )

    if has_header:
        headers = first_row
        data_rows = filtered[1:]
    else:
        data_rows = filtered

    # Normalize rows to header length
    target_cols = len(headers) if has_header else modal_cols
    rows: list[list[str]] = []
    for row in data_rows:
        while len(row) < target_cols:
            row.append("")
        rows.append(row[:target_cols])

    if not rows:
        return []

    if not has_header:
        # Synthesize headers using content analysis of the parsed rows
        headers = _synthesize_headers(modal_cols, sample_rows=rows[:10])

    return [ExtractedTable(
        page_number=1,
        table_index=0,
        headers=headers,
        rows=rows,
    )]


def _synthesize_headers(
    num_cols: int,
    sample_rows: list[list[str]] | None = None,
) -> list[str]:
    """Generate synthetic headers for headerless tables.

    Uses common lab column order: Name, Value, Units, Range, Flag.
    If sample_rows are provided, uses content analysis to detect unit and
    range columns for more accurate header assignment.
    """
    default_names = ["Name", "Value", "Units", "Range", "Flag"]
    if num_cols <= len(default_names) and not sample_rows:
        return default_names[:num_cols]
    if not sample_rows:
        return default_names + [f"Col{i}" for i in range(len(default_names), num_cols)]

    # Content-based header detection
    headers = [""] * num_cols
    headers[0] = "Name"  # First column is always the test name

    for col in range(1, num_cols):
        col_vals = [
            row[col].strip() for row in sample_rows
            if col < len(row) and row[col].strip()
        ]
        if not col_vals:
            continue

        # Check if column looks like units
        unit_matches = sum(1 for v in col_vals if _UNIT_PATTERNS.match(v))
        if unit_matches >= len(col_vals) * 0.4 and unit_matches >= 2:
            headers[col] = "Units"
            continue

        # Check if column looks like a reference range (e.g. "70-100", "<200", "0.4-4.0")
        range_matches = sum(
            1 for v in col_vals
            if re.match(r"^[<>]?\s*\d+\.?\d*\s*[-–]\s*\d+\.?\d*$", v)
            or re.match(r"^[<>]\s*\d+\.?\d*$", v)
        )
        if range_matches >= len(col_vals) * 0.3 and range_matches >= 2:
            headers[col] = "Range"
            continue

        # Check if column looks like flags (H, L, HH, LL, A, *)
        flag_matches = sum(
            1 for v in col_vals
            if re.match(r"^[HLA\*]{1,2}$", v, re.IGNORECASE)
        )
        if flag_matches >= len(col_vals) * 0.2 and flag_matches >= 1:
            headers[col] = "Flag"
            continue

        # Check if column looks like numeric values
        num_matches = sum(
            1 for v in col_vals
            if re.match(r"^[<>]?\s*\d+\.?\d*$", v)
        )
        if num_matches >= len(col_vals) * 0.5:
            headers[col] = "Value" if "Value" not in headers else f"Value{col}"

    # Fill remaining empty headers with defaults
    used = {h for h in headers if h}
    for i in range(num_cols):
        if not headers[i]:
            for default in default_names:
                if default not in used:
                    headers[i] = default
                    used.add(default)
                    break
            else:
                headers[i] = f"Col{i}"

    return headers
