"""Patient follow-up chatbot routes.

Provides shareable chat sessions where patients can ask follow-up
questions about their report via an AI chatbot scoped to the original
explanation. No JWT required for patient endpoints — access is via
URL-safe token validated against the database.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from storage.pg_database import _get_pool

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_MESSAGES_PER_SESSION = 50
MAX_MESSAGE_LENGTH = 500
DEFAULT_EXPIRY_DAYS = 30
CHATBOT_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# System Prompt Builder
# ---------------------------------------------------------------------------

def _build_system_prompt(session: dict) -> str:
    """Build a safety-guardrailed system prompt from stored session data."""
    explanation_summary = session.get("explanation_summary", "")
    test_type_display = session.get("test_type_display", "")
    literacy_level = session.get("literacy_level", "grade_8")
    report_context = session.get("report_context", "")
    clinical_context = session.get("clinical_context") or ""
    severity_score = session.get("severity_score")

    # Parse stored JSON fields (may be dict or JSON string or None)
    full_explanation = session.get("full_explanation")
    if isinstance(full_explanation, str):
        try:
            full_explanation = json.loads(full_explanation)
        except (json.JSONDecodeError, TypeError):
            full_explanation = None

    teaching_points = session.get("teaching_points")
    if isinstance(teaching_points, str):
        try:
            teaching_points = json.loads(teaching_points)
        except (json.JSONDecodeError, TypeError):
            teaching_points = None

    glossary = session.get("glossary")
    if isinstance(glossary, str):
        try:
            glossary = json.loads(glossary)
        except (json.JSONDecodeError, TypeError):
            glossary = None

    # Determine tone from severity
    if severity_score is not None:
        if severity_score > 0.6:
            tone_level = "HIGH"
            tone_instruction = (
                "Use a calm but serious tone. Emphasize the importance of "
                "clinician follow-up. Never minimize findings."
            )
        elif severity_score >= 0.3:
            tone_level = "INTERMEDIATE"
            tone_instruction = (
                "Use a balanced tone. Explain significance clearly without alarm."
            )
        else:
            tone_level = "LOW"
            tone_instruction = (
                "Use a reassuring but factual tone. Emphasize the absence of "
                "major abnormalities where applicable."
            )
    else:
        tone_level = "INTERMEDIATE"
        tone_instruction = "Use a balanced, empathetic tone."

    # Check for severe/critical findings (over-reassurance guard)
    has_severe = False
    if full_explanation:
        for f in full_explanation.get("key_findings", []):
            if f.get("severity") in ("severe", "critical"):
                has_severe = True
                break

    # Build structured data sections
    sections = []

    sections.append(f"""## Physician's Approved Summary
{explanation_summary}""")

    # Key Findings
    if full_explanation and full_explanation.get("key_findings"):
        findings_lines = []
        for f in full_explanation["key_findings"]:
            sev = f.get("severity", "informational")
            findings_lines.append(
                f"- [{sev.upper()}] {f.get('finding', '')}: {f.get('explanation', '')}"
            )
        sections.append("## Key Findings\n" + "\n".join(findings_lines))

    # Measurements
    if full_explanation and full_explanation.get("measurements"):
        meas_lines = []
        for m in full_explanation["measurements"]:
            status = m.get("status", "")
            meas_lines.append(
                f"- {m.get('abbreviation', '')}: {m.get('value', '')} {m.get('unit', '')} "
                f"({status}) — {m.get('plain_language', '')}"
            )
        sections.append("## Measurements\n" + "\n".join(meas_lines))

    # Clinical Context
    if clinical_context:
        sections.append(f"## Clinical Context\n{clinical_context}")

    # Glossary
    if glossary:
        glossary_lines = [f"- **{term}**: {defn}" for term, defn in glossary.items()]
        sections.append("## Glossary\n" + "\n".join(glossary_lines))

    # Teaching Points
    if teaching_points:
        tp_lines = [f"- {tp.get('text', tp) if isinstance(tp, dict) else tp}" for tp in teaching_points]
        sections.append("## Teaching Points (Physician Instructions)\n" + "\n".join(tp_lines))

    # Questions for Care Team
    if full_explanation and full_explanation.get("questions_for_care_team"):
        q_lines = [f"- {q}" for q in full_explanation["questions_for_care_team"]]
        sections.append("## Questions for Care Team\n" + "\n".join(q_lines))

    # Discussion Topics
    if full_explanation and full_explanation.get("discussion_topics"):
        dt_lines = []
        for dt in full_explanation["discussion_topics"]:
            if isinstance(dt, dict):
                dt_lines.append(f"- {dt.get('topic', '')}: {dt.get('context', '')}")
            else:
                dt_lines.append(f"- {dt}")
        sections.append("## Discussion Topics\n" + "\n".join(dt_lines))

    # --- Conditional analogy enforcement ---
    test_type = session.get("test_type", "")
    _ECHO_TYPES = {"echo", "exercise_stress_echo", "pharma_stress_echo", "tee"}
    _PET_SPECT_TYPES = {
        "pharma_pet_stress", "exercise_pet_stress",
        "pharma_spect_stress", "exercise_spect_stress",
    }
    _CALCIUM_TYPES = {"cta_coronary", "ct_calcium_score"}

    analogy_section = ""
    if test_type in _ECHO_TYPES:
        analogy_section = """
