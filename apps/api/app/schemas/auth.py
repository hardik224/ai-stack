from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    user_id: UUID | None = None
    scope: Literal["chatbot"] = "chatbot"
    expires_in_days: int | None = Field(default=90, ge=1, le=3650)
