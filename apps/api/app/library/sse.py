import json
from typing import Any

from app.library.security import utcnow



def format_sse_event(event_type: str, data: dict[str, Any] | None = None, *, session_id: str | None = None, message_id: str | None = None) -> str:
    payload: dict[str, Any] = {
        'type': event_type,
        'timestamp': utcnow().isoformat(),
        'data': data or {},
    }
    if session_id:
        payload['session_id'] = session_id
    if message_id:
        payload['message_id'] = message_id
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str, ensure_ascii=True)}\n\n"



def format_sse_comment(text: str) -> str:
    return f": {text}\n\n"
