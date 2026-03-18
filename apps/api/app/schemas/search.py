from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    collection_id: UUID | None = None
    file_id: UUID | None = None
    limit: int = Field(default=5, ge=1, le=20)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