## Required Analogies
You MUST use these analogies when explaining the corresponding findings. Always include the relevant analogy — do not skip it.

**Diastolic function (balloon-to-football):**
- Normal: "Between each heartbeat, your heart relaxes and fills with blood easily — like inflating a soft, flexible balloon that expands without much effort."
- Grade I (impaired relaxation): "Your heart muscle is a little stiffer when it relaxes between beats — like a balloon that's a bit thicker and takes a little more effort to inflate. It still fills well, but not quite as easily. This is the mildest form and is very common with age."
- Grade II (pseudonormal): "Your heart muscle has become noticeably stiffer — less like a soft balloon and more like trying to inflate a football. It takes more pressure to fill, and even though the filling pattern may look normal on the surface, the pressures inside are higher than they should be."
- Grade III (restrictive): "Your heart muscle is quite stiff — like trying to inflate a football that's already firm. It takes a lot of pressure to fill, and the heart has significant difficulty relaxing between beats."

**Valve regurgitation (door analogy):**
- Trace/mild: "Think of a door that doesn't quite close all the way — a tiny bit of blood leaks back through. This is so common it's considered normal."
- Moderate: "The door has a noticeable gap — more blood leaks backward than it should, making the heart work a bit harder."
- Severe: "The door is significantly open — a large amount of blood flows back the wrong way, putting extra strain on the heart."

**Valve stenosis (door opening):**
- Mild: "The valve opening is slightly narrower than normal — like a door that doesn't open all the way but you can still walk through comfortably."
- Moderate: "The valve opening is noticeably narrowed — like having to turn sideways to fit through a partially open door."
- Severe: "The valve opening is very tight — like trying to squeeze through a barely open door. The heart has to push much harder to get blood through."

**Ejection fraction (water pump):**
- Normal (>=55%): "Your heart pumps out more than half of its blood with each beat — like a strong water pump working at full efficiency."
- Mildly reduced (41-54%): "Your heart's pumping power is slightly below the ideal range — like a pump that's lost a little efficiency but still moves plenty of water."
- Moderately reduced (30-40%): "Your heart's pumping strength is noticeably reduced — like a pump running at half power."
- Severely reduced (<30%): "Your heart's pumping power is significantly weakened — like a pump that can only push out a small fraction of its capacity."

**Chamber size (balloon inflation):**
- Normal: "Your heart chambers are a normal size — like a balloon inflated to the right amount."
- Mildly dilated: "This chamber is slightly larger than normal — like a balloon that's been stretched just a bit beyond its usual size."
- Severely dilated: "This chamber is significantly enlarged — like a balloon stretched well beyond its normal size, which means the walls may not squeeze as effectively."
"""
    elif test_type in _PET_SPECT_TYPES:
        analogy_section = """
## Required Analogies
You MUST use these analogies when explaining the corresponding findings. Always include the relevant analogy — do not skip it.

**Coronary Flow Capacity — freeway analogy:**
- Normal CFC: "Think of your coronary arteries like a freeway with no traffic — blood flows freely even during rush hour (stress)."
- Mildly reduced CFC: "Like a freeway with some congestion during rush hour — traffic still moves but a bit slower than ideal."
- Moderately reduced CFC: "Like a freeway with significant traffic backup — blood flow is noticeably restricted when your heart needs it most."
- Severely reduced CFC: "Like a freeway with a major bottleneck — blood flow is significantly restricted during stress."

**Stress MBF — water pipe analogy:**
- Normal stress MBF (>= 2.0): "Your heart's blood vessels can deliver plenty of blood when demand increases — like a water pipe with strong pressure."
- Mildly reduced (1.5-2.0): "The pipe still delivers water but the pressure drops a little when multiple faucets are running."
- Moderately reduced (1.0-1.5): "The pipe delivers noticeably less water under high demand — like low water pressure when everyone's showering."
- Severely reduced (< 1.0): "The pipe can barely keep up with demand — very limited flow even when the heart needs it most."

**MFR/CFR — flow reserve:**
- Normal (>= 2.0): "Your heart can at least double its blood flow when needed — like having plenty of reserve fuel in the tank."
- Mildly reduced (1.5-2.0): "Your heart can increase blood flow but not quite as much as expected — the reserve tank is a little lower than ideal."
- Moderately reduced (1.0-1.5): "Your heart has limited ability to increase blood flow under stress."
- Severely reduced (< 1.0): "Your heart can barely increase blood flow at all when it needs to — the reserve is very limited."
"""

    if analogy_section:
        sections.append(analogy_section.strip())

    structured_data = "\n\n".join(sections)

    over_reassurance_rule = ""
    if has_severe:
        over_reassurance_rule = (
            "\n- OVER-REASSURANCE GUARD: This report contains severe/critical findings. "
            "NEVER minimize with phrases like 'not dangerous', 'nothing to worry about', "
            "'you'll be fine', or 'don't worry'. Maintain appropriate seriousness."
        )

    # Physician name personalization
    physician_name = session.get("physician_name") or ""
    if physician_name:
        doctor_ref = physician_name
        doctor_instruction = (
            f"\n## Physician Name\n"
            f"The patient's doctor is **{physician_name}**. When referring to their "
            f"doctor, use \"{physician_name}\" instead of generic phrases like "
            f"\"your doctor\", \"your physician\", or \"your care team\". "
            f"For example: \"You should discuss this with {physician_name}\" or "
            f"\"{physician_name} can explain this further at your next visit.\""
        )
    else:
        doctor_ref = "your doctor"
        doctor_instruction = ""

    # Calcium Score & Plaque Education (conditional)
    calcium_education_section = ""
    if test_type in _CALCIUM_TYPES:
        calcium_education_section = f"""
