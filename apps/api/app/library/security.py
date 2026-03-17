import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, Request, status


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "collection"


def sanitize_filename(filename: str) -> str:
    return Path(filename or "upload").name


def get_client_ip(request: Request) -> str | None:
    if request.client and request.client.host:
        return request.client.host
    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return None
    return forwarded_for.split(",")[0].strip()


def get_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def get_api_key_from_request(request: Request) -> str | None:
    direct = request.headers.get("x-api-key")
    if direct:
        return direct.strip()
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("apikey "):
        return authorization.split(" ", 1)[1].strip()
    return None


def validate_limit_offset(limit: int, offset: int, default_limit: int, max_limit: int) -> tuple[int, int]:
    safe_limit = limit if limit > 0 else default_limit
    if safe_limit > max_limit:
        safe_limit = max_limit
    safe_offset = max(offset, 0)
    return safe_limit, safe_offset


def require_condition(condition: bool, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
    if not condition:
        raise HTTPException(status_code=status_code, detail=detail)
