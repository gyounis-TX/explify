"""SQS wrapper for the async extraction pipeline (scaffolding).

The message body is ONLY the job_id — no PHI ever transits the queue. Everything else
lives in Postgres/S3 behind IAM. If EXTRACTION_QUEUE_URL is unset, enqueue() raises so
the API can fall back to the synchronous path.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

import boto3


def queue_url() -> Optional[str]:
    return os.getenv("EXTRACTION_QUEUE_URL") or None


@lru_cache(maxsize=1)
def _client():
    return boto3.client("sqs", region_name=os.getenv("AWS_REGION", "us-east-1"))


def enqueue(job_id: str) -> None:
    url = queue_url()
    if not url:
        raise RuntimeError("EXTRACTION_QUEUE_URL not configured")
    _client().send_message(QueueUrl=url, MessageBody=json.dumps({"job_id": job_id}))


def receive(max_messages: int = 1, wait_seconds: int = 20, visibility_timeout: int = 900):
    """Long-poll the queue. Returns a list of raw SQS messages."""
    url = queue_url()
    if not url:
        raise RuntimeError("EXTRACTION_QUEUE_URL not configured")
    resp = _client().receive_message(
        QueueUrl=url,
        MaxNumberOfMessages=max(1, min(10, max_messages)),
        WaitTimeSeconds=wait_seconds,
        VisibilityTimeout=visibility_timeout,
    )
    return resp.get("Messages", [])


def delete(receipt_handle: str) -> None:
    url = queue_url()
    if not url:
        return
    _client().delete_message(QueueUrl=url, ReceiptHandle=receipt_handle)


def parse_job_id(message: dict) -> Optional[str]:
    try:
        return json.loads(message.get("Body", "{}")).get("job_id")
    except (ValueError, TypeError):
        return None