## Calcium Score & Plaque Education
When discussing coronary calcium scores or plaque findings:
- You may explain what a calcium score measures (presence of calcified plaque
  in coronary arteries)
- You may explain that calcium scoring is one of several tools used to assess
  coronary artery disease risk
- Do NOT state specific score thresholds (e.g., "above 400 is severe") unless
  the physician's analysis explicitly labels the score category
- Do NOT compare the patient's score to population percentiles unless provided
  in the data
- Do NOT suggest the score predicts specific outcomes (heart attack risk, need
  for stenting, etc.)
- Do NOT re-interpret plaque burden beyond what the report states
- For questions about treatment based on calcium score, redirect: "Calcium
  score results are one piece of {doctor_ref}'s overall assessment. Treatment
  decisions are based on your complete risk profile."
- Explain that both calcified and non-calcified plaque exist, but do not
  speculate about non-calcified plaque unless the report discusses it
"""

    prompt = f"""\
You are an educational companion helping a patient understand their
{test_type_display} results. You are NOT a medical provider and this chat
is NOT monitored by clinical staff. This is not medical care and is not a
substitute for talking with {doctor_ref}. Your responses are grounded
EXCLUSIVELY in the physician-approved analysis data below.

## Test Type
{test_type_display}

## Literacy Level
{literacy_level}
{doctor_instruction}

{structured_data}

## Original Report Context
{report_context}

# SAFETY RULES — YOU MUST FOLLOW ALL OF THESE

## 1. Source of Truth (Hard Rule)
You may ONLY use information from:
- The Physician's Approved Summary above
- The Key Findings, Measurements, Glossary, Clinical Context, and Teaching Points above
- The Original Report Context above

You may NOT:
- Infer new diagnoses beyond what is stated
- Re-grade severity of any finding
- Recommend treatments or medications
- Provide prognosis or survival statistics
- Introduce findings not present in the analysis data

## 2. Primary Conclusion Lock
The first sentence of every response must reflect the physician's overall
impression from the Approved Summary. All explanations must be anchored to
that conclusion. Never reinterpret or contradict it.

## 3. No Triage Questioning (Emergency Redirect)
If the patient reports new or worsening symptoms (chest pain, shortness of
breath, fainting, stroke-like symptoms, sudden weakness, palpitations, etc.):
"This chat cannot evaluate urgent or new symptoms. If you are experiencing
active or worsening symptoms, please contact your healthcare provider
immediately or seek emergency medical care."
Stop further interpretation after this redirect.

Critical:
- Do NOT ask clarifying questions about symptoms (e.g., "Where is the pain?",
  "How long has this been going on?", "On a scale of 1-10…")
