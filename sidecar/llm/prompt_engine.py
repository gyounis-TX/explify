"""
Prompt construction for medical report explanation.

Builds a system prompt (role, rules, anti-hallucination constraints)
and a user prompt (parsed report data, reference ranges, glossary).

Clinical Voice Rule: All outputs follow "Doctor Interpretation Mode" —
structured around clinical reasoning, not neutral summaries.
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
        "4th-grade level. Very simple words, short sentences. "
        "No medical jargon — use everyday analogies. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.GRADE_6: (
        "6th-grade level. Simple, clear language. Short sentences. "
        "Briefly define any medical term you must use. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.GRADE_8: (
        "8th-grade level. Clear language with brief definitions of "
        "technical terms. Moderate sentence complexity is acceptable. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.GRADE_12: (
        "12th-grade / college level. Natural adult language with medical "
        "terms introduced in context and briefly explained. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.CLINICAL: (
        "Physician-level. Standard medical terminology allowed. "
        "Be precise and concise. Still patient-facing in tone. "
        "The clinical interpretation structure stays the same."
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
        "1-2 sentences per section. Omit background and context."
    ),
    2: (
        "Be concise. Cover key points only with short explanations. "
        "2-3 sentences per section. Minimal background detail."
    ),
    3: (
        "Provide a standard level of detail. 3-5 sentences per section. "
        "Include enough context to understand each finding."
    ),
    4: (
        "Be thorough. Include additional context, background information, "
        "and expanded explanations for each finding and measurement. "
        "4-6 sentences per section."
    ),
    5: (
        "Be very comprehensive. Provide detailed explanations with full "
        "clinical context for every finding. Include background on what "
        "each measurement means and why it matters. 5-8 sentences per section."
    ),
}

# ---------------------------------------------------------------------------
# Clinical Voice Rule — shared across all output modes
# ---------------------------------------------------------------------------

_CLINICAL_VOICE_RULE = """\
## CLINICAL VOICE RULE — "DOCTOR INTERPRETATION MODE"

The explanation must sound like what a SPECIALIST in {specialty} would tell
a patient during a results discussion, NOT like a report recap or neutral
summary. Apply the clinical judgment, priorities, and interpretive lens of
a {specialty} specialist. Highlight what a specialist in this field would
consider most significant, and de-emphasize what they would consider
incidental or clinically unimportant.

Core Principle: Interpret, don't narrate.
- BAD (narrative): "The echocardiogram was performed and showed that the \
left ventricle was measured at 55%."
- GOOD (interpretive): "Your heart's pumping strength (LVEF 55%) falls \
within the normal range, which suggests your heart is pumping effectively."

For every finding, answer the patient's implicit question: \
"What does this mean for me?"

"""

_INTERPRETATION_STRUCTURE = """\
## Required Interpretation Structure

Organize the overall_summary into these sections IN ORDER, each as its own
paragraph separated by a blank line (\\n\\n). Use the section labels as
mental structure — do NOT print the labels as headers in the output.

1. BOTTOM LINE — 1-2 sentences stating what matters most and whether the
   findings are overall reassuring or concerning.

2. WHAT IS REASSURING — Normal or stable findings that reduce immediate
   concern. Start with LV size and function.

