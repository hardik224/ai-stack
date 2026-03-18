from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from app.config.settings import Settings, get_settings

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - optional future provider
    Anthropic = None


@dataclass(frozen=True)
class LLMStreamRequest:
    messages: list[dict[str, str]]
    mode: str
    model: str | None = None


class LLMProvider(Protocol):
    def stream_chat(self, request: LLMStreamRequest) -> Iterator[str]:
        ...


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings):
        if not settings.llm_base_url:
            raise RuntimeError('LLM_BASE_URL is required for openai_compatible provider.')
        self.settings = settings
        self.client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
        )

    def stream_chat(self, request: LLMStreamRequest) -> Iterator[str]:
        request_args = {
            'model': request.model or self.settings.llm_model,
            'messages': request.messages,
            'stream': True,
            'temperature': _resolve_temperature(self.settings, request.mode),
            'top_p': self.settings.llm_top_p,
            'max_tokens': self.settings.llm_max_output_tokens,
        }
        extra_body = {}
        if self.settings.llm_reasoning_effort:
            extra_body['reasoning_effort'] = self.settings.llm_reasoning_effort
        if extra_body:
            request_args['extra_body'] = extra_body

        stream = self.client.chat.completions.create(**request_args)
        for chunk in stream:
            choices = getattr(chunk, 'choices', None) or []
            if not choices:
                continue
            delta = getattr(choices[0], 'delta', None)
            content = getattr(delta, 'content', None) if delta else None
            if content:
                yield content


class OpenAIProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.llm_api_key, timeout=settings.llm_timeout_seconds)

    def stream_chat(self, request: LLMStreamRequest) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=request.model or self.settings.llm_model,
            messages=request.messages,
            stream=True,
            temperature=_resolve_temperature(self.settings, request.mode),
            top_p=self.settings.llm_top_p,
            max_tokens=self.settings.llm_max_output_tokens,
        )
        for chunk in stream:
            choices = getattr(chunk, 'choices', None) or []
            if not choices:
                continue
            delta = getattr(choices[0], 'delta', None)
            content = getattr(delta, 'content', None) if delta else None
            if content:
                yield content


class AnthropicProvider:
    def __init__(self, settings: Settings):
        if Anthropic is None:
            raise RuntimeError('Anthropic provider selected but the anthropic package is not installed.')
        self.settings = settings
        self.client = Anthropic(api_key=settings.llm_api_key, timeout=settings.llm_timeout_seconds)

    def stream_chat(self, request: LLMStreamRequest) -> Iterator[str]:
        system_message = ''
        anthropic_messages = []
        for message in request.messages:
            if message['role'] == 'system':
                system_message = f"{system_message}\n\n{message['content']}".strip()
                continue
            anthropic_messages.append({'role': message['role'], 'content': message['content']})

        with self.client.messages.stream(
            model=request.model or self.settings.llm_model,
            system=system_message,
            messages=anthropic_messages,
            temperature=_resolve_temperature(self.settings, request.mode),
            top_p=self.settings.llm_top_p,
            max_tokens=self.settings.llm_max_output_tokens,
        ) as stream:
            for event in stream:
                if getattr(event, 'type', '') == 'content_block_delta':
                    delta = getattr(event, 'delta', None)
                    text = getattr(delta, 'text', None) if delta else None
                    if text:
                        yield text


_provider: LLMProvider | None = None



def init_llm_client(settings: Settings | None = None) -> None:
    global _provider
    if _provider is not None:
        return
    resolved = settings or get_settings()
    provider_name = resolved.llm_provider
    if provider_name == 'openai_compatible':
        if not resolved.llm_base_url:
            return
        _provider = OpenAICompatibleProvider(resolved)
        return
    if provider_name == 'openai':
        _provider = OpenAIProvider(resolved)
        return
    if provider_name == 'anthropic':
        _provider = AnthropicProvider(resolved)
        return
    raise RuntimeError(f"Unsupported LLM provider '{provider_name}'.")



def get_llm_client() -> LLMProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        init_llm_client(settings)
        if _provider is None:
            raise RuntimeError('LLM client is not configured. Set LLM_PROVIDER, LLM_BASE_URL, and LLM_MODEL.')
    return _provider



def close_llm_client() -> None:
    global _provider
    _provider = None



def stream_markdown_answer(messages: list[dict[str, str]], *, mode: str) -> Iterator[str]:
    request = LLMStreamRequest(messages=messages, mode=mode)
    yield from get_llm_client().stream_chat(request)



def _resolve_temperature(settings: Settings, mode: str) -> float:
    if mode == 'analysis':
        return max(0.2, min(settings.llm_temperature, 0.5))
    return settings.llm_temperature