- Do NOT reassure the patient about symptoms (e.g., "That's probably nothing
  to worry about")
- Do NOT attempt to triage, risk-stratify, or assess urgency of symptoms
- Any mention of active symptoms → immediate redirect, no follow-up questions

## 4. No Diagnosis or Causal Attribution
- You may explain what a finding generally means in medical education
- You may NOT tell the patient what caused their condition or findings
- You may NOT link findings to specific causes in the patient's case
- Correct: "Aortic stenosis can be associated with aging, bicuspid valve, or
  other factors"
- Incorrect: "Your aortic stenosis is caused by years of high blood pressure"
- Incorrect: "This is happening because of your diabetes"
- When discussing relationships, use educational framing: "In general, [X] can
  be associated with [Y]" — never "In your case, [X] caused [Y]"

## 5. No Personalized Recommendations
For treatment, medication, or surgery questions, respond with:
"Treatment decisions are made by {doctor_ref} based on your complete medical
history. I can explain what the report says, but I can't recommend specific
next steps."

Additional boundaries:
- Do NOT advise the patient to stop, start, adjust, or change any medication
- Do NOT provide exercise clearance or activity restrictions
- For "Should I…?" questions, do NOT answer yes or no. Provide general
  education about the topic, then redirect: "Whether that applies to your
  situation is something {doctor_ref} can help you with."
- For medication-change questions: "Medication decisions involve weighing
  benefits, risks, and your individual health profile — that's a conversation
  for {doctor_ref}."

After two repeated attempts on the same topic, repeat the boundary and stop
escalating detail.

## 6. Prognosis & Research Boundary
For survival, life expectancy, statistical risk, time estimates, or event
probability questions, respond with:
"Research findings vary, and individual risk depends on many factors.
{doctor_ref} can discuss personalized risk in more detail."

Never provide percentages, survival statistics, time estimates for disease
progression, or probabilities of cardiac events.

## 7. Numeric Containment
When severity labels are provided in Key Findings or Measurements:
- Use numbers only to explain what the label means
- Do NOT independently interpret numeric thresholds
- Do NOT declare numbers normal/abnormal unless the analysis explicitly labeled them
- Do NOT cite specific guideline cutoff numbers (e.g., "LDL should be below 70",
  "EF below 40% means heart failure")
- Do NOT re-interpret percent stenosis values beyond what the report states
- When asked about targets or thresholds: "Different professional guidelines
  use risk-based thresholds that depend on your individual profile.
  {doctor_ref} can tell you what targets apply to you."
- Correct: "The report labels this as moderate aortic stenosis."
- Incorrect: "A gradient of 42 usually requires surgery."
- Incorrect: "Your LDL of 130 is above the recommended target of 70."

## 8. Medication Education — Guarded Mode
- You may provide general educational information about classes of medications
  (e.g., "Statins are a class of medication that can help lower cholesterol")
- Do NOT name specific drugs unless they are already mentioned in the
  physician-provided data above
- Do NOT provide dosing information, titration schedules, or drug interactions
- Do NOT suggest starting, stopping, or adjusting any medication
- Always frame medication discussion as shared decision-making: "Medication
  choices are a shared decision between you and {doctor_ref}, based on your
  individual risk factors and preferences."
{calcium_education_section}## 9. Response Taxonomy (Internal Routing)
Before composing each response, internally classify the patient's question:
- FACTUAL: "What does [term] mean?" → Explain using analysis data only
- COMPARATIVE: "Is this normal?" → Use severity labels from data, no independent interpretation
- ACTIONABLE: "Should I [do X]?" → General education + redirect to {doctor_ref}
- EMOTIONAL: "Am I going to be okay?" → Acknowledge emotion + anchor to physician's conclusion + redirect
- OUT_OF_SCOPE: Not about this report → Scope boundary redirect
Apply the corresponding guardrails for each category.

## 10. Binary Block
If the patient asks a yes/no question about their health, diagnosis, or
treatment (e.g., "Is this dangerous?", "Do I need surgery?", "Am I at risk?"):
- Do NOT answer with "yes" or "no"
- Instead: provide general education about the topic, anchor to what the report
  says, and redirect: "Whether this is a concern in your specific case is
  something {doctor_ref} can address."

## 11. Tone Calibration — {tone_level}
{tone_instruction}

Emotional intelligence:
- You may acknowledge emotion: "It's understandable to feel concerned when
  reading medical results."
- Never say: "You'll be fine", "Don't worry", or "There's nothing to worry about"
{over_reassurance_rule}
Preferred phrasing:
- Use "This indicates…" or "This suggests…" when explaining findings
- Use "The report shows…" to anchor to physician data
- Avoid "I think…" or "In my opinion…" — you are not providing clinical judgment

## 12. Progressive Disclosure
- Default: Give a SHORT, concise answer to the question (2-3 paragraphs max)
- If the patient requests more detail: Give an EXPANDED explanation using key findings
- If the patient asks further: Give a DEEP DIVE using measurement-by-measurement
  explanation with only values present in the analysis. Never introduce new metrics.

## 13. Teaching Points
Teaching points from the physician are authoritative instructions for how to
explain specific findings. Follow them closely — they represent the physician's
clinical judgment about what to emphasize, de-emphasize, or explain differently.

## 14. Response Focus
Do NOT restate or summarize all the findings before answering. Focus directly on
answering the patient's specific question. Only reference findings that are directly
relevant to what was asked. If the patient asks about a single measurement, explain
that measurement — do not recite the entire report. Provide context and meaning
rather than simply repeating what the report already says.

## 15. Scope Reminder (Drift Control)
If the conversation extends beyond approximately 4-5 assistant responses, append
the following reminder to your next response:
"Just a reminder — I can only help explain what's in this specific report.
For any questions about your treatment plan or next steps, {doctor_ref} is
the best person to ask."
Continue answering normally but include this reminder periodically in longer
conversations.

## 16. Complexity Ceiling
If the patient pushes for academic-level physiological detail, complex
pathophysiology mechanisms, or argues with the explanation provided:
"That's a great question that goes beyond what I can cover here.
{doctor_ref} can walk you through the details at your next visit."
Do not engage in extended academic-level physiology debates.

## 17. Internal Medicine Overlap
For questions about how cardiac findings relate to other conditions (CKD,
diabetes, hypertension, thyroid disease, etc.):
- You may explain general relationships in educational terms (e.g., "High
  blood pressure over time can affect the heart's structure")
- Do NOT attribute the patient's cardiac findings to a specific comorbidity
- Do NOT suggest lab-based medication adjustments (e.g., "Your A1c means
  you should adjust your insulin")
- Redirect specifics: "How these conditions interact in your case is something
  {doctor_ref} can explain."

## 18. Analytics / No Storage Framing
- Do NOT reference storing, saving, or monitoring the patient's data
- Do NOT suggest this chat integrates with their medical chart or EHR
- Do NOT imply continuous monitoring or tracking of their condition
- This is a one-time educational tool, not an ongoing clinical relationship

## 19. Patient Identity Lock
These test results belong to THE PATIENT directly. The person reading this
chat IS the patient. Never frame results as belonging to a family member,
child, parent, or other third party.
- ALWAYS address the patient as "you" / "your"
- NEVER write "your son's results", "your daughter's echo",
  "your child's test", "your mother's report", or similar
- Even if the report text or clinical context mentions family relationships,
  pediatric context, or guardian information, the explanation is addressed
  to the patient about THEIR OWN results
- Correct: "Your echocardiogram shows..."
- Incorrect: "Your son's echocardiogram shows..."

## 20. Formatting
Use **bold** for key terms, finding names, and measurement labels to improve
readability. Use relevant emoji/symbols (e.g. ✅ ⚠️ ❤️ 💪 📋) to make
responses more scannable and patient-friendly. Keep formatting clean — no
markdown headings (# ## ###), no horizontal rules (---).

Mobile-friendly formatting:
- Use short paragraphs (2-3 sentences max per paragraph)
- Use bullet points for lists of related items
- Avoid dense walls of text

## 21. Scope Boundary
If the patient asks about something outside this report, say:
"I can only help with questions about this specific report. For other
concerns, please reach out to {doctor_ref}."
"""
    return prompt


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class CreateChatSessionRequest(BaseModel):
    history_id: int | str
    patient_label: Optional[str] = None
    expires_days: int = Field(default=DEFAULT_EXPIRY_DAYS, ge=1, le=90)
    clinical_context: Optional[str] = None
    # Optional overrides: when provided, these take precedence over what's
    # stored in the history table, ensuring the chat reflects the physician's
    # latest edits, regenerations, and slider adjustments.
    current_full_response: Optional[dict] = None
    edited_summary: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., max_length=MAX_MESSAGE_LENGTH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_session_by_token(token: str) -> dict | None:
    """Load a chat session by its URL token, or None if not found."""
    pool = await _get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM chat_sessions WHERE token = $1", token,
    )
    if not row:
        return None
    return dict(row)


async def _get_bedrock_client():
    """Build a Bedrock client using IAM role credentials for chat."""
    from llm.client import LLMClient, LLMProvider

    return LLMClient(
        provider=LLMProvider.BEDROCK,
        api_key={"access_key": "iam_role", "region": "us-east-1"},
        model=CHATBOT_MODEL,
    )


def _scrub_report_text(text: str) -> str:
    """Remove PHI from report text before storing in chat session."""
    from phi.scrubber import scrub_phi
    result = scrub_phi(text)
    return result.scrubbed_text


async def _load_teaching_points(test_type: str, user_id: str) -> list[dict]:
    """Load teaching points for a test type + user (own + practice shared)."""
    try:
        from storage.pg_database import PgDatabase
        db = PgDatabase()
        return await db.list_all_teaching_points_for_prompt(
            test_type=test_type, user_id=user_id,
        )
    except Exception:
        _logger.exception("Failed to load teaching points for chat session")
        return []


def _load_glossary(test_type: str) -> dict[str, str]:
    """Load glossary for a test type from the handler registry."""
    try:
        from test_types import registry
        _resolved_id, handler = registry.resolve(test_type)
        if handler:
            return handler.get_glossary()
    except Exception:
        _logger.exception("Failed to load glossary for test type %s", test_type)
    return {}


def _validate_session_active(session: dict) -> JSONResponse | None:
    """Return an error response if session is expired or at message limit, else None."""
    if session["expires_at"] < _now():
        return JSONResponse(
            {"detail": "This chat link has expired."},
            status_code=410,
        )
    if session["message_count"] >= MAX_MESSAGES_PER_SESSION:
        return JSONResponse(
            {"detail": "This chat session has reached its message limit. Please contact your care team for further questions."},
            status_code=429,
        )
    return None


async def _store_assistant_message(session: dict, content: str, input_tokens: int = 0, output_tokens: int = 0) -> dict:
    """Store an assistant message and update session counters. Returns message dict."""
    pool = await _get_pool()
    assistant_time = _now()
    await pool.execute(
        """INSERT INTO chat_messages
           (session_id, role, content, created_at, input_tokens, output_tokens)
           VALUES ($1, 'assistant', $2, $3, $4, $5)""",
        session["id"], content, assistant_time, input_tokens, output_tokens,
    )
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 1, last_message_at = $1
           WHERE id = $2""",
        assistant_time, session["id"],
    )
    return {
        "role": "assistant",
        "content": content,
        "created_at": assistant_time.isoformat(),
    }


# ---------------------------------------------------------------------------
# Authenticated Endpoints (nurse/physician)
# ---------------------------------------------------------------------------

@router.post("/create")
async def create_chat_session(request: Request, body: CreateChatSessionRequest):
    """Create a new chat session for a patient (authenticated)."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    pool = await _get_pool()

    # Load the history entry
    row = await pool.fetchrow(
        "SELECT * FROM history WHERE (sync_id = $1 OR id = $2) AND user_id = $3",
        str(body.history_id), int(body.history_id) if str(body.history_id).isdigit() else -1, user_id,
    )
    if not row:
        return JSONResponse({"detail": "History entry not found"}, status_code=404)

    history = dict(row)

    # Use the frontend-provided current_full_response if available (reflects
    # regenerations, slider changes, long comment, etc.), otherwise fall back
    # to the history DB row which may be stale.
    full_response = body.current_full_response
    if full_response is None:
        full_response = history.get("full_response")
        if isinstance(full_response, str):
            full_response = json.loads(full_response)

    # Extract report text and explanation summary
    report_text = ""
    if full_response:
        parsed = full_response.get("parsed_report", {})
        for section in parsed.get("sections", []):
            report_text += section.get("content", "") + "\n"
        if not report_text.strip():
            report_text = history.get("summary", "")

    explanation = full_response.get("explanation", {}) if full_response else {}
    explanation_summary = explanation.get("overall_summary", history.get("summary", ""))

    # If the physician edited the summary text, use that instead
    if body.edited_summary:
        explanation_summary = body.edited_summary

    # Scrub PHI from the report context
    scrubbed_report = _scrub_report_text(report_text) if report_text else ""

    # Extract enrichment data from full_response
    full_explanation_json = json.dumps(explanation) if explanation else None
    parsed_measurements = full_response.get("parsed_report", {}).get("measurements") if full_response else None
    parsed_measurements_json = json.dumps(parsed_measurements) if parsed_measurements else None
    severity_score = history.get("severity_score")

    # Use the practice-validated physician name from the explain response.
    # The explain route already resolves this against practice_providers,
    # so only practice physicians will appear here — never outside referring
    # doctors.  No fallback extraction: if the explain response has no name,
    # the chat will use generic phrasing ("your doctor").
    physician_name = None
    if full_response:
        physician_name = full_response.get("physician_name")

    # Clinical context from request (already PHI-scrubbed by the physician)
    clinical_context = body.clinical_context

    # Load teaching points and glossary
    test_type = history.get("test_type", "unknown")
    teaching_points = await _load_teaching_points(test_type, user_id)
    teaching_points_json = json.dumps(teaching_points) if teaching_points else None

    glossary = _load_glossary(test_type)
    glossary_json = json.dumps(glossary) if glossary else None

    # Generate short token (8 bytes → 11 URL-safe chars) and create session
    token = secrets.token_urlsafe(8)
    expires_at = _now() + timedelta(days=body.expires_days)

    await pool.execute(
        """INSERT INTO chat_sessions
           (token, user_id, history_id, test_type, test_type_display,
            report_context, explanation_summary, patient_label,
            literacy_level, expires_at,
            full_explanation, parsed_measurements, teaching_points,
            glossary, clinical_context, severity_score, physician_name)
           VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10,
                   $11::jsonb, $12::jsonb, $13::jsonb, $14::jsonb, $15, $16, $17)""",
        token, user_id,
        history.get("id"),
        test_type,
        history.get("test_type_display", "Unknown Test"),
        scrubbed_report,
        explanation_summary,
        body.patient_label,
        "grade_8",
        expires_at,
        full_explanation_json,
        parsed_measurements_json,
        teaching_points_json,
        glossary_json,
        clinical_context,
        severity_score,
        physician_name,
    )

    return {
        "token": token,
        "url": f"/c/{token}",
        "expires_at": expires_at.isoformat(),
    }


@router.get("/list")
async def list_chat_sessions(request: Request):
    """List all chat sessions created by the authenticated user."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    pool = await _get_pool()
    rows = await pool.fetch(
        """SELECT id, token, test_type_display, patient_label,
                  message_count, last_message_at, expires_at, created_at
           FROM chat_sessions
           WHERE user_id = $1::uuid
           ORDER BY created_at DESC""",
        user_id,
    )

    sessions = []
    for row in rows:
        r = dict(row)
        sessions.append({
            "id": str(r["id"]),
            "token": r["token"],
            "test_type_display": r["test_type_display"],
            "patient_label": r["patient_label"],
            "message_count": r["message_count"],
            "last_message_at": r["last_message_at"].isoformat() if r["last_message_at"] else None,
            "expires_at": r["expires_at"].isoformat(),
            "created_at": r["created_at"].isoformat(),
            "is_expired": r["expires_at"] < _now(),
        })

    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(request: Request, session_id: str):
    """Delete a chat session (authenticated — nurse revokes access)."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    pool = await _get_pool()
    result = await pool.execute(
        "DELETE FROM chat_sessions WHERE id = $1::uuid AND user_id = $2::uuid",
        session_id, user_id,
    )

    if result == "DELETE 0":
        return JSONResponse({"detail": "Session not found"}, status_code=404)

    return {"deleted": True}


# ---------------------------------------------------------------------------
# Token-based Endpoints (patient — no auth required)
# ---------------------------------------------------------------------------

@router.get("/sessions/{token}")
async def get_chat_session(request: Request, token: str):
    """Load a chat session by token (patient access, no auth)."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

    if session["expires_at"] < _now():
        return JSONResponse(
            {"detail": "This chat link has expired. Please contact your care team for a new link."},
            status_code=410,
        )

    # Load messages
    pool = await _get_pool()
    msg_rows = await pool.fetch(
        """SELECT role, content, created_at
           FROM chat_messages
           WHERE session_id = $1
           ORDER BY created_at ASC""",
        session["id"],
    )

    messages = [
        {
            "role": dict(r)["role"],
            "content": dict(r)["content"],
            "created_at": dict(r)["created_at"].isoformat(),
        }
        for r in msg_rows
    ]

    # Parse full_explanation for frontend
    full_explanation = session.get("full_explanation")
    if isinstance(full_explanation, str):
        try:
            full_explanation = json.loads(full_explanation)
        except (json.JSONDecodeError, TypeError):
            full_explanation = None

    return {
        "token": session["token"],
        "test_type": session.get("test_type"),
        "test_type_display": session["test_type_display"],
        "explanation_summary": session["explanation_summary"],
        "patient_label": session.get("patient_label"),
        "full_explanation": full_explanation,
        "messages": messages,
        "expires_at": session["expires_at"].isoformat(),
    }


@router.post("/sessions/{token}/messages")
async def send_chat_message(request: Request, token: str, body: SendMessageRequest):
    """Patient sends a message; chatbot responds (token auth)."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

    error_resp = _validate_session_active(session)
    if error_resp:
        return error_resp

    pool = await _get_pool()
    now = _now()

    # Store patient message
    await pool.execute(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES ($1, 'patient', $2, $3)""",
        session["id"], body.content, now,
    )

    # Update message count for patient message
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 1, last_message_at = $1
           WHERE id = $2""",
        now, session["id"],
    )

    # Build system prompt with full analysis context
    system_prompt = _build_system_prompt(session)

    try:
        client = await _get_bedrock_client()
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=body.content,
            max_tokens=1024,
            temperature=0.3,
        )
        assistant_content = response.raw_content
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens
    except Exception as exc:
        _logger.exception("Chat LLM call failed for session %s: %s", session["id"], exc)
        assistant_content = (
            "I'm sorry, I'm having trouble responding right now. "
            "Please try again in a moment, or contact your care team directly."
        )
        input_tokens = 0
        output_tokens = 0

    return await _store_assistant_message(session, assistant_content, input_tokens, output_tokens)


@router.post("/sessions/{token}/simplify")
async def simplify_explanation(request: Request, token: str):
    """Generate a simplified (grade 4) explanation from stored analysis data."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

    error_resp = _validate_session_active(session)
    if error_resp:
        return error_resp

    # Store a synthetic patient message so conversation history stays valid
    pool = await _get_pool()
    now = _now()
    patient_text = "Can you simplify the explanation for me?"
    await pool.execute(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES ($1, 'patient', $2, $3)""",
        session["id"], patient_text, now,
    )
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 1, last_message_at = $1
           WHERE id = $2""",
        now, session["id"],
    )

    # Build context from stored data
    system_prompt = _build_system_prompt(session)

    user_prompt = (
        "Please rewrite the explanation of my results in very simple language "
        "that a 9-year-old could understand (grade 4 reading level). "
        "Use short sentences, simple words, and helpful comparisons. "
        "Keep the same main conclusion from the physician's summary as your "
        "first sentence. Explain what each finding means in everyday terms. "
        "If something is normal, say so simply. If something needs attention, "
        "explain it gently but honestly."
    )

    try:
        client = await _get_bedrock_client()
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1500,
            temperature=0.3,
        )
        content = response.raw_content
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens
    except Exception as exc:
        _logger.exception("Simplify LLM call failed for session %s: %s", session["id"], exc)
        return JSONResponse(
            {"detail": "Failed to generate simplified explanation. Please try again."},
            status_code=500,
        )

    return await _store_assistant_message(session, content, input_tokens, output_tokens)


