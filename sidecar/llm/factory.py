"""Factory for building an LLMClient from a user's stored settings.

Request-free so both the synchronous extraction routes and the async extraction worker
construct the *same* vision-OCR client from a user_id. The logic mirrors what the
synchronous `/extract/*` routes have always done (provider from settings, key/creds from
`get_api_key_for_provider`); it was extracted here so the worker can reach accuracy
parity with the request path.
"""

from __future__ import annotations

import logging
from typing import Optional

from api import settings_store
from llm.client import LLMClient, LLMProvider

logger = logging.getLogger(__name__)


async def build_extract_llm_client(user_id: Optional[str]) -> Optional[LLMClient]:
    """Build an LLM client for vision-OCR fallback, or None if unavailable."""
    try:
        settings = await settings_store.get_settings(user_id=user_id)
        provider_str = settings.llm_provider.value
        api_key = settings_store.get_api_key_for_provider(provider_str)
        if api_key:
            return LLMClient(provider=LLMProvider(provider_str), api_key=api_key)
    except Exception:
        logger.debug("Could not build LLM client for vision OCR", exc_info=True)
    return None
