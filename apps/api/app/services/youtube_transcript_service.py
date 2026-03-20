from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from youtube_transcript_api import YouTubeTranscriptApi

from app.config.settings import get_settings
from app.library.storage import download_bytes, ensure_bucket_exists, upload_bytes


YOUTUBE_ID_PATTERNS = [
    r"v=([a-zA-Z0-9_-]{11})",
    r"youtu\.be/([a-zA-Z0-9_-]{11})",
    r"embed/([a-zA-Z0-9_-]{11})",
]


def create_transcript_file(*, youtube_url: str, current_identity: dict, download_base_url: str) -> dict:
    _require_api_key_identity(current_identity)

    video_id = extract_video_id(youtube_url)
    transcript_entries = fetch_transcript(video_id)
    content = build_transcript_text(video_id=video_id, youtube_url=youtube_url, entries=transcript_entries)
    filename = f'youtube-transcript-{video_id}.txt'
    object_key = f"utilities/youtube-transcripts/{datetime.now(tz=UTC).strftime('%Y/%m/%d')}/{video_id}-{int(time.time())}.txt"

    settings = get_settings()
    ensure_bucket_exists(settings.minio_documents_bucket)
    upload_bytes(
        bucket_name=settings.minio_documents_bucket,
        object_key=object_key,
        content=content.encode('utf-8'),
        content_type='text/plain; charset=utf-8',
    )

    token = build_download_token(
        bucket_name=settings.minio_documents_bucket,
        object_key=object_key,
        filename=filename,
        content_type='text/plain; charset=utf-8',
    )
    separator = '&' if '?' in download_base_url else '?'
    download_url = f"{download_base_url}{separator}token={quote(token)}"

    return {
        'video_id': video_id,
        'filename': filename,
        'line_count': len(transcript_entries),
        'download_url': download_url,
        'bucket': settings.minio_documents_bucket,
        'object_key': object_key,
    }


def download_transcript_from_token(token: str):
    payload = parse_download_token(token)
    content = download_bytes(payload['bucket_name'], payload['object_key'])
    headers = {'Content-Disposition': f"attachment; filename*=UTF-8''{quote(payload['filename'])}"}
    return StreamingResponse(
        iter([content]),
        media_type=payload.get('content_type') or 'text/plain; charset=utf-8',
        headers=headers,
    )


def _require_api_key_identity(current_identity: dict) -> None:
    if current_identity.get('auth_type') != 'api_key':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='This endpoint requires API key authentication only.')
    if current_identity.get('api_key_scope') != 'chatbot':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='API key does not have chatbot scope.')


def extract_video_id(url: str) -> str:
    for pattern in YOUTUBE_ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid YouTube URL.')


def fetch_transcript(video_id: str) -> list[dict]:
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    available_langs = [lang.language_code for lang in transcript_list]
    if 'en' not in available_langs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='English transcript is not available for this video.')

    transcript = api.fetch(video_id, languages=['en', 'hi'])
    raw_transcript = transcript.to_raw_data()

    result = []
    for entry in raw_transcript:
        start = round(float(entry['start']), 2)
        duration = round(float(entry['duration']), 2)
        end = round(start + duration, 2)
        text = str(entry['text']).strip()
        if not text:
            continue
        result.append({'text': text, 'start': start, 'end': end, 'duration': duration})

    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Transcript is empty for this video.')
    return result


def build_transcript_text(*, video_id: str, youtube_url: str, entries: list[dict]) -> str:
    lines = [
        f'YouTube URL: {youtube_url}',
        f'Video ID: {video_id}',
        f'Transcript lines: {len(entries)}',
        '',
        'Transcript:',
        '',
    ]
    for entry in entries:
        lines.append(f"[{_format_timestamp(entry['start'])} - {_format_timestamp(entry['end'])}] {entry['text']}")
    lines.append('')
    return '\n'.join(lines)


def _format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f'{hours:02d}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'


def build_download_token(*, bucket_name: str, object_key: str, filename: str, content_type: str) -> str:
    settings = get_settings()
    payload = {
        'bucket_name': bucket_name,
        'object_key': object_key,
        'filename': Path(filename).name,
        'content_type': content_type,
        'exp': int(time.time()) + 86400,
    }
    serialized = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    signature = hmac.new(settings.minio_secret_key.encode('utf-8'), serialized, hashlib.sha256).digest()
    return f"{base64.urlsafe_b64encode(serialized).decode('utf-8').rstrip('=')}.{base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')}"


def parse_download_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload_part, signature_part = token.split('.', 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid download token.') from exc

    payload_bytes = _decode_base64url(payload_part)
    signature = _decode_base64url(signature_part)
    expected_signature = hmac.new(settings.minio_secret_key.encode('utf-8'), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Invalid download token signature.')

    payload = json.loads(payload_bytes.decode('utf-8'))
    if int(payload.get('exp', 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='Download link has expired.')
    return payload


def _decode_base64url(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
