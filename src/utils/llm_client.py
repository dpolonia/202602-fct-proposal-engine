"""
Unified LLM client with provider abstraction.
Reads provider/model from config.yaml (via cfg), API keys from .env (via secrets).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import LLMProvider, LLMRole, cfg, secrets
from src.utils.prompt_loader import get_prompt
from src.utils.sanitize import redact_secrets

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: LLMProvider
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""


class BaseLLMClient(ABC):
    provider: LLMProvider

    @abstractmethod
    async def generate(
        self, prompt: str, system: str = "", max_tokens: int = 4096, temperature: float = 0.3
    ) -> LLMResponse: ...

    async def generate_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
    ) -> LLMResponse:
        json_instruction = get_prompt("generator", "json_instruction")
        return await self.generate(
            prompt + "\n\n" + json_instruction,
            system=system,
            max_tokens=max_tokens,
            temperature=0.1,
        )


# --- Retryable error helpers ----------------------------------------------------


def _is_retryable_status(exc: Exception) -> bool:
    """Check if an HTTP/API error has a retryable status code."""
    exc_str = str(exc).lower()
    return any(
        k in exc_str
        for k in (
            "429",
            "rate",
            "overloaded",
            "500",
            "502",
            "503",
            "529",
            "timeout",
            "connection",
            "unavailable",
        )
    )


class _RetryableAPIError(Exception):
    """Wrapper for provider errors that are safe to retry."""


# --- Provider implementations ---------------------------------------------------


class AnthropicClient(BaseLLMClient):
    provider = LLMProvider.ANTHROPIC

    def __init__(self, model: str):
        import anthropic

        self.client = anthropic.AsyncAnthropic(api_key=secrets.anthropic_api_key)
        self.model = model

    @retry(
        retry=retry_if_exception_type(_RetryableAPIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        before_sleep=lambda rs: logger.warning(
            "Anthropic retry %d/3 after: %s",
            rs.attempt_number,
            redact_secrets(str(rs.outcome.exception())),
        ),
    )
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        try:
            msg = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or get_prompt("system", "default"),
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            if _is_retryable_status(exc):
                raise _RetryableAPIError(redact_secrets(f"{type(exc).__name__}: {exc}")) from exc
            raise
        return LLMResponse(
            text=msg.content[0].text,
            model=self.model,
            provider=self.provider,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            finish_reason=msg.stop_reason or "",
        )


class OpenAIClient(BaseLLMClient):
    provider = LLMProvider.OPENAI

    def __init__(self, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=secrets.openai_api_key)
        self.model = model

    @retry(
        retry=retry_if_exception_type(_RetryableAPIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        before_sleep=lambda rs: logger.warning(
            "OpenAI retry %d/3 after: %s",
            rs.attempt_number,
            redact_secrets(str(rs.outcome.exception())),
        ),
    )
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            if _is_retryable_status(exc):
                raise _RetryableAPIError(redact_secrets(f"{type(exc).__name__}: {exc}")) from exc
            raise
        c = resp.choices[0]
        return LLMResponse(
            text=c.message.content or "",
            model=self.model,
            provider=self.provider,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            finish_reason=c.finish_reason or "",
        )


class _GeminiRetryableError(Exception):
    """Wrapper for Gemini errors that are safe to retry."""


class GoogleClient(BaseLLMClient):
    provider = LLMProvider.GOOGLE

    def __init__(self, model: str):
        from google import genai

        self.client = genai.Client(api_key=secrets.google_api_key)
        self.model = model

    @retry(
        retry=retry_if_exception_type(_GeminiRetryableError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(min=2, max=60),
        before_sleep=lambda rs: logger.warning(
            "Gemini retry %d/4 after: %s",
            rs.attempt_number,
            redact_secrets(str(rs.outcome.exception())),
        ),
    )
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system or get_prompt("system", "default"),
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            exc_name = type(exc).__name__
            exc_str = str(exc).lower()
            # Rate-limit, quota, and transient server errors are retryable
            if any(
                k in exc_str
                for k in (
                    "429",
                    "rate",
                    "quota",
                    "resource_exhausted",
                    "500",
                    "503",
                    "unavailable",
                    "deadline",
                )
            ):
                raise _GeminiRetryableError(redact_secrets(f"{exc_name}: {exc}")) from exc
            # Auth, invalid request, and permission errors are not
            logger.error("Gemini non-retryable error (%s): %s", exc_name, redact_secrets(str(exc)))
            raise

        # Handle safety-blocked or empty responses
        if not resp.candidates:
            reason = getattr(resp, "prompt_feedback", None)
            raise ValueError(f"Gemini returned no candidates. Prompt feedback: {reason}")

        candidate = resp.candidates[0]
        finish = getattr(candidate, "finish_reason", None)
        if finish and str(finish) == "SAFETY":
            blocked = getattr(candidate, "safety_ratings", [])
            raise ValueError(f"Gemini blocked response (SAFETY). Ratings: {blocked}")

        text = resp.text or ""
        if not text.strip():
            logger.warning("Gemini returned empty text; using empty string")

        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.provider,
            input_tokens=(
                getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0
            ),
            output_tokens=(
                getattr(resp.usage_metadata, "candidates_token_count", 0)
                if resp.usage_metadata
                else 0
            ),
        )


class HuggingFaceClient(BaseLLMClient):
    provider = LLMProvider.HUGGINGFACE

    def __init__(self, model: str):
        from huggingface_hub import AsyncInferenceClient

        self.client = AsyncInferenceClient(token=secrets.huggingface_api_key)
        self.model = model

    @retry(
        retry=retry_if_exception_type(_RetryableAPIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        before_sleep=lambda rs: logger.warning(
            "HuggingFace retry %d/3 after: %s",
            rs.attempt_number,
            redact_secrets(str(rs.outcome.exception())),
        ),
    )
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = await self.client.chat_completion(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            if _is_retryable_status(exc):
                raise _RetryableAPIError(redact_secrets(f"{type(exc).__name__}: {exc}")) from exc
            raise
        c = resp.choices[0]
        return LLMResponse(
            text=c.message.content or "",
            model=self.model,
            provider=self.provider,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            finish_reason=c.finish_reason or "",
        )


# --- Factory -------------------------------------------------------------------

_ClientType = type[AnthropicClient | OpenAIClient | GoogleClient | HuggingFaceClient]
_CLIENTS: dict[LLMProvider, _ClientType] = {
    LLMProvider.ANTHROPIC: AnthropicClient,
    LLMProvider.OPENAI: OpenAIClient,
    LLMProvider.GOOGLE: GoogleClient,
    LLMProvider.HUGGINGFACE: HuggingFaceClient,
}


def get_llm_client(
    provider: LLMProvider | str | None = None,
    model: str | None = None,
) -> BaseLLMClient:
    """
    Build an LLM client.  Falls back to cfg.generator settings when not specified.
    """
    p = LLMProvider(provider) if provider else cfg.generator.provider
    m = model or cfg.generator.model

    if not secrets.has_key(p.value):
        raise ValueError(
            f"No API key found for provider '{p.value}'. "
            f"Add {p.value.upper()}_API_KEY to your .env file."
        )

    cls = _CLIENTS.get(p)
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {p}")
    return cls(model=m)


def get_llm_for_role(role: LLMRole) -> BaseLLMClient:
    """Build a client from an LLMRole (generator, consensus, revision)."""
    return get_llm_client(provider=role.provider, model=role.model)
