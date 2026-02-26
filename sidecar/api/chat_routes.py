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
CHATBOT_MODEL = "claude-haiku-4-5-20251001"

_CHATBOT_SYSTEM_PROMPT = """\
You are a patient-friendly medical assistant helping a patient understand
their test results. You have access to the original report and explanation
below. Your job is to answer follow-up questions clearly and compassionately.

## Original Report Context
{report_context}

## Explanation That Was Provided
{explanation_summary}

## Test Type
{test_type_display}

## Rules
- ONLY answer questions about the report and explanation above.
- Use inclusive "we" language — "we can see from your results...", etc.
- Match the literacy level: {literacy_level}
- You CAN: explain findings in more detail, define medical terms, provide
  analogies, clarify what measurements mean, and restate things differently.
- You CANNOT: prescribe, diagnose new conditions, provide emergency advice,
  suggest specific treatments, or discuss conditions not in the report.
- If the patient asks about treatments or what to do next, redirect warmly:
  "That's a great question to bring up with your care team at your next
  visit. What I can help with is explaining what your results show."
- If the patient asks about something outside the report scope, say:
  "I can only help with questions about this specific report. For other
  concerns, please reach out to your care team."
- Keep responses concise (2-4 paragraphs max).
- Be warm, empathetic, and encouraging.
"""


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class CreateChatSessionRequest(BaseModel):
    history_id: int | str
    patient_label: Optional[str] = None
    expires_days: int = Field(default=DEFAULT_EXPIRY_DAYS, ge=1, le=90)


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

    # Scrub PHI from the report context
    scrubbed_report = _scrub_report_text(report_text) if report_text else ""

    # Generate token and create session
    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(days=body.expires_days)

    await pool.execute(
        """INSERT INTO chat_sessions
           (token, user_id, history_id, test_type, test_type_display,
            report_context, explanation_summary, patient_label,
            literacy_level, expires_at)
           VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10)""",
        token, user_id,
        history.get("id"),
        history.get("test_type", "unknown"),
        history.get("test_type_display", "Unknown Test"),
        scrubbed_report,
        explanation_summary,
        body.patient_label,
        "grade_8",
        expires_at,
    )

    return {
        "token": token,
        "url": f"/patient-chat/{token}",
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

    return {
        "token": session["token"],
        "test_type_display": session["test_type_display"],
        "explanation_summary": session["explanation_summary"],
        "patient_label": session.get("patient_label"),
        "messages": messages,
        "expires_at": session["expires_at"].isoformat(),
    }


@router.post("/sessions/{token}/messages")
async def send_chat_message(request: Request, token: str, body: SendMessageRequest):
    """Patient sends a message; chatbot responds (token auth)."""
    session = await _get_session_by_token(token)
    if not session:
        return JSONResponse({"detail": "Chat session not found"}, status_code=404)

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

    pool = await _get_pool()
    now = _now()

    # Store patient message
    await pool.execute(
        """INSERT INTO chat_messages (session_id, role, content, created_at)
           VALUES ($1, 'patient', $2, $3)""",
        session["id"], body.content, now,
    )

    # Build conversation history for LLM
    msg_rows = await pool.fetch(
        """SELECT role, content FROM chat_messages
           WHERE session_id = $1
           ORDER BY created_at ASC""",
        session["id"],
    )

    # Build Bedrock converse messages
    converse_messages = []
    for r in msg_rows:
        role = "user" if r["role"] == "patient" else "assistant"
        converse_messages.append({
            "role": role,
            "content": [{"text": r["content"]}],
        })

    # Call LLM
    system_prompt = _CHATBOT_SYSTEM_PROMPT.format(
        report_context=session["report_context"],
        explanation_summary=session["explanation_summary"],
        test_type_display=session["test_type_display"],
        literacy_level=session["literacy_level"],
    )

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
    except Exception:
        _logger.exception("Chat LLM call failed for session %s", session["id"])
        assistant_content = (
            "I'm sorry, I'm having trouble responding right now. "
            "Please try again in a moment, or contact your care team directly."
        )
        input_tokens = 0
        output_tokens = 0

    # Store assistant message
    assistant_time = _now()
    await pool.execute(
        """INSERT INTO chat_messages
           (session_id, role, content, created_at, input_tokens, output_tokens)
           VALUES ($1, 'assistant', $2, $3, $4, $5)""",
        session["id"], assistant_content, assistant_time, input_tokens, output_tokens,
    )

    # Update session counters
    await pool.execute(
        """UPDATE chat_sessions
           SET message_count = message_count + 2, last_message_at = $1
           WHERE id = $2""",
        assistant_time, session["id"],
    )

    return {
        "role": "assistant",
        "content": assistant_content,
        "created_at": assistant_time.isoformat(),
    }
