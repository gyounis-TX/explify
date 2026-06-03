"""S3 I/O for async extraction inputs/results (scaffolding).

Inputs are uploaded source documents; results are serialized ExtractionResult JSON kept
off the Postgres row. Objects are written with SSE; set a short lifecycle expiry on the
bucket/prefix for PHI (see infra/async-extraction/README.md).
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3

_INPUT_PREFIX = "extraction-jobs/input/"
_RESULT_PREFIX = "extraction-jobs/result/"


def bucket() -> str:
    b = os.getenv("S3_BUCKET")
    if not b:
        raise RuntimeError("S3_BUCKET not configured")
    return b


@lru_cache(maxsize=1)
def _client():
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))


def put_input(job_id: str, data: bytes, content_type: str) -> str:
    key = f"{_INPUT_PREFIX}{job_id}"
    _client().put_object(
        Bucket=bucket(), Key=key, Body=data,
        ContentType=content_type, ServerSideEncryption="AES256",
    )
    return key


def get_input(key: str) -> bytes:
    return _client().get_object(Bucket=bucket(), Key=key)["Body"].read()


def put_result(job_id: str, result_json: str) -> str:
    key = f"{_RESULT_PREFIX}{job_id}.json"
    _client().put_object(
        Bucket=bucket(), Key=key, Body=result_json.encode("utf-8"),
        ContentType="application/json", ServerSideEncryption="AES256",
    )
    return key


def get_result(key: str) -> str:
    return _client().get_object(Bucket=bucket(), Key=key)["Body"].read().decode("utf-8")
