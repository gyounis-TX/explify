"""SQS-driven extraction worker (scaffolding).

Long-polls the extraction queue and runs the EXISTING ExtractionPipeline for each job,
then writes the result to S3 + the job row. Designed to run as a Fargate service that
autoscales 0 ⇄ N on queue depth (infra/async-extraction/), so extraction compute is
paid only while jobs exist.

Run: `python -m worker.extraction_worker`  (CMD of infra/async-extraction/worker.Dockerfile)

Idempotency & reliability:
  * The SQS message body is only the job_id.
  * If a job is already terminal (done/failed) the message is deleted (handles SQS
    at-least-once redelivery).
  * On success the message is deleted; on error it is NOT deleted, so SQS redelivers and
    eventually routes to the DLQ after maxReceiveCount.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from extraction import ExtractionPipeline
from llm.factory import build_extract_llm_client
from jobs import queue as jq
from jobs import s3io, store
from jobs.models import JobKind, JobStatus

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("extraction_worker")

_pipeline = ExtractionPipeline()

# Map a job kind to a temp-file suffix for the pipeline's file-based entrypoints.
_SUFFIX = {JobKind.PDF: ".pdf", JobKind.IMAGE: ".img"}


async def _run_pipeline(job) -> str:
    """Run the appropriate pipeline entry and return serialized ExtractionResult JSON."""
    # Build the same per-user vision-OCR client the synchronous /extract routes use, so
    # low-confidence pages get the Bedrock vision-OCR fallback (accuracy parity). Returns
    # None if the user has no usable provider/creds, in which case the pipeline runs
    # tesseract-only — identical to the request path's behavior.
    llm_client = await build_extract_llm_client(job.user_id)

    if job.kind == JobKind.TEXT:
        text = s3io.get_input(job.input_s3_key).decode("utf-8", errors="replace")
        result = _pipeline.extract_from_text(text)
    else:
        data = s3io.get_input(job.input_s3_key)
        with tempfile.NamedTemporaryFile(suffix=_SUFFIX.get(job.kind, ""), delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            if job.kind == JobKind.PDF:
                result = await _pipeline.extract_from_pdf(tmp.name, llm_client=llm_client)
            else:
                result = await _pipeline.extract_from_image(tmp.name, llm_client=llm_client)

    # ExtractionResult is a Pydantic model (api/models.py)
    return result.model_dump_json()


async def _handle(message: dict) -> None:
    job_id = jq.parse_job_id(message)
    receipt = message.get("ReceiptHandle")
    if not job_id:
        logger.warning("message without job_id; deleting")
        if receipt:
            jq.delete(receipt)
        return

    job = await store.get_job(job_id)
    if job is None:
        logger.warning("job %s not found; deleting message", job_id)
        if receipt:
            jq.delete(receipt)
        return
    if job.status in (JobStatus.DONE, JobStatus.FAILED):
        logger.info("job %s already %s; deleting message", job_id, job.status.value)
        if receipt:
            jq.delete(receipt)
        return

    logger.info("processing job %s (%s)", job_id, job.kind.value)
    await store.mark_processing(job_id)
    try:
        result_json = await _run_pipeline(job)
        result_key = s3io.put_result(job_id, result_json)
        await store.mark_done(job_id, result_key)
        if receipt:
            jq.delete(receipt)
        logger.info("job %s done", job_id)
    except Exception as exc:  # noqa: BLE001 - record and let SQS retry/DLQ
        logger.exception("job %s failed: %s", job_id, exc)
        await store.mark_failed(job_id, repr(exc))
        # Do NOT delete the message: SQS redelivers, then DLQ after maxReceiveCount.


async def main() -> None:
    await store.ensure_table()
    logger.info("extraction worker started; polling %s", jq.queue_url())
    idle_exit = int(os.getenv("WORKER_IDLE_EXIT_SECONDS", "0"))  # 0 = run forever
    idle = 0
    while True:
        messages = jq.receive(max_messages=1, wait_seconds=20)
        if not messages:
            idle += 20
            if idle_exit and idle >= idle_exit:
                logger.info("idle for %ss; exiting for scale-in", idle)
                return
            continue
        idle = 0
        for message in messages:
            await _handle(message)


if __name__ == "__main__":
    asyncio.run(main())
