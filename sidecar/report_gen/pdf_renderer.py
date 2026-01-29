"""Render an ExplainResponse dict into a PDF report using WeasyPrint."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
import weasyprint

TEMPLATES_DIR = Path(__file__).parent / "templates"

SEVERITY_LABELS: dict[str, str] = {
    "normal": "Normal",
    "mildly_abnormal": "Mildly Abnormal",
    "moderately_abnormal": "Moderately Abnormal",
    "severely_abnormal": "Severely Abnormal",
    "undetermined": "Undetermined",
}

SEVERITY_ICONS: dict[str, str] = {
    "normal": "\u2713",
    "mildly_abnormal": "\u26A0",
    "moderately_abnormal": "\u25B2",
    "severely_abnormal": "\u2716",
    "undetermined": "\u2014",
}

FINDING_SEVERITY_ICONS: dict[str, str] = {
    "normal": "\u2713",
    "mild": "\u26A0",
    "moderate": "\u25B2",
    "severe": "\u2716",
    "informational": "\u24D8",
}


def render_pdf(explain_response: dict) -> bytes:
    """Convert an ExplainResponse dict into PDF bytes."""
    explanation = explain_response.get("explanation", {})
    parsed_report = explain_response.get("parsed_report", {})

    # Build measurement lookup for reference ranges
    measurement_map: dict[str, dict] = {}
    for m in parsed_report.get("measurements", []):
        measurement_map[m["abbreviation"]] = m

    # Enrich explanation measurements with reference ranges
    measurements = []
    for m in explanation.get("measurements", []):
        parsed = measurement_map.get(m.get("abbreviation", ""), {})
        measurements.append({
            **m,
            "reference_range": parsed.get("reference_range", "--"),
        })

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html")

    html_str = template.render(
        test_type_display=parsed_report.get("test_type_display", "Medical Report"),
        summary=explanation.get("overall_summary", ""),
        findings=explanation.get("key_findings", []),
        measurements=measurements,
        questions=explanation.get("questions_for_doctor", []),
        disclaimer=explanation.get("disclaimer", ""),
        severity_labels=SEVERITY_LABELS,
        severity_icons=SEVERITY_ICONS,
        finding_severity_icons=FINDING_SEVERITY_ICONS,
        generated_date=date.today().isoformat(),
    )

    css_path = TEMPLATES_DIR / "report.css"
    css = weasyprint.CSS(filename=str(css_path))
    pdf_bytes = weasyprint.HTML(string=html_str).write_pdf(stylesheets=[css])
    return pdf_bytes
