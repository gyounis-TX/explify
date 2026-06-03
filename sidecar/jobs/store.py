"""Postgres-backed job store for async extraction (scaffolding).

Reuses the existing asyncpg pool from storage.pg_database. The table is created
idempotently (CREATE TABLE IF NOT EXISTS) so this can be exercised without touching the
project's migration runner; promote the DDL into a real migration before production.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from storage.pg_database import _get_pool  # existing asyncpg pool accessor

from .models import ExtractionJob, JobKind, JobStatus

_DDL = """
CREATE TABLE IF NOT EXISTS extraction_jobs (
    job_id        UUID PRIMARY KEY,
    user_id       TEXT,
    practice_id   TEXT,
    kind          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'queued',
    input_s3_key  TEXT,
    result_s3_key TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS extraction_jobs_status_idx ON extraction_jobs (status);
CREATE INDEX IF NOT EXISTS extraction_jobs_user_idx ON extraction_jobs (user_id);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_job(row) -> ExtractionJob:
    return ExtractionJob(
        job_id=str(row["job_id"]),
        user_id=row["user_id"],
        practice_id=row["practice_id"],
        kind=JobKind(row["kind"]),
        status=JobStatus(row["status"]),
        input_s3_key=row["input_s3_key"],
        result_s3_key=row["result_s3_key"],
        attempts=row["attempts"],
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


async def ensure_table() -> None:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(_DDL)


async def create_job(
    kind: JobKind,
    input_s3_key: Optional[str],
    user_id: Optional[str] = None,
    practice_id: Optional[str] = None,
) -> ExtractionJob:
    job_id = str(uuid.uuid4())
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO extraction_jobs (job_id, user_id, practice_id, kind, status, input_s3_key)
            VALUES ($1, $2, $3, $4, 'queued', $5)
            RETURNING *
            """,
            job_id, user_id, practice_id, kind.value, input_s3_key,
        )
    return _row_to_job(row)


async def get_job(job_id: str, user_id: Optional[str] = None) -> Optional[ExtractionJob]:
    """Fetch a job. If user_id is given, scope to that user (tenant isolation)."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        if user_id is not None:
            row = await conn.fetchrow(
                "SELECT * FROM extraction_jobs WHERE job_id = $1 AND user_id = $2",
                job_id, user_id,
            )
        else:
            row = await conn.fetchrow(
                "SELECT * FROM extraction_jobs WHERE job_id = $1", job_id,
            )
    return _row_to_job(row) if row else None


async def set_input_key(job_id: str, input_s3_key: str) -> None:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE extraction_jobs SET input_s3_key = $2, updated_at = $3 WHERE job_id = $1",
            job_id, input_s3_key, _now(),
        )


async def mark_processing(job_id: str) -> None:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE extraction_jobs
               SET status = 'processing', attempts = attempts + 1, updated_at = $2
             WHERE job_id = $1
            """,
            job_id, _now(),
        )


async def mark_done(job_id: str, result_s3_key: str) -> None:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE extraction_jobs
               SET status = 'done', result_s3_key = $2, last_error = NULL,
                   completed_at = $3, updated_at = $3
             WHERE job_id = $1
            """,
            job_id, result_s3_key, _now(),
        )


async def mark_failed(job_id: str, error: str) -> None:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE extraction_jobs
               SET status = 'failed', last_error = $2, updated_at = $3
             WHERE job_id = $1
            """,
            job_id, error[:2000], _now(),
        )
