"""Additive async-extraction API routes (scaffolding).

NOT mounted by default. To enable, set ASYNC_EXTRACTION=true and mount this router in
main.py / api.routes:

    from api.jobs_routes import router as jobs_router
    if async_extraction_enabled():
        app.include_router(jobs_router)

The existing synchronous /extract/* routes are unchanged and remain the fallback.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from jobs import s3io, store
from jobs.models import JobKind, JobStatus, async_extraction_enabled

logger = logging.getLogger(__name__)
router = APIRouter()


def _user_id(request: Request):
    return getattr(request.state, "user_id", None)


def _practice_id(request: Request):
    return getattr(request.state, "practice_id", None)


_KIND_BY_CONTENT = {
    "application/pdf": JobKind.PDF,
    "image/png": JobKind.IMAGE,
    "image/jpeg": JobKind.IMAGE,
    "image/tiff": JobKind.IMAGE,
}


@router.post("/extract/jobs", status_code=202)
async def submit_extraction_job(request: Request, file: UploadFile = File(...)):
    """Accept a document, stash it in S3, enqueue a job, return 202 + job_id."""
    if not async_extraction_enabled():
        raise HTTPException(status_code=404, detail="Async extraction disabled")

    kind = _KIND_BY_CONTENT.get((file.content_type or "").lower())
    if kind is None:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {file.content_type}")

    data = await file.read()
    await store.ensure_table()
    # Create the row first to get a job_id, then store input under that id, then enqueue.
    job = await store.create_job(
        kind=kind, input_s3_key=None,
        user_id=_user_id(request), practice_id=_practice_id(request),
    )
    key = s3io.put_input(job.job_id, data, file.content_type or "application/octet-stream")
    await store.set_input_key(job.job_id, key)

    from jobs import queue as jq
    try:
        jq.enqueue(job.job_id)
    except RuntimeError as exc:
        logger.error("enqueue failed: %s", exc)
        await store.mark_failed(job.job_id, "queue unavailable")
        raise HTTPException(status_code=503, detail="Extraction queue unavailable") from exc

    return {"job_id": job.job_id, "status": JobStatus.QUEUED.value}


@router.get("/extract/jobs/{job_id}")
async def get_extraction_job(request: Request, job_id: str):
    """Poll job status; returns the ExtractionResult JSON when done."""
    job = await store.get_job(job_id, user_id=_user_id(request))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    body = {
        "job_id": job.job_id,
        "status": job.status.value,
        "attempts": job.attempts,
    }
    if job.status == JobStatus.DONE and job.result_s3_key:
        body["result"] = s3io.get_result(job.result_s3_key)
    elif job.status == JobStatus.FAILED:
        body["error"] = job.last_error
    return body
