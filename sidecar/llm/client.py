"""
LLM client abstraction supporting Claude (primary) and OpenAI (secondary).

Both providers use their respective structured output mechanisms:
- Claude: tool_use (tools parameter)
- OpenAI: function calling (tools parameter with type "function")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

CLAUDE_DEEP_MODEL = "claude-opus-4-20250514"


class LLMProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


@dataclass
class LLMResponse:
    """Raw response from an LLM API call."""

    provider: LLMProvider
    raw_content: str
    tool_call_result: Optional[dict]
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def text_content(self) -> str:
        """Return the plain text content of the response."""
        return self.raw_content


class LLMClient:
    """Unified LLM client. Instantiated per-request with settings."""

    def __init__(
        self,
        provider: LLMProvider,
        api_key: str,
        model: Optional[str] = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model or self._default_model()

    def _default_model(self) -> str:
        if self.provider == LLMProvider.CLAUDE:
            return "claude-sonnet-4-20250514"
        return "gpt-4.1-mini"

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Send a prompt and return a plain text response (no tool use)."""
        if self.provider == LLMProvider.CLAUDE:
            return await self._call_claude_text(
                system_prompt, user_prompt, max_tokens, temperature,
            )
        else:
            return await self._call_openai_text(
                system_prompt, user_prompt, max_tokens, temperature,
            )

    async def call_with_tool(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_schema: dict[str, Any],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Send a prompt and force a structured tool_use/function_call response."""
        if self.provider == LLMProvider.CLAUDE:
            return await self._call_claude(
                system_prompt,
                user_prompt,
                tool_name,
                tool_schema,
                max_tokens,
                temperature,
            )
        else:
            return await self._call_openai(
                system_prompt,
                user_prompt,
                tool_name,
                tool_schema,
                max_tokens,
                temperature,
            )

    async def _call_claude(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_schema: dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[
                {
                    "name": tool_name,
                    "description": (
                        "Generate structured medical report explanation"
                    ),
                    "input_schema": tool_schema,
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )

        tool_result = None
        raw_text = ""

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                tool_result = block.input
            elif block.type == "text":
                raw_text = block.text

        return LLMResponse(
            provider=LLMProvider.CLAUDE,
            raw_content=raw_text,
            tool_call_result=tool_result,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_schema: dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import json

        import openai

        client = openai.AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": (
                            "Generate structured medical report explanation"
                        ),
                        "parameters": tool_schema,
                    },
                }
            ],
            tool_choice={
                "type": "function",
                "function": {"name": tool_name},
            },
        )

        choice = response.choices[0]
        tool_result = None
        raw_text = choice.message.content or ""

        if choice.message.tool_calls:
            tc = choice.message.tool_calls[0]
            tool_result = json.loads(tc.function.arguments)

        return LLMResponse(
            provider=LLMProvider.OPENAI,
            raw_content=raw_text,
            tool_call_result=tool_result,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    async def _call_claude_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = ""
        for block in response.content:
            if block.type == "text":
                raw_text += block.text

        return LLMResponse(
            provider=LLMProvider.CLAUDE,
            raw_content=raw_text,
            tool_call_result=None,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def _call_openai_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import openai

        client = openai.AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        choice = response.choices[0]
        raw_text = choice.message.content or ""

        return LLMResponse(
            provider=LLMProvider.OPENAI,
            raw_content=raw_text,
            tool_call_result=None,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
