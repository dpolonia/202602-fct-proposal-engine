"""
Unified LLM client with provider abstraction.
Reads provider/model from config.yaml (via cfg), API keys from .env (via secrets).
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import LLMProvider, LLMRole, cfg, secrets

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
    async def generate(self, prompt: str, system: str = "", max_tokens: int = 4096,
                       temperature: float = 0.3) -> LLMResponse: ...

    async def generate_json(self, prompt: str, system: str = "", max_tokens: int = 4096) -> LLMResponse:
        return await self.generate(
            prompt + "\n\nRespond ONLY with valid JSON. No markdown, no backticks.",
            system=system, max_tokens=max_tokens, temperature=0.1,
        )


# --- Provider implementations ---------------------------------------------------

class AnthropicClient(BaseLLMClient):
    provider = LLMProvider.ANTHROPIC

    def __init__(self, model: str):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=secrets.anthropic_api_key)
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        msg = await self.client.messages.create(
            model=self.model, max_tokens=max_tokens, temperature=temperature,
            system=system or "You are an expert academic research proposal writer.",
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            text=msg.content[0].text, model=self.model, provider=self.provider,
            input_tokens=msg.usage.input_tokens, output_tokens=msg.usage.output_tokens,
            finish_reason=msg.stop_reason or "",
        )


class OpenAIClient(BaseLLMClient):
    provider = LLMProvider.OPENAI

    def __init__(self, model: str):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=secrets.openai_api_key)
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=max_tokens, temperature=temperature,
        )
        c = resp.choices[0]
        return LLMResponse(
            text=c.message.content or "", model=self.model, provider=self.provider,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            finish_reason=c.finish_reason or "",
        )


class GoogleClient(BaseLLMClient):
    provider = LLMProvider.GOOGLE

    def __init__(self, model: str):
        from google import genai
        self.client = genai.Client(api_key=secrets.google_api_key)
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=system or "You are an expert academic research proposal writer.",
            max_output_tokens=max_tokens, temperature=temperature,
        )
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, lambda: self.client.models.generate_content(
                model=self.model, contents=prompt, config=config,
            ),
        )
        return LLMResponse(
            text=resp.text or "", model=self.model, provider=self.provider,
            input_tokens=getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0,
            output_tokens=getattr(resp.usage_metadata, "candidates_token_count", 0) if resp.usage_metadata else 0,
        )


class HuggingFaceClient(BaseLLMClient):
    provider = LLMProvider.HUGGINGFACE

    def __init__(self, model: str):
        from huggingface_hub import AsyncInferenceClient
        self.client = AsyncInferenceClient(token=secrets.huggingface_api_key)
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.3):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await self.client.chat_completion(
            model=self.model, messages=messages, max_tokens=max_tokens, temperature=temperature,
        )
        c = resp.choices[0]
        return LLMResponse(
            text=c.message.content or "", model=self.model, provider=self.provider,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            finish_reason=c.finish_reason or "",
        )


# --- Factory -------------------------------------------------------------------

_CLIENTS = {
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
