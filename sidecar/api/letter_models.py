"""Pydantic models for the /letters endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LetterGenerateRequest(BaseModel):
    """Request body for POST /letters/generate."""

    prompt: str = Field(..., min_length=1, max_length=5000)
    letter_type: str = Field(
        default="general",
        description="Type of content: 'explanation', 'question', 'letter', or 'general'.",
    )


class LetterResponse(BaseModel):
    """Single letter record."""

    id: int
    created_at: str
    prompt: str
    content: str
    letter_type: str


class LetterListResponse(BaseModel):
    """List of letters."""

    items: list[LetterResponse]
    total: int


class LetterDeleteResponse(BaseModel):
    """Response for DELETE /letters/{id}."""

    deleted: bool
    id: int
