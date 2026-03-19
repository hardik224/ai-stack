from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from app.library import cache
from app.services.llm_config_service import RuntimeLLMConfig, get_active_runtime_config

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
    def __init__(self, config: RuntimeLLMConfig):
        if not config.base_url:
            raise RuntimeError('Base URL is required for openai_compatible provider.')
        self.config = config
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key or 'local-vllm-key',
            timeout=config.timeout_seconds,
        )

    def stream_chat(self, request: LLMStreamRequest) -> Iterator[str]:
        request_args = {
            'model': request.model or self.config.model,
            'messages': request.messages,
            'stream': True,
            'temperature': _resolve_temperature(self.config, request.mode),
            'top_p': self.config.top_p,
            'max_tokens': self.config.max_output_tokens,
        }
        extra_body = {}
        if self.config.reasoning_effort:
            extra_body['reasoning_effort'] = self.config.reasoning_effort
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
    def __init__(self, config: RuntimeLLMConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, timeout=config.timeout_seconds)

    def stream_chat(self, request: LLMStreamRequest) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=request.model or self.config.model,
            messages=request.messages,
            stream=True,
            temperature=_resolve_temperature(self.config, request.mode),
            top_p=self.config.top_p,
            max_tokens=self.config.max_output_tokens,
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
    def __init__(self, config: RuntimeLLMConfig):
        if Anthropic is None:
            raise RuntimeError('Anthropic provider selected but the anthropic package is not installed.')
        self.config = config
        self.client = Anthropic(api_key=config.api_key, timeout=config.timeout_seconds)

    def stream_chat(self, request: LLMStreamRequest) -> Iterator[str]:
        system_message = ''
        anthropic_messages = []
        for message in request.messages:
            if message['role'] == 'system':
                system_message = f"{system_message}\n\n{message['content']}".strip()
                continue
            anthropic_messages.append({'role': message['role'], 'content': message['content']})

        with self.client.messages.stream(
            model=request.model or self.config.model,
            system=system_message,
            messages=anthropic_messages,
            temperature=_resolve_temperature(self.config, request.mode),
            top_p=self.config.top_p,
            max_tokens=self.config.max_output_tokens,
        ) as stream:
            for event in stream:
                if getattr(event, 'type', '') == 'content_block_delta':
                    delta = getattr(event, 'delta', None)
                    text = getattr(delta, 'text', None) if delta else None
                    if text:
                        yield text


_provider: LLMProvider | None = None
_runtime_config: RuntimeLLMConfig | None = None
_provider_signature: dict | None = None
_provider_version: int | None = None



def _build_provider(config: RuntimeLLMConfig) -> LLMProvider:
    provider_name = config.provider
    if provider_name == 'openai_compatible':
        return OpenAICompatibleProvider(config)
    if provider_name == 'openai':
        return OpenAIProvider(config)
    if provider_name == 'anthropic':
        return AnthropicProvider(config)
    raise RuntimeError(f"Unsupported LLM provider '{provider_name}'.")



def init_llm_client(settings=None) -> None:
    try:
        get_runtime_llm_config()
        get_llm_client()
    except Exception:
        return



def get_runtime_llm_config() -> RuntimeLLMConfig:
    global _runtime_config, _provider_version
    current_version = cache.get_llm_config_version()
    if _runtime_config is not None and _provider_version == current_version:
        return _runtime_config
    runtime_config = get_active_runtime_config()
    _runtime_config = runtime_config
    _provider_version = current_version
    return runtime_config



def get_llm_client(runtime_config: RuntimeLLMConfig | None = None) -> LLMProvider:
    global _provider, _provider_signature, _provider_version, _runtime_config
    resolved = runtime_config or get_runtime_llm_config()
    current_version = cache.get_llm_config_version()
    signature = resolved.signature()
    if _provider is None or _provider_signature != signature or _provider_version != current_version:
        _provider = _build_provider(resolved)
        _provider_signature = signature
        _provider_version = current_version
        _runtime_config = resolved
    return _provider



def close_llm_client() -> None:
    global _provider, _runtime_config, _provider_signature, _provider_version
    _provider = None
    _runtime_config = None
    _provider_signature = None
    _provider_version = None



def stream_markdown_answer(messages: list[dict[str, str]], *, mode: str, runtime_config: RuntimeLLMConfig | None = None) -> Iterator[str]:
    request = LLMStreamRequest(messages=messages, mode=mode)
    yield from get_llm_client(runtime_config=runtime_config).stream_chat(request)



def _resolve_temperature(config: RuntimeLLMConfig, mode: str) -> float:
    if mode == 'analysis':
        return max(0.2, min(config.temperature, 0.5))
    return config.temperature
