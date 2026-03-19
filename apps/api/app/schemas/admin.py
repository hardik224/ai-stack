from uuid import UUID

from pydantic import BaseModel, Field


class BulkDeleteRequest(BaseModel):
    ids: list[UUID] = Field(default_factory=list, min_length=1)
