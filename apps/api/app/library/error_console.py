import json
import traceback
from datetime import datetime, timezone
from typing import Any

from app.library.redis_client import get_redis_client


ERROR_CONSOLE_KEY = 'ai-stack:error-console'
ERROR_CONSOLE_MAX_ITEMS = 500


def _safe_text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value)
    return text[:4000]


def record_backend_error(*, source: str, message: str, level: str = 'ERROR', details: dict[str, Any] | None = None, exc: Exception | None = None) -> None:
    payload = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'level': level,
        'source': source,
        'message': _safe_text(message),
        'details': details or {},
    }
    if exc is not None:
        payload['exception_type'] = exc.__class__.__name__
        payload['exception'] = _safe_text(exc)
        payload['traceback'] = _safe_text(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))

    client = get_redis_client()
    serialized = json.dumps(payload, default=str)
    client.lpush(ERROR_CONSOLE_KEY, serialized)
    client.ltrim(ERROR_CONSOLE_KEY, 0, ERROR_CONSOLE_MAX_ITEMS - 1)


def list_backend_errors(*, limit: int = 200) -> list[dict[str, Any]]:
    client = get_redis_client()
    rows = client.lrange(ERROR_CONSOLE_KEY, 0, max(limit - 1, 0))
    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            items.append(json.loads(row))
        except Exception:
            items.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'level': 'ERROR',
                'source': 'error_console',
                'message': _safe_text(row),
                'details': {},
            })
    return items
