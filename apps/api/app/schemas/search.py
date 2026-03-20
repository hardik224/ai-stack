from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    collection_id: UUID | None = None
    file_id: UUID | None = None
    source_type: Literal['pdf', 'csv', 'excel', 'txt'] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    limit: int | None = Field(default=5, ge=1, le=20)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    dedupe: bool = True
    enable_vector: bool = True
    enable_keyword: bool = True
    enable_rerank: bool | None = None
    debug: bool = False
    max_context_chunks: int | None = Field(default=None, ge=1, le=20)
    max_context_chars: int | None = Field(default=None, ge=500, le=50000)
    session_id: UUID | None = None

    @model_validator(mode='after')
    def normalize_limits(self):
        resolved_top_k = self.top_k or self.limit or 5
        self.top_k = resolved_top_k
        self.limit = resolved_top_k
        return self