@router.post("/sessions/{token}/detail")
async def detail_explanation(request: Request, token: str):
    """Generate a comprehensive detailed explanation from stored analysis data."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

    error_resp = _validate_session_active(session)
    if error_resp:
        return error_resp

    # Store a synthetic patient message so conversation history stays valid
    pool = await _get_pool()
    now = _now()
    patient_text = "Can you give me a more detailed explanation of all my results?"
    await pool.execute(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES ($1, 'patient', $2, $3)""",
        session["id"], patient_text, now,
    )
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 1, last_message_at = $1
           WHERE id = $2""",
        now, session["id"],
    )

    system_prompt = _build_system_prompt(session)

    user_prompt = (
        "Please give me a very comprehensive, detailed explanation of all my results. "
        "Be very comprehensive. Provide detailed explanations with full clinical context "
        "for every finding. Include background on what each finding means and why it "
        "matters. Use 5-8 sentences per section.\n\n"
        "Include:\n"
        "1. A headline reflecting the physician's overall conclusion\n"
        "2. Each key finding explained at a patient-friendly level with full severity "
        "context, background on what each finding means, and why it matters\n"
        "3. Topics that may come up at my next visit\n\n"
        "Do NOT include a measurements breakdown or a list of questions to ask — "
        "those are available separately. Focus on explaining the key findings in depth.\n\n"
        "Be thorough but still use clear, accessible language. Follow the physician's "
        "teaching points for how to explain specific findings."
    )

    try:
        client = await _get_bedrock_client()
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=3000,
            temperature=0.3,
        )
        content = response.raw_content
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens
    except Exception as exc:
        _logger.exception("Detail LLM call failed for session %s: %s", session["id"], exc)
        return JSONResponse(
            {"detail": "Failed to generate detailed explanation. Please try again."},
            status_code=500,
        )

    return await _store_assistant_message(session, content, input_tokens, output_tokens)


@router.post("/sessions/{token}/key-findings")
async def key_findings_explanation(request: Request, token: str):
    """Generate a focused explanation of the patient's key findings."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

    error_resp = _validate_session_active(session)
    if error_resp:
        return error_resp

    # Store a synthetic patient message
    pool = await _get_pool()
    now = _now()
    patient_text = "Can you explain my key findings?"
    await pool.execute(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES ($1, 'patient', $2, $3)""",
        session["id"], patient_text, now,
    )
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 1, last_message_at = $1
           WHERE id = $2""",
        now, session["id"],
    )

    system_prompt = _build_system_prompt(session)

    user_prompt = (
        "Please explain each of my key findings in patient-friendly language. "
        "For each finding, explain what it means, its severity, and why it matters. "
        "Focus only on the key findings listed in the data above."
    )

    try:
        client = await _get_bedrock_client()
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2000,
            temperature=0.3,
        )
        content = response.raw_content
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens
    except Exception as exc:
        _logger.exception("Key findings LLM call failed for session %s: %s", session["id"], exc)
        return JSONResponse(
            {"detail": "Failed to generate key findings explanation. Please try again."},
            status_code=500,
        )

    return await _store_assistant_message(session, content, input_tokens, output_tokens)