3. WHAT IS MOST IMPORTANT / ABNORMAL — The key medical issues that need
   attention, prioritized by clinical significance:
   a. Severe findings first, then moderate.
   b. Mild STENOSIS is clinically noteworthy — include with context.
   c. Mild REGURGITATION is very common and usually insignificant — mention
      only briefly in passing (e.g. "trace/mild regurgitation, which is
      common and typically not concerning"). Do NOT elevate it as an
      important finding.

4. HOW THIS RELATES TO YOUR SYMPTOMS — Tie findings directly to the
   patient's complaint or clinical context when provided. If no clinical
   context was given, omit this section.

5. WHEN TO CONTACT US SOONER — Brief safety guidance for symptom changes
   or urgent concerns. Keep to 1-2 sentences.

6. WHAT HAPPENS NEXT — Describe follow-up, additional testing, or
   monitoring using non-directive language (e.g. "your doctor may
   recommend…"). Incorporate any physician-selected next steps naturally.
   This section comes LAST.

"""

_TONE_RULES = """\
## Tone Rules
- Speak directly to the patient ("you," "your heart," "your doctor").
- Calm, confident, and clinically grounded.
- Reassuring when appropriate, but never dismissive.
- Never alarmist.
- Never speculative beyond the report.
- Use hedging language: "may," "appears to," "could suggest,"
  "seems to indicate."
- Avoid: "proves," "confirms," "definitely."

"""

_SAFETY_RULES = """\
## Safety & Scope Rules
1. ONLY use data that appears in the report provided. NEVER invent, guess,
   or assume measurements, findings, or diagnoses not explicitly stated.
2. For each measurement, the app has already classified it against reference
   ranges. You MUST use the status provided (normal, mildly_abnormal, etc.)
   — do NOT re-classify.
3. When explaining a measurement, state the patient's value, the normal
   range, and interpret what the status means clinically.
4. If a measurement has status "undetermined", say the value was noted but
   cannot be classified without more context.
5. Do NOT mention the patient by name or include any PHI.
6. Do NOT introduce diagnoses, treatments, or prognoses not supported by
   the source report.
7. Do NOT provide medication advice.
8. Use "may," "can," and "we will review" for next-step framing.
9. Call the explain_report tool with your response. Do not produce any
   output outside of this tool call.

"""

_CLINICAL_DOMAIN_KNOWLEDGE = """\
## Clinical Domain Knowledge

Apply these condition-specific interpretation rules:

- HYPERTROPHIC CARDIOMYOPATHY (HCM): A supra-normal or hyperdynamic ejection
  fraction (e.g. LVEF > 65-70%) is NOT reassuring in HCM. It may reflect
  hypercontractility from a thickened, stiff ventricle. Do NOT describe it as
  "strong" or "better than normal." Instead, note the EF value neutrally and
  explain that in the context of HCM, an elevated EF can be part of the
  disease pattern rather than a sign of good health.

"""

_CLINICAL_CONTEXT_RULE = """\
## Clinical Context Integration

When clinical context is provided (e.g. symptoms, reason for test):
- You MUST connect at least one finding to the clinical context.
- Tie findings directly to the clinical context by explaining how the
  results relate to the patient's symptoms or reason for testing.
- Use phrasing like "Given that this test was ordered for [reason]..."
  or "These findings help explain your [symptom]..."
- This applies to BOTH long-form and short comment outputs.
- If no clinical context was provided, skip this requirement.

"""


class PromptEngine:
    """Constructs system and user prompts for report explanation."""

    @staticmethod
    def _short_comment_sections(
        include_key_findings: bool, include_measurements: bool,
    ) -> str:
        n = 1
        lines: list[str] = []
        lines.append(
            f"{n}. Condensed clinical interpretation. Start with LV function, "
            f"then most significant findings by severity. Separate topics with "
            f"line breaks. 2-4 sentences. Mild regurgitation is NOT a key finding."
        )
        n += 1
        if include_key_findings:
            lines.append(
                f"{n}. KEY FINDINGS — Bullet list of clinically significant findings. "
                f"Severe/moderate first. Do NOT list mild regurgitation. 2-4 items."
            )
            n += 1
        if include_measurements:
            lines.append(
                f"{n}. MEASUREMENTS — Bullet list of key measurements with brief "
                f"interpretation. 2-4 items."
            )
            n += 1
        lines.append(
            f"{n}. NEXT STEPS — Only if the user prompt includes next steps. "
            f"List each as a bullet. If none provided, skip entirely."
        )
        return "\n".join(lines)

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
        include_key_findings: bool = True,
        include_measurements: bool = True,
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
                    f"10. Keep the entire overall_summary under {hard_limit} characters."
                )
            else:
                length_constraint = (
                    "- No strict character limit, but keep the comment concise and focused.\n"
                    "- Keep line width narrow (short lines, not long paragraphs).\n"
                )
                length_rule = (
                    "10. Keep the overall_summary concise but cover all relevant findings."
                )

            return (
                f"You are a {specialty} specialist explaining results to a patient.\n\n"
                f"{_CLINICAL_VOICE_RULE.format(specialty=specialty)}"
                f"{_CLINICAL_CONTEXT_RULE}"
                f"{_CLINICAL_DOMAIN_KNOWLEDGE}"
                f"## Short Comment Mode\n"
                f"Produce a condensed Results Comment using the same clinical "
                f"interpretation voice. The overall_summary should follow the "
                f"interpretation structure below but in abbreviated form.\n\n"
                f"## Output Constraints\n"
                f"{length_constraint}"
                f"- Plain text ONLY — no markdown, no emojis, no rich text.\n"
                f"- Avoid nested bullets or indentation.\n\n"
                f"## Formatting Rules\n"
                f"- Section headers: ALL CAPS on their own line. No bold, no symbols.\n"
                f"- One blank line between sections.\n"
                f"- Bullet items start with \"- \" (hyphen space).\n\n"
                f"## Required Sections (in this exact order)\n"
                f"{self._short_comment_sections(include_key_findings, include_measurements)}\n"
                f"## Literacy Level\n"
                f"{_LITERACY_DESCRIPTIONS[literacy_level]}\n\n"
                f"{physician_section}"
                f"{_TONE_RULES}"
                f"{_SAFETY_RULES}"
                f"{length_rule}"
            )

        literacy_desc = _LITERACY_DESCRIPTIONS[literacy_level]
        guidelines = prompt_context.get("guidelines", "standard clinical guidelines")
        explanation_style = prompt_context.get("explanation_style", "")
        tone = prompt_context.get("tone", "")

        tone_section = f"## Template Tone\n{tone}\n\n" if tone else ""

        tone_pref = _TONE_DESCRIPTIONS.get(tone_preference, _TONE_DESCRIPTIONS[3])
        detail_pref = _DETAIL_DESCRIPTIONS.get(detail_preference, _DETAIL_DESCRIPTIONS[3])

        style_section = (
            f"## Explanation Style\n{explanation_style}\n\n" if explanation_style else ""
        )

        return (
            f"You are a {specialty} specialist explaining results to a patient.\n\n"
            f"{_CLINICAL_VOICE_RULE.format(specialty=specialty)}"
            f"{_CLINICAL_CONTEXT_RULE}"
            f"{_CLINICAL_DOMAIN_KNOWLEDGE}"
            f"{_INTERPRETATION_STRUCTURE}"
            f"## Literacy Level\n{literacy_desc}\n\n"
            f"## Clinical Guidelines\n"
            f"Base your interpretations on: {guidelines}\n\n"
            f"{style_section}"
            f"{tone_section}"
            f"## Tone Preference\n{tone_pref}\n\n"
            f"## Detail Level\n{detail_pref}\n\n"
            f"{physician_section}"
            f"{_TONE_RULES}"
            f"{_SAFETY_RULES}"
            f"## Validation Rule\n"
            f"If the output reads like a neutral summary or report recap rather "
            f"than a clinical interpretation, regenerate.\n"
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
        teaching_points: list[dict] | None = None,
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
                "The physician has selected these next steps for the patient. Include them\n"
                "in the WHAT HAPPENS NEXT section at the end of the overall_summary:"
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

        # 1f. Teaching points (personalized instructions)
        if teaching_points:
            sections.append("\n## Teaching Points")
            sections.append(
                "The user has provided the following personalized instructions for how to\n"
                "interpret and explain results. Follow these guidelines:"
            )
            for tp in teaching_points:
                sections.append(f"- {tp['text']}")

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
            "Using ONLY the data above, generate a structured clinical "
            "interpretation by calling the explain_report tool. Include all "
            "measurements listed above. Do not add measurements or findings "
            "not present in the data."
        )

        return "\n".join(sections)
