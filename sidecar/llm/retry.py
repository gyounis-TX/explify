"""Retry logic with exponential backoff for LLM API calls."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class LLMRetryError(Exception):
    """All retry attempts exhausted."""

    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(f"Failed after {attempts} attempts: {last_error}")


async def with_retry(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 15.0,
    timeout_seconds: float = 90.0,
    **kwargs: Any,
) -> Any:
    """
    Call fn with exponential backoff retry and overall timeout.

    Retries on: 429 rate limits, 5xx server errors, network timeouts.
    Does NOT retry: 401/403 auth errors, 400 client errors.
    On timeout, raises LLMRetryError wrapping a TimeoutError.
    """
    last_error: Exception | None = None

    try:
        async with asyncio.timeout(timeout_seconds):
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()

                    # Do not retry auth errors
                    if any(
                        code in error_str
                        for code in ["401", "403", "authentication", "invalid api key"]
                    ):
                        raise

                    # Do not retry client errors (except rate limits)
                    if "400" in error_str and "429" not in error_str:
                        raise

                    if attempt < max_attempts:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.warning(
                            "LLM call attempt %d failed: %s. Retrying in %.1fs...",
                            attempt,
                            e,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise LLMRetryError(last_error, max_attempts)
    except TimeoutError:
        raise LLMRetryError(
            TimeoutError(f"LLM call timed out after {timeout_seconds}s"),
            max_attempts,
        )

    raise LLMRetryError(last_error or Exception("Unknown error"), max_attempts)
