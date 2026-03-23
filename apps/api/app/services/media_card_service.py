from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.config.settings import get_settings


YOUTUBE_CHUNK_TYPES = {'youtube_segment', 'youtube_window', 'youtube_video'}



def choose_media_suggestions(items: list[dict[str, Any]], *, question: str | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.media_cards_enabled:
        return []

    youtube_items = [item for item in items if _is_youtube_item(item)]
    if not youtube_items:
        return []

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in youtube_items:
        grouped[str(item['source_metadata'].get('video_id'))].append(item)

    ranked_groups = sorted(
        grouped.values(),
        key=lambda group: max(_item_score(item) for item in group),
        reverse=True,
    )
    if not ranked_groups:
        return []

    best_group = ranked_groups[0]
    best_score = max(_item_score(item) for item in best_group)
    if best_score < settings.youtube_card_min_score:
        return []

    segment_items = [item for item in best_group if item['source_metadata'].get('chunk_type') in {'youtube_segment', 'youtube_window'} and item['source_metadata'].get('start') is not None]
    video_item = next((item for item in best_group if item['source_metadata'].get('chunk_type') == 'youtube_video'), None)

    if segment_items:
        ordered_segments = sorted(segment_items, key=lambda item: _item_score(item), reverse=True)
        top_segment = ordered_segments[0]
        nearby_segments = [top_segment]
        for candidate in ordered_segments[1:]:
            if len(nearby_segments) >= 3:
                break
            if _segments_are_related(top_segment, candidate):
                nearby_segments.append(candidate)

        span_start = min(float(item['source_metadata'].get('start') or 0.0) for item in nearby_segments)
        span_end = max(float(item['source_metadata'].get('end') or span_start) for item in nearby_segments)
        span_seconds = max(int(span_end - span_start), 0)
        if span_seconds <= settings.youtube_segment_max_span_seconds:
            top_meta = top_segment['source_metadata']
            title = top_meta.get('title') or top_meta.get('document_title') or top_segment.get('filename') or 'Video reference'
            return [
                {
                    'type': 'youtube_segment',
                    'video_id': top_meta.get('video_id'),
                    'title': title,
                    'url': top_meta.get('url'),
                    'deep_link_url': build_youtube_deep_link(str(top_meta.get('url') or ''), span_start),
                    'thumbnail_url': top_meta.get('thumbnail_url') or build_youtube_thumbnail(str(top_meta.get('video_id') or '')),
                    'start': span_start,
                    'end': span_end,
                    'timestamp_label': format_timestamp_label(span_start, span_end),
                    'subtitle': _build_reason_snippet(nearby_segments),
                    'reason': 'Relevant answer found in this video segment.',
                    'transcript_language': top_meta.get('transcript_language'),
                }
            ]

    preferred = video_item or max(best_group, key=_item_score)
    meta = preferred.get('source_metadata', {})
    title = meta.get('title') or meta.get('document_title') or preferred.get('filename') or 'Video reference'
    return [
        {
            'type': 'youtube_video',
            'video_id': meta.get('video_id'),
            'title': title,
            'url': meta.get('url') or meta.get('deep_link_url'),
            'thumbnail_url': meta.get('thumbnail_url') or build_youtube_thumbnail(str(meta.get('video_id') or '')),
            'subtitle': _build_reason_snippet(best_group[:2]),
            'reason': 'This video appears broadly relevant to the answer.',
            'transcript_language': meta.get('transcript_language'),
        }
    ]



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



def format_timestamp_label(start: float | int | None, end: float | int | None) -> str:
    return f'{format_timestamp(start)} - {format_timestamp(end)}'



def _item_score(item: dict[str, Any]) -> float:
    return float(item.get('rerank_score') or item.get('fused_score') or item.get('vector_score') or item.get('score') or 0.0)



def _is_youtube_item(item: dict[str, Any]) -> bool:
    metadata = item.get('source_metadata') or {}
    return item.get('source_type') == 'json' and metadata.get('knowledge_type') == 'youtube_transcript' and metadata.get('chunk_type') in YOUTUBE_CHUNK_TYPES



def _segments_are_related(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_meta = first.get('source_metadata') or {}
    second_meta = second.get('source_metadata') or {}
    if first_meta.get('video_id') != second_meta.get('video_id'):
        return False
    first_start = float(first_meta.get('start') or 0.0)
    first_end = float(first_meta.get('end') or first_start)
    second_start = float(second_meta.get('start') or 0.0)
    second_end = float(second_meta.get('end') or second_start)
    return abs(first_start - second_start) <= 120 or abs(first_end - second_end) <= 120 or (second_start <= first_end and second_end >= first_start)



def _build_reason_snippet(items: list[dict[str, Any]]) -> str:
    for item in items:
        metadata = item.get('source_metadata') or {}
        snippet = str(metadata.get('snippet') or '').strip()
        if snippet:
            return snippet
        text = str(item.get('text') or '').strip()
        if text:
            return text[:180].strip() + ('...'  if len(text) > 180 else '')
    return 'Relevant transcript evidence is available.'
