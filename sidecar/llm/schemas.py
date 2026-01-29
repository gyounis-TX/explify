"""
Structured output schema for the explain_report tool.

Used as tool input_schema (Claude) or function parameters (OpenAI)
to force structured JSON output from the LLM.
"""

EXPLANATION_TOOL_NAME = "explain_report"

EXPLANATION_TOOL_SCHEMA: dict = {
    "type": "object",
    "required": [
        "overall_summary",
        "measurements",
        "key_findings",
        "questions_for_doctor",
        "disclaimer",
    ],
    "properties": {
        "overall_summary": {
            "type": "string",
            "description": (
                "A 2-4 sentence plain-language summary of what the report shows. "
                "Written at the requested literacy level. Must not invent data."
            ),
        },
        "measurements": {
            "type": "array",
            "description": "One entry per parsed measurement from the report.",
            "items": {
                "type": "object",
                "required": [
                    "abbreviation",
                    "value",
                    "unit",
                    "status",
                    "plain_language",
                ],
                "properties": {
                    "abbreviation": {
                        "type": "string",
                        "description": "The measurement abbreviation, e.g. 'LVEF'.",
                    },
                    "value": {
                        "type": "number",
                        "description": "The numeric value from the report.",
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit of measurement.",
                    },
                    "status": {
                        "type": "string",
                        "enum": [
                            "normal",
                            "mildly_abnormal",
                            "moderately_abnormal",
                            "severely_abnormal",
                            "undetermined",
                        ],
                        "description": "Severity classification.",
                    },
                    "plain_language": {
                        "type": "string",
                        "description": (
                            "1-2 sentence explanation of what this measurement "
                            "means and whether it is normal, at the requested "
                            "literacy level."
                        ),
                    },
                },
            },
        },
        "key_findings": {
            "type": "array",
            "description": (
                "3-8 key findings from the report, each a short "
                "plain-language sentence."
            ),
            "items": {
                "type": "object",
                "required": ["finding", "severity", "explanation"],
                "properties": {
                    "finding": {
                        "type": "string",
                        "description": "Brief finding statement.",
                    },
                    "severity": {
                        "type": "string",
                        "enum": [
                            "normal",
                            "mild",
                            "moderate",
                            "severe",
                            "informational",
                        ],
                        "description": "Severity level of this finding.",
                    },
                    "explanation": {
                        "type": "string",
                        "description": (
                            "1-3 sentence plain-language explanation of what "
                            "this finding means for the patient."
                        ),
                    },
                },
            },
        },
        "questions_for_doctor": {
            "type": "array",
            "description": (
                "2-5 questions the patient might want to ask their doctor "
                "based on these results."
            ),
            "items": {"type": "string"},
        },
        "disclaimer": {
            "type": "string",
            "description": (
                "A brief disclaimer that this is an AI-generated explanation, "
                "not medical advice, and that the patient should discuss results "
                "with their healthcare provider."
            ),
        },
    },
}
