from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BulkDeleteRequest(BaseModel):
    ids: list[UUID] = Field(default_factory=list, min_length=1)


LLMProvider = Literal['anthropic', 'openai', 'openai_compatible']


class LlmConfigCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    provider: LLMProvider
    base_url: str | None = Field(default=None, max_length=1024)
    api_key: str | None = Field(default=None, max_length=4096)
    model: str = Field(min_length=1, max_length=255)
    timeout_seconds: int = Field(default=180, ge=1, le=600)
    max_output_tokens: int = Field(default=1400, ge=1, le=32768)
    temperature: float = Field(default=0.6, ge=0, le=2)
    top_p: float = Field(default=0.95, ge=0, le=1)
    reasoning_effort: str | None = Field(default=None, max_length=32)
    is_enabled: bool = True
    activate: bool = False
    metadata: dict[str, Any] | None = None


class LlmConfigUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    provider: LLMProvider
    base_url: str | None = Field(default=None, max_length=1024)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False
    model: str = Field(min_length=1, max_length=255)
    timeout_seconds: int = Field(default=180, ge=1, le=600)
    max_output_tokens: int = Field(default=1400, ge=1, le=32768)
    temperature: float = Field(default=0.6, ge=0, le=2)
    top_p: float = Field(default=0.95, ge=0, le=1)
    reasoning_effort: str | None = Field(default=None, max_length=32)
    is_enabled: bool = True
    activate: bool = False
    metadata: dict[str, Any] | None = None
