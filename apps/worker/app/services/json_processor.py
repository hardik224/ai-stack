from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.config.settings import get_settings
from app.services.chunking_service import ParsedUnit, normalize_text


IDENTIFIER_KEYS = ('id', 'key', 'code', 'slug', 'video_id')
YOUTUBE_DETECT_FIELDS = {'video_id', 'title', 'url', 'paragraphs'}
PUNCTUATION_RE = re.compile(r'\s+([,.;:!...])')
MULTISPACE_RE = re.compile(r'\s{2,}')


def detect_json_knowledge_type(payload: Any) -> str:
    if isinstance(payload, dict) and YOUTUBE_DETECT_FIELDS.issubset(payload.keys()) and isinstance(payload.get('paragraphs'), list):
        return 'youtube_transcript'
    return 'generic_json'



def parse_json_bytes(content: bytes) -> dict:
    decoded = content.decode('utf-8-sig', errors='replace')
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON file: {exc.msg} at line {exc.lineno}, column {exc.colno}.') from exc

    knowledge_type = detect_json_knowledge_type(payload)
    if knowledge_type == 'youtube_transcript':
        return extract_youtube_transcript_chunks(payload)
    return extract_generic_json_chunks(payload)



def extract_generic_json_chunks(payload: Any, options: dict | None = None) -> dict:
    settings = get_settings()
    max_chars = max(getattr(settings, 'json_generic_summary_max_chars', 1600), 400)
    document_title = _extract_document_title(payload) or 'JSON document'
    units: list[ParsedUnit] = []
    sequence = 0

    def append_unit(*, text: str, json_path: str, node_type: str, metadata: dict | None = None) -> None:
        nonlocal sequence
        normalized = normalize_text(text)
        if not normalized:
            return
        sequence += 1
        unit_metadata = {
            'knowledge_type': 'generic_json',
            'json_path': json_path,
            'node_type': node_type,
            'document_title': document_title,
        }
        if metadata:
            unit_metadata.update(metadata)
        units.append(
            ParsedUnit(
                source_type='json',
                text=normalized,
                row_number=sequence,
                source_metadata=unit_metadata,
            )
        )

    def walk(node: Any, path: str, inherited_title: str | None = None, inherited_identifiers: dict[str, Any] | None = None) -> None:
        inherited_identifiers = dict(inherited_identifiers or {})
        if isinstance(node, dict):
            current_title = _extract_document_title(node) or inherited_title or document_title
            identifiers = {**inherited_identifiers, **_extract_identifiers(node)}
            scalar_pairs: list[tuple[str, str]] = []
            for key, value in node.items():
                if _is_meaningful_scalar(value):
                    scalar_text = _scalar_to_text(value)
                    if scalar_text:
                        scalar_pairs.append((str(key), scalar_text))
            if scalar_pairs:
                parts = []
                if current_title:
                    parts.append(f'Title: {current_title}')
                for key, value in scalar_pairs:
                    parts.append(f'{_humanize_key(key)}: {value}')
                append_unit(
                    text=(' | '.join(parts))[:max_chars],
                    json_path=path,
                    node_type='object',
                    metadata={
                        'entity_identifiers': identifiers or None,
                        'field_names': [key for key, _ in scalar_pairs],
                    },
                )
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    walk(value, f'{path}.{key}', current_title, identifiers)
            return

        if isinstance(node, list):
            if node and all(_is_meaningful_scalar(item) for item in node):
                values = [_scalar_to_text(item) for item in node]
                values = [value for value in values if value]
                if values:
                    append_unit(
                        text=f'{document_title} | {_path_label(path)}: ' + ' | '.join(values),
                        json_path=path,
                        node_type='array',
                        metadata={'item_count': len(values)},
                    )
                return
            for index, item in enumerate(node):
                walk(item, f'{path}[{index}]', inherited_title, inherited_identifiers)
            return

        if _is_meaningful_scalar(node):
            scalar_text = _scalar_to_text(node)
            if scalar_text:
                append_unit(
                    text=f'{document_title} | {_path_label(path)}: {scalar_text}',
                    json_path=path,
                    node_type='scalar',
                )

    walk(payload, '$')

    return {
        'source_type': 'json',
        'page_count': None,
        'row_count': len(units),
        'units': units,
        'file_metadata': {
            'knowledge_type': 'generic_json',
            'document_title': document_title,
            'unit_count': len(units),
        },
    }



