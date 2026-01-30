"""
Prompt construction for medical report explanation.

Builds a system prompt (role, rules, anti-hallucination constraints)
and a user prompt (parsed report data, reference ranges, glossary).
"""

from __future__ import annotations

from enum import Enum

from api.analysis_models import ParsedReport


class LiteracyLevel(str, Enum):
    GRADE_4 = "grade_4"
    GRADE_6 = "grade_6"
    GRADE_8 = "grade_8"
    GRADE_12 = "grade_12"
    CLINICAL = "clinical"


_LITERACY_DESCRIPTIONS: dict[LiteracyLevel, str] = {
    LiteracyLevel.GRADE_4: (
        "Write at a 4th-grade reading level. Use very simple words and short "
        "sentences. Avoid all medical jargon. Use analogies a child could "
        "understand."
    ),
    LiteracyLevel.GRADE_6: (
        "Write at a 6th-grade reading level. Use simple, clear language. "
        "Briefly define medical terms when you must use them. Keep sentences "
        "short."
    ),
    LiteracyLevel.GRADE_8: (
        "Write at an 8th-grade reading level. Use clear language, briefly "
        "defining technical terms. Moderate sentence complexity is acceptable."
    ),
    LiteracyLevel.GRADE_12: (
        "Write at a 12th-grade reading level. Use natural adult language "
        "with medical terms introduced in context. Assume a well-educated "
        "reader who is not a medical professional."
    ),
    LiteracyLevel.CLINICAL: (
        "Write at a clinical level suitable for a healthcare professional. "
        "Use standard medical terminology. Be precise and concise."
    ),
}


_TONE_DESCRIPTIONS: dict[int, str] = {
    1: (
        "Be direct and clinical about all findings, including abnormal ones. "
        "Do not sugarcoat or minimize concerning results. State facts plainly."
    ),
    2: (
        "Be matter-of-fact and straightforward. State findings clearly "
        "without adding extra reassurance. Keep the tone professional."
    ),
    3: (
        "Balance clinical precision with empathy. Acknowledge concerning "
        "findings while providing appropriate context. Use a calm, "
        "neutral tone."
    ),
    4: (
        "Emphasize positive and normal findings. Frame concerns gently "
        "with reassuring context. Use warm, supportive language."
    ),
    5: (
        "Lead with good news and normal findings. Be warm, empathetic, "
        "and comforting throughout. Minimize alarm for abnormal findings "
        "while still being accurate. Emphasize that doctors will guide "
        "next steps."
    ),
}

_DETAIL_DESCRIPTIONS: dict[int, str] = {
    1: (
        "Be extremely brief. Provide only the most essential information. "
        "Use short summaries of 1-2 sentences. Omit background and context."
    ),
    2: (
        "Be concise. Cover key points only with short explanations. "
        "Summaries should be 2-3 sentences. Minimal background detail."
    ),
    3: (
        "Provide a standard level of detail. Summaries of 4-6 sentences. "
        "Include enough context to understand each finding."
    ),
    4: (
        "Be thorough. Include additional context, background information, "
        "and expanded explanations for each finding and measurement. "
        "Summaries of 5-8 sentences."
    ),
    5: (
        "Be very comprehensive. Provide detailed explanations with full "
        "clinical context for every finding. Include background on what "
        "each measurement means and why it matters. Summaries of 6-10 "
        "sentences."
    ),
}


