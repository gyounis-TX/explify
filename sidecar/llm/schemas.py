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
    ],
    "properties": {
        "overall_summary": {
            "type": "string",
            "description": (
                "A 4-6 sentence plain-language summary providing a comprehensive "
                "overview of what the report shows. Lead with positive or normal "
                "findings. Use a warm, reassuring tone and frame any concerning "
                "findings gently. Written at the requested literacy level. "
                "Must not invent data."
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
    },
}