def extract_youtube_transcript_chunks(payload: dict[str, Any], options: dict | None = None) -> dict:
    settings = get_settings()
    paragraphs = payload.get('paragraphs') or []
    video_id = str(payload.get('video_id') or '').strip()
    title = str(payload.get('title') or 'Untitled video').strip()
    url = str(payload.get('url') or '').strip()
    transcript_language = str(payload.get('transcript_language') or '').strip() or None
    translated_to_english = bool(payload.get('translated_to_english'))
    source = str(payload.get('source') or '').strip() or None
    thumbnail_url = str(payload.get('thumbnail_url') or build_youtube_thumbnail(video_id)).strip()

    normalized_segments: list[dict[str, Any]] = []
    for index, paragraph in enumerate(paragraphs):
        if not isinstance(paragraph, dict):
            continue
        text = cleanup_transcript_text(str(paragraph.get('text') or ''))
        if not text:
            continue
        start = _coerce_seconds(paragraph.get('start'))
        end = _coerce_seconds(paragraph.get('end'))
        if end is None and start is not None:
            duration = _coerce_seconds(paragraph.get('duration')) or 0.0
            end = round(start + duration, 2)
        if start is None:
            start = 0.0
        if end is None:
            end = start
        normalized_segments.append(
            {
                'index': index,
                'start': start,
                'end': end,
                'text': text,
                'raw_text': str(paragraph.get('text') or '').strip(),
                'segment_label': f'{format_timestamp(start)} - {format_timestamp(end)}',
                'deep_link_url': build_youtube_deep_link(url, start),
            }
        )

    total_duration = max((segment['end'] for segment in normalized_segments), default=0.0)
    full_text = cleanup_transcript_text(str(payload.get('full_text_for_llm') or ''))
    if not full_text:
        full_text = '\n\n'.join(segment['text'] for segment in normalized_segments)

    common_metadata = {
        'knowledge_type': 'youtube_transcript',
        'video_id': video_id,
        'document_title': title,
        'title': title,
        'url': url,
        'transcript_language': transcript_language,
        'translated_to_english': translated_to_english,
        'source': source,
        'thumbnail_url': thumbnail_url,
        'total_duration': total_duration,
    }

    units: list[ParsedUnit] = []
    sequence = 0

    def append_unit(*, text: str, metadata: dict[str, Any]) -> None:
        nonlocal sequence
        normalized = normalize_text(text)
        if not normalized:
            return
        sequence += 1
        units.append(
            ParsedUnit(
                source_type='json',
                text=normalized,
                row_number=sequence,
                source_metadata=metadata,
            )
        )

    if full_text:
        append_unit(
            text=(
                f'Video title: {title}\n'
                f'Video URL: {url}\n'
                'Transcript summary:\n'
                f'{full_text}'
            ),
            metadata={
                **common_metadata,
                'json_path': '$.full_text_for_llm',
                'chunk_type': 'youtube_video',
                'deep_link_url': url,
                'timestamp_label': f'00:00 - {format_timestamp(total_duration)}' if total_duration else None,
            },
        )

    for segment in normalized_segments:
        append_unit(
            text=(
                f'Video title: {title}\n'
                f'Relevant segment: {segment["segment_label"]}\n'
                'Transcript excerpt:\n'
                f'{segment["text"]}'
            ),
            metadata={
                **common_metadata,
                'json_path': f'$.paragraphs[{segment["index"]}]',
                'chunk_type': 'youtube_segment',
                'paragraph_index': segment['index'],
                'start': segment['start'],
                'end': segment['end'],
                'timestamp_label': segment['segment_label'],
                'segment_label': segment['segment_label'],
                'deep_link_url': segment['deep_link_url'],
                'raw_text': segment['raw_text'],
                'clean_text': segment['text'],
                'snippet': _truncate_text(segment['text'], 180),
            },
        )

    window_size = max(getattr(settings, 'youtube_window_size', 3), 2)
    overlap = max(min(getattr(settings, 'youtube_window_overlap', 1), window_size - 1), 0)
    step = max(window_size - overlap, 1)
    for start_index in range(0, len(normalized_segments), step):
        window = normalized_segments[start_index:start_index + window_size]
        if len(window) < 2:
            continue
        window_start = window[0]['start']
        window_end = window[-1]['end']
        window_text = '\n'.join(segment['text'] for segment in window)
        append_unit(
            text=(
                f'Video title: {title}\n'
                f'Window segment: {format_timestamp(window_start)} - {format_timestamp(window_end)}\n'
                'Transcript excerpt:\n'
                f'{window_text}'
            ),
            metadata={
                **common_metadata,
                'json_path': f'$.paragraphs[{window[0]["index"]}:{window[-1]["index"]}]',
                'chunk_type': 'youtube_window',
                'paragraph_start_index': window[0]['index'],
                'paragraph_end_index': window[-1]['index'],
                'start': window_start,
                'end': window_end,
                'timestamp_label': f'{format_timestamp(window_start)} - {format_timestamp(window_end)}',
                'segment_label': f'{format_timestamp(window_start)} - {format_timestamp(window_end)}',
                'deep_link_url': build_youtube_deep_link(url, window_start),
                'snippet': _truncate_text(window_text, 220),
            },
        )

    return {
        'source_type': 'json',
        'page_count': None,
        'row_count': len(normalized_segments),
        'units': units,
        'file_metadata': {
            **common_metadata,
            'paragraph_count': len(normalized_segments),
            'unit_count': len(units),
        },
    }



def build_youtube_deep_link(url: str, start_seconds: float | int | None) -> str:
    if not url:
        return ''
    start = int(float(start_seconds or 0))
    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if start > 0:
        query['t'] = str(start)
    else:
        query.pop('t', None)
    return urlunparse(parsed._replace(query=urlencode(query)))



def build_youtube_thumbnail(video_id: str) -> str:
    if not video_id:
        return ''
    return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'



def format_timestamp(seconds: float | int | None) -> str:
    total_seconds = max(int(float(seconds or 0)), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f'{hours:02d}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'



def cleanup_transcript_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = MULTISPACE_RE.sub(' ', normalized)
    normalized = PUNCTUATION_RE.sub(r'\1', normalized)
    return normalized.strip()



def _extract_document_title(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ('title', 'name', 'heading', 'label', 'subject'):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None



def _extract_identifiers(payload: dict[str, Any]) -> dict[str, Any]:
    identifiers = {}
    for key in IDENTIFIER_KEYS:
        value = payload.get(key)
        if _is_meaningful_scalar(value):
            identifiers[key] = value
    return identifiers



def _humanize_key(key: str) -> str:
    return str(key).replace('_', ' ').replace('-', ' ').strip().title()



def _path_label(path: str) -> str:
    return path.replace('$.', '').replace('$', 'root')



def _is_meaningful_scalar(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, (int, float, bool))



def _scalar_to_text(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(round(value, 4))
    return str(value).strip()



def _coerce_seconds(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None



def _truncate_text(text: str, limit: int) -> str:
    normalized = cleanup_transcript_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 1, 0)].rstrip() + '...' 
