from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "internal_user", "user"] = "user"
    status: Literal["active", "disabled"] = "active"
