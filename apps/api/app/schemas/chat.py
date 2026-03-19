from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=12000)
    mode: Literal['knowledge_qa', 'analysis'] = 'knowledge_qa'
    session_id: UUID | None = None
    collection_id: UUID | None = None
    file_id: UUID | None = None
    source_type: Literal['pdf', 'csv', 'excel'] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    dedupe: bool = True
    max_context_chunks: int | None = Field(default=None, ge=1, le=20)
    max_context_chars: int | None = Field(default=None, ge=500, le=50000)
