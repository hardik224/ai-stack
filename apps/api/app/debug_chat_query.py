from __future__ import annotations

import argparse
import json
import sys
import traceback
from textwrap import shorten
from typing import Any
from uuid import UUID

from app.config.settings import get_settings
from app.library.db import close_db_pool, fetch_all, init_db_pool
from app.library.qdrant import close_qdrant_client, init_qdrant_client
from app.library.redis_client import close_redis_client, init_redis_client
from app.services import retrieval_service
from app.services.llm_config_service import ensure_default_llm_config
from app.services.llm_service import get_runtime_llm_config, stream_markdown_answer
from app.services.prompt_service import build_chat_prompt

FIND_FILES_SQL = """
SELECT
    f.id,
    f.collection_id,
    f.uploaded_by,
    f.original_name,
    f.source_type,
    f.created_at,
    c.name AS collection_name,
    u.email AS uploaded_by_email,
    u.role AS uploaded_by_role
FROM files f
LEFT JOIN collections c ON c.id = f.collection_id
LEFT JOIN users u ON u.id = f.uploaded_by
WHERE lower(f.original_name) = lower(%s)
ORDER BY f.created_at DESC;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Debug grounded chat retrieval and live LLM streaming for a specific uploaded file.')
    parser.add_argument('--file-name', default='API Documentation.pdf', help='Indexed file original_name to debug against.')
    parser.add_argument('--question', default='what is Get_data_frame_from_image?', help='Question to ask against the indexed file.')
    parser.add_argument('--top-k', type=int, default=5, help='Top K retrieval size.')
    parser.add_argument('--max-preview-chars', type=int, default=220, help='Preview length for retrieved chunks.')
    return parser.parse_args()


def print_header(title: str) -> None:
    print(f"\n{'=' * 24} {title} {'=' * 24}")


def print_json(label: str, payload: Any) -> None:
    print(f"{label}:\n{json.dumps(payload, indent=2, default=str, ensure_ascii=False)}")


def preview(text: str, width: int) -> str:
    return shorten(' '.join((text or '').split()), width=width, placeholder=' ...')


def select_file(file_name: str) -> dict[str, Any]:
    rows = fetch_all(FIND_FILES_SQL, (file_name,))
    if not rows:
        raise SystemExit(f"No indexed file found with original_name='{file_name}'.")
    if len(rows) > 1:
        print(f"Found {len(rows)} matching files. Using the most recent one: {rows[0]['id']}")
    return rows[0]


def build_identity(file_row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': str(file_row['uploaded_by']),
        'role': file_row.get('uploaded_by_role') or 'internal_user',
        'auth_type': 'debug_script',
        'email': file_row.get('uploaded_by_email'),
    }


def run_retrieval(
    label: str,
    *,
    question: str,
    identity: dict[str, Any],
    collection_id: str | None,
    file_id: str | None,
    top_k: int,
    max_preview_chars: int,
) -> dict[str, Any]:
    print_header(f'{label} retrieval')
    result = retrieval_service.retrieve_chunks(
        query=question,
        current_identity=identity,
        collection_id=UUID(collection_id) if collection_id else None,
        file_id=UUID(file_id) if file_id else None,
        top_k=top_k,
        persist_trace=False,
        debug=True,
    )
    print_json('Evidence assessment', result.get('evidence_assessment', {}))
    print_json('Timings', result.get('timings', {}))
    print_json('Cache', result.get('cache', {}))
    print_json('Debug', result.get('debug', {}))
    print(f"Selected items: {result.get('selected_count', 0)} / Candidates: {result.get('candidate_count', 0)}")
    for item in result.get('items', []):
        loc = []
        if item.get('page_number'):
            loc.append(f"page {item['page_number']}")
        if item.get('row_number'):
            loc.append(f"row {item['row_number']}")
        location = ', '.join(loc) if loc else 'location unavailable'
        print(
            f"- [{item.get('citation_label')}] {item.get('filename')} | score={item.get('score')} | rerank={item.get('rerank_score')} | {location}\n"
            f"  preview: {preview(item.get('text', ''), max_preview_chars)}"
        )
    return result


def run_llm_probe(question: str, retrieval_result: dict[str, Any]) -> None:
    print_header('Runtime LLM config')
    runtime = get_runtime_llm_config()
    print_json(
        'Active runtime config',
        {
            'name': runtime.name,
            'provider': runtime.provider,
            'model': runtime.model,
            'base_url': runtime.base_url,
            'timeout_seconds': runtime.timeout_seconds,
            'max_output_tokens': runtime.max_output_tokens,
            'temperature': runtime.temperature,
            'top_p': runtime.top_p,
            'reasoning_effort': runtime.reasoning_effort,
            'source': runtime.source,
            'has_api_key': bool(runtime.api_key),
            'api_key_prefix': runtime.api_key[:6] if runtime.api_key else None,
        },
    )

    prompt_messages = build_chat_prompt(
        question=question,
        context_items=retrieval_result.get('items', []),
        history_messages=[],
        mode='knowledge_qa',
    )
    print_header('Prompt preview')
    prompt_text = prompt_messages[-1]['content']
    print(prompt_text[:2500])
    if len(prompt_text) > 2500:
        print('...<truncated>...')

    print_header('Live stream probe')
    generated: list[str] = []
    chunk_count = 0
    try:
        for delta in stream_markdown_answer(prompt_messages, mode='knowledge_qa', runtime_config=runtime):
            chunk_count += 1
            generated.append(delta)
            sys.stdout.write(delta)
            sys.stdout.flush()
        print('\n')
        print_json(
            'Stream summary',
            {
                'chunk_count': chunk_count,
                'output_chars': len(''.join(generated)),
            },
        )
    except Exception as exc:
        print('\n')
        print_json(
            'LLM exception',
            {
                'type': type(exc).__name__,
                'message': str(exc),
                'repr': repr(exc),
            },
        )
        print('Traceback:')
        traceback.print_exc()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    init_db_pool(settings.database_url)
    init_redis_client(settings.redis_url)
    init_qdrant_client(settings)
    ensure_default_llm_config(settings=settings)

    try:
        print_header('Target file')
        file_row = select_file(args.file_name)
        print_json('Indexed file', file_row)
        identity = build_identity(file_row)
        print_json('Debug identity', identity)

        run_retrieval(
            'Global',
            question=args.question,
            identity=identity,
            collection_id=None,
            file_id=None,
            top_k=args.top_k,
            max_preview_chars=args.max_preview_chars,
        )
        scoped = run_retrieval(
            'File-scoped',
            question=args.question,
            identity=identity,
            collection_id=str(file_row['collection_id']) if file_row.get('collection_id') else None,
            file_id=str(file_row['id']),
            top_k=args.top_k,
            max_preview_chars=args.max_preview_chars,
        )
        run_llm_probe(args.question, scoped)
    finally:
        close_qdrant_client()
        close_redis_client()
        close_db_pool()


if __name__ == '__main__':
    main()
