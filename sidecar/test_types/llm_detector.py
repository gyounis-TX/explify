"""
LLM-based test type detection fallback.

Uses a cheap LLM call to classify a medical report when keyword-based
detection returns low confidence.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from llm.client import LLMClient

logger = logging.getLogger(__name__)


def _build_system_prompt(registry_types: list[dict]) -> str:
    """Build classifier prompt from currently registered types.

    Groups types by category for readability and omits keyword listings
    to keep the prompt compact as the type count grows.
    """
    lines = [
        "You are a medical report classifier. Given the text of a medical "
        "report, identify which type of test it represents.",
        "",
        "Available test types (grouped by category):",
    ]

    # Group by category
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in registry_types:
        groups[t.get("category", "other")].append(t)

    # Pretty labels for category headers
    category_labels = {
        "cardiac": "Cardiac",
        "interventional": "Interventional / Procedures",
        "vascular": "Vascular",
        "lab": "Laboratory",
        "imaging_ct": "CT Imaging",
        "imaging_mri": "MRI",
        "imaging_ultrasound": "Ultrasound",
        "imaging_xray": "X-Ray / Radiography",
        "pulmonary": "Pulmonary",
        "neurophysiology": "Neurophysiology",
        "endoscopy": "Endoscopy",
        "pathology": "Pathology",
        "allergy": "Allergy / Immunology",
        "dermatology": "Dermatology",
        "other": "Other",
    }

    idx = 1
    for cat, cat_types in groups.items():
        label = category_labels.get(cat, cat.replace("_", " ").title())
        lines.append(f"\n[{label}]")
        for t in cat_types:
            lines.append(f"  {idx}. {t['test_type_id']} — {t['display_name']}")
            idx += 1

    lines.append("")
    lines.append(
        "If the report is a body-part-specific variant of a modality "
        "(e.g., MRI Lumbar Spine), map to the modality-level type (e.g., mri). "
        "Prefer specific types when they exist (e.g., use ct_chest for a chest CT, "
        "not ct_scan; use chest_xray for a chest X-ray, not xray)."
    )
    lines.append("")
    lines.append(
        'Respond with a JSON object only — no markdown, no explanation:\n'
        '{"test_type_id": "<id>", "display_name": "<name>", '
        '"confidence": <0.0-1.0>, "reasoning": "<one sentence>"}'
    )
    lines.append(
        "PHARMACOLOGIC STRESS MAPPING: If the report mentions lexiscan, "
        "regadenoson, adenosine, or dipyridamole, it is a pharmacologic "
        "(not exercise) stress test. If it mentions dobutamine, it is "
        "pharmacologic — and if combined with echocardiogram/echo, it is "
        "pharma_stress_echo. Map SPECT/sestamibi/technetium to the SPECT "
        "variants, and PET/rubidium/Rb-82/positron to the PET variants."
    )
    lines.append("")
    lines.append(
        "If the report does not match any listed type, use the CLOSEST "
        "match or create a descriptive snake_case ID."
    )
    return "\n".join(lines)


def _build_structured_excerpt(
    report_text: str,
    tables: list[dict] | None = None,
    keyword_candidates: list[tuple[str, float]] | None = None,
    max_chars: int = 2500,
) -> str:
    """Build a structured excerpt that preserves diagnostic content.

    Sections (in priority order):
    1. Header (first 800 chars) — report title, patient info, procedure name
    2. Section headers — extracted via regex scan of full text
    3. Table headers — from extracted tables
    4. Keyword hints — top candidates from keyword detection
    5. Tail (last 400 chars) — impressions/conclusions often at end
    6. Middle sample — fills remaining budget from middle of report
    """
    parts: list[str] = []
    budget = max_chars

    # 1. Header
    header = report_text[:800].strip()
    parts.append(f"[HEADER]\n{header}")
    budget -= len(header) + 10

    # 2. Section headers (scan full text)
    section_re = re.compile(
        r"(?m)^[A-Z][A-Z\s/&]{3,50}:\s*$|"
        r"(?m)^(?:IMPRESSION|FINDINGS|CONCLUSION|INDICATION|TECHNIQUE|"
        r"COMPARISON|PROCEDURE|REPORT|RESULT)[S]?\s*[:\-]",
    )
    headers_found = [m.group().strip() for m in section_re.finditer(report_text)]
    if headers_found:
        header_block = "Section headers found: " + ", ".join(dict.fromkeys(headers_found))
        parts.append(f"\n[SECTION HEADERS]\n{header_block}")
        budget -= len(header_block) + 20

    # 3. Table headers
    if tables:
        table_info = []
        for t in tables[:3]:
            hdrs = t.get("headers", [])
            if hdrs:
                table_info.append(f"Table (p{t.get('page_number', '?')}): {' | '.join(hdrs)}")
        if table_info:
            block = "\n".join(table_info)
            parts.append(f"\n[TABLE HEADERS]\n{block}")
            budget -= len(block) + 20

    # 4. Keyword hints
    if keyword_candidates:
        hints = [f"{tid} ({conf:.0%})" for tid, conf in keyword_candidates[:5]]
        hint_block = "Keyword detection candidates: " + ", ".join(hints)
        parts.append(f"\n[KEYWORD HINTS]\n{hint_block}")
        budget -= len(hint_block) + 20

    # 5. Tail
    tail_size = min(400, budget // 3)
    if len(report_text) > 800 + tail_size:
        tail = report_text[-tail_size:].strip()
        parts.append(f"\n[TAIL]\n{tail}")
        budget -= len(tail) + 10

    # 6. Middle sample (fill remaining budget)
    if budget > 200 and len(report_text) > 1600:
        mid_start = len(report_text) // 3
        mid_sample = report_text[mid_start:mid_start + budget].strip()
        parts.append(f"\n[MIDDLE]\n{mid_sample}")

    return "\n".join(parts)


async def llm_detect_test_type(
    client: LLMClient,
    report_text: str,
    user_hint: Optional[str] = None,
    registry_types: list[dict] | None = None,
    tables: list[dict] | None = None,
    keyword_candidates: list[tuple[str, float]] | None = None,
) -> tuple[Optional[str], float, Optional[str]]:
    """Classify a medical report using an LLM.

    Returns (test_type_id, confidence, display_name) or (None, 0.0, None)
    on any failure.
    """
    if registry_types is None:
        registry_types = []

    system_prompt = _build_system_prompt(registry_types)

    # Build structured excerpt instead of blind truncation
    truncated = _build_structured_excerpt(
        report_text, tables=tables, keyword_candidates=keyword_candidates,
    )

    user_prompt = f"Report text:\n\n{truncated}"
    if user_hint:
        user_prompt += f'\n\nThe user describes this report as: "{user_hint}"'

    try:
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=200,
            temperature=0.0,
        )

        raw = response.text_content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        parsed = json.loads(raw)
        type_id = parsed.get("test_type_id")
        confidence = float(parsed.get("confidence", 0.0))
        display_name = parsed.get("display_name")

        logger.info(
            "LLM detection: type=%s confidence=%.2f display=%s reasoning=%s",
            type_id,
            confidence,
            display_name,
            parsed.get("reasoning", ""),
        )
        return (type_id, confidence, display_name)

    except Exception:
        logger.exception("LLM test type detection failed")
        return (None, 0.0, None)