@router.post("/sessions/{token}/measurements")
async def measurements_explanation(request: Request, token: str):
    """Generate a focused explanation of the patient's measurements."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

    error_resp = _validate_session_active(session)
    if error_resp:
        return error_resp

    # Store a synthetic patient message
    pool = await _get_pool()
    now = _now()
    patient_text = "Can you walk me through my measurements?"
    await pool.execute(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES ($1, 'patient', $2, $3)""",
        session["id"], patient_text, now,
    )
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 1, last_message_at = $1
           WHERE id = $2""",
        now, session["id"],
    )

    system_prompt = _build_system_prompt(session)

    user_prompt = (
        "Please explain each of my measurements in patient-friendly language. "
        "For each measurement, tell me what was measured, what the value means, "
        "and whether it's normal or abnormal based on the analysis labels. "
        "Use the physician-provided severity labels — do not independently "
        "interpret numeric thresholds."
    )

    try:
        client = await _get_bedrock_client()
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2500,
            temperature=0.3,
        )
        content = response.raw_content
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens
    except Exception as exc:
        _logger.exception("Measurements LLM call failed for session %s: %s", session["id"], exc)
        return JSONResponse(
            {"detail": "Failed to generate measurements explanation. Please try again."},
            status_code=500,
        )

    return await _store_assistant_message(session, content, input_tokens, output_tokens)


@router.post("/sessions/{token}/questions")
async def questions_to_ask(request: Request, token: str):
    """Generate a list of questions the patient should ask their doctor."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

    error_resp = _validate_session_active(session)
    if error_resp:
        return error_resp

    # Store a synthetic patient message
    pool = await _get_pool()
    now = _now()
    patient_text = "What questions should I ask my doctor?"
    await pool.execute(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES ($1, 'patient', $2, $3)""",
        session["id"], patient_text, now,
    )
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 1, last_message_at = $1
           WHERE id = $2""",
        now, session["id"],
    )

    system_prompt = _build_system_prompt(session)

    user_prompt = (
        "Based on my specific results, what questions should I ask my doctor "
        "at my next visit? For each question, briefly explain WHY it's worth "
        "asking — what context from my results makes it relevant. Use the "
        "Questions for Care Team and Discussion Topics from the data above as "
        "your primary source, but frame them as natural patient questions. "
        "Do not simply list the questions — provide context for why each one "
        "matters given MY specific findings."
    )

    try:
        client = await _get_bedrock_client()
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2000,
            temperature=0.3,
        )
        content = response.raw_content
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens
    except Exception as exc:
        _logger.exception("Questions LLM call failed for session %s: %s", session["id"], exc)
        return JSONResponse(
            {"detail": "Failed to generate questions list. Please try again."},
            status_code=500,
        )

    return await _store_assistant_message(session, content, input_tokens, output_tokens)
