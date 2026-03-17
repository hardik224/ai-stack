from typing import Literal

from pydantic import BaseModel, Field


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    slug: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    visibility: Literal["private", "internal", "shared"] = "internal"