class PromptEngine:
    """Constructs system and user prompts for report explanation."""

    def build_system_prompt(
        self,
        literacy_level: LiteracyLevel,
        prompt_context: dict,
        tone_preference: int = 3,
        detail_preference: int = 3,
        physician_name: str | None = None,
        short_comment: bool = False,
        explanation_voice: str = "third_person",
        name_drop: bool = True,
        short_comment_char_limit: int | None = 1000,
    ) -> str:
        """Build the system prompt with role, rules, and constraints."""
        specialty = prompt_context.get("specialty", "general medicine")

        physician_section = ""
        if explanation_voice == "first_person":
            physician_section = (
                "## Physician Voice\n"
                "Write as if you ARE the physician speaking directly to the patient. "
                "Use first-person language: \"I have reviewed your results\", "
                "\"I would recommend\", \"In my assessment\". "
                "NEVER use third-person references like \"your doctor\" or "
                "\"your physician\".\n\n"
            )
        elif physician_name:
            attribution = ""
            if name_drop:
                attribution = (
                    f" Include at least one explicit attribution phrase such as "
                    f"\"{physician_name} has reviewed your results\" or "
                    f"\"{physician_name} recommends\"."
                )
            physician_section = (
                f"## Physician Attribution\n"
                f"When referring to the patient's doctor, use \"{physician_name}\" "
                f"instead of generic phrases like \"your doctor\", \"your physician\", "
                f"or \"your healthcare provider\". For example, write "
                f"\"{physician_name} may want to discuss...\" instead of "
                f"\"Your doctor may want to discuss...\".{attribution}\n\n"
            )

        if short_comment:
            if short_comment_char_limit is not None:
                target = int(short_comment_char_limit * 0.9)
                hard_limit = short_comment_char_limit
                length_constraint = (
                    f"- Target maximum {target} characters; NEVER exceed {hard_limit} characters.\n"
                    f"- Keep line width narrow (short lines, not long paragraphs).\n"
                )
                length_rule = (
                    f"5. Keep the entire overall_summary under {hard_limit} characters."
                )
            else:
                length_constraint = (
                    "- No strict character limit, but keep the comment concise and focused.\n"
                    "- Keep line width narrow (short lines, not long paragraphs).\n"
                )
                length_rule = (
                    "5. Keep the overall_summary concise but cover all relevant findings."
                )

            return (
                f"You are a medical report explanation assistant specializing "
                f"in {specialty}.\n"
                f"Your task is to produce a patient-facing Epic Results Comment "
                f"optimized for Epic's narrow, mobile-first display.\n\n"
                f"## Output Constraints\n"
                f"{length_constraint}"
                f"- Plain text ONLY — no markdown, no emojis, no rich text, no special formatting.\n"
                f"- Avoid nested bullets or indentation.\n\n"
                f"## Formatting Rules\n"
                f"- Headers: ALL CAPS. No bold, no symbols, no separators other than line breaks.\n"
                f"- Paragraphs: Maximum 2-3 short sentences per block. One blank line between sections.\n"
                f"- Lists: Prefer short labeled lines over bullet lists.\n"
                f"  Example:\n"
                f"  Key numbers:\n"
                f"  LVEF 50%\n\n"
                f"## Required Sections (in this order)\n"
                f"1. HEADER — One-line test type summary, e.g. HEART ULTRASOUND SUMMARY\n"
                f"2. REASSURANCE BLOCK — 1-2 sentences covering: pumping function, "
                f"right heart status, pericardial fluid (if relevant).\n"
                f"3. MAIN FINDINGS BLOCK — 2-3 sentences covering: primary abnormality "
                f"(e.g. valve disease), symptom connection, chamber changes if relevant.\n"
                f"4. KEY NUMBERS BLOCK — 1-2 lines only. No parentheticals or long explanations.\n"
                f"5. NEXT STEPS BLOCK — 1-2 sentences. Clear action or follow-up.\n"
                f"6. FOOTER (optional) — Brief sign-off if space allows.\n\n"
                f"{physician_section}"
                f"## Critical Rules\n"
                f"1. ONLY use data from the report. NEVER invent findings.\n"
                f"2. Use the status provided (normal, mildly_abnormal, etc.) — do NOT re-classify.\n"
                f"3. Do NOT mention the patient by name or include PHI.\n"
                f"4. Call the explain_report tool. Put the short comment in overall_summary.\n"
                f"{length_rule}"
            )

        literacy_desc = _LITERACY_DESCRIPTIONS[literacy_level]
        guidelines = prompt_context.get("guidelines", "standard clinical guidelines")
        explanation_style = prompt_context.get("explanation_style", "")
        tone = prompt_context.get("tone", "")

        tone_section = f"## Tone\n{tone}\n\n" if tone else ""

        tone_pref = _TONE_DESCRIPTIONS.get(tone_preference, _TONE_DESCRIPTIONS[3])
        detail_pref = _DETAIL_DESCRIPTIONS.get(detail_preference, _DETAIL_DESCRIPTIONS[3])

        return (
            f"You are a medical report explanation assistant specializing "
            f"in {specialty}.\n"
            f"Your task is to explain a medical report to a patient in "
            f"plain language.\n\n"
            f"## Literacy Level\n{literacy_desc}\n\n"
            f"## Clinical Guidelines\n"
            f"Base your interpretations on: {guidelines}\n\n"
            f"## Explanation Style\n{explanation_style}\n\n"
            f"{tone_section}"
            f"## Tone Preference\n{tone_pref}\n\n"
            f"## Detail Level\n{detail_pref}\n\n"
            f"{physician_section}"
            f"## Tone and Language Style\n"
            f"Use hedging language "
            f"throughout to reflect the inherent uncertainty in medical "
            f"interpretation.\n"
            f"- Use: \"may\", \"appears to\", \"could suggest\", "
            f"\"seems to indicate\"\n"
            f"- Avoid: \"is\", \"shows\", \"proves\", \"confirms\"\n"
            f"- Example: \"Your heart appears to be functioning normally\" "
            f"not \"Your heart is normal\"\n"
            f"- Frame abnormalities gently, e.g. \"something your doctor "
            f"may want to look into further\"\n\n"
            f"## Critical Rules\n"
            f"1. ONLY use data that appears in the report provided. "
            f"NEVER invent, guess, or assume measurements, findings, or "
            f"diagnoses that are not explicitly stated.\n"
            f"2. For each measurement, the app has already classified it "
            f"against reference ranges. You MUST use the status provided "
            f"(normal, mildly_abnormal, etc.) -- do NOT re-classify.\n"
            f"3. When explaining a measurement, always mention the patient's "
            f"value, the normal range, and what the status means.\n"
            f"4. If a measurement has status \"undetermined\", say the value "
            f"was noted but cannot be classified without more context.\n"
            f"5. Do NOT mention the patient by name or include any personally "
            f"identifying information.\n"
            f"6. Call the explain_report tool with your response. Do not "
            f"produce any output outside of this tool call.\n"
            f"7. Provide comprehensive, reassuring summaries of 4-6 sentences. "
            f"Lead with positive or normal findings. Frame any concerning "
            f"findings gently, emphasizing that a doctor will provide proper "
            f"interpretation and next steps."
        )

    def build_user_prompt(
        self,
        parsed_report: ParsedReport,
        reference_ranges: dict,
        glossary: dict[str, str],
        scrubbed_text: str,
        clinical_context: str | None = None,
        template_instructions: str | None = None,
        closing_text: str | None = None,
        refinement_instruction: str | None = None,
        liked_examples: list[dict] | None = None,
        next_steps: list[str] | None = None,
    ) -> str:
        """Build the user prompt with report data, ranges, and glossary."""
        sections: list[str] = []

        # 1. Report text (scrubbed)
        sections.append("## Report Text (PHI Removed)")
        sections.append(scrubbed_text)

        # 1b. Clinical context (if provided)
        if clinical_context:
            sections.append("\n## Clinical Context")
            sections.append(
                f"The clinical reason for this test: {clinical_context}\n"
                f"Prioritize findings relevant to this clinical context in your explanation."
            )

        # 1c. Next steps to include (if provided)
        if next_steps and any(s != "No comment" for s in next_steps):
            sections.append("\n## Next Steps to Include")
            sections.append(
                "The physician has selected these next steps for the patient. Naturally weave\n"
                "them into your overall_summary where appropriate:"
            )
            for step in next_steps:
                if step != "No comment":
                    sections.append(f"- {step}")

        # 1d. Template instructions (if provided)
        if template_instructions:
            sections.append("\n## Structure Instructions")
            sections.append(template_instructions)
        if closing_text:
            sections.append("\n## Closing Text")
            sections.append(
                f"End the overall_summary with the following closing text:\n{closing_text}"
            )

        # 1e. Preferred output style from liked examples
        if liked_examples:
            sections.append("\n## Preferred Output Style")
            sections.append(
                "The user has indicated they prefer explanations similar to the following examples.\n"
                "Match their style, tone, level of detail, and structure as closely as possible\n"
                "while using ONLY the data from the current report."
            )
            for idx, example in enumerate(liked_examples, 1):
                sections.append(f"\n### Example {idx}")
                sections.append(f"**Summary:** {example['overall_summary']}")
                key_findings = example.get("key_findings", [])
                if key_findings:
                    sections.append("**Key findings:**")
                    for kf in key_findings:
                        finding = kf.get("finding", "")
                        explanation = kf.get("explanation", "")
                        sections.append(f"- {finding}: {explanation}")

        # 2. Parsed measurements with reference ranges
        sections.append("\n## Parsed Measurements")
        if parsed_report.measurements:
            for m in parsed_report.measurements:
                ref_info = ""
                if m.abbreviation in reference_ranges:
                    rr = reference_ranges[m.abbreviation]
                    parts: list[str] = []
                    if rr.get("normal_min") is not None:
                        parts.append(f"min={rr['normal_min']}")
                    if rr.get("normal_max") is not None:
                        parts.append(f"max={rr['normal_max']}")
                    if parts:
                        ref_info = (
                            f" | Normal range: {', '.join(parts)} "
                            f"{rr.get('unit', '')}"
                        )

                sections.append(
                    f"- {m.name} ({m.abbreviation}): {m.value} {m.unit} "
                    f"[status: {m.status.value}]{ref_info}"
                )
        else:
            sections.append("No structured measurements were extracted.")

        # 3. Findings
        if parsed_report.findings:
            sections.append("\n## Report Findings/Conclusions")
            for f in parsed_report.findings:
                sections.append(f"- {f}")

        # 4. Sections
        if parsed_report.sections:
            sections.append("\n## Report Sections")
            for s in parsed_report.sections:
                sections.append(f"### {s.name}")
                sections.append(s.content)

        # 5. Glossary
        sections.append(
            "\n## Glossary (use these definitions when explaining terms)"
        )
        for term, definition in glossary.items():
            sections.append(f"- **{term}**: {definition}")

        # 6. Refinement instruction (if provided)
        if refinement_instruction:
            sections.append("\n## Refinement Instruction")
            sections.append(refinement_instruction)

        # 7. Instructions
        sections.append(
            "\n## Instructions\n"
            "Using ONLY the data above, generate a structured explanation by "
            "calling the explain_report tool. Include all measurements listed "
            "above. Do not add measurements or findings not present in the data."
        )

        return "\n".join(sections)
