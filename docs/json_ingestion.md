# JSON Knowledge Ingestion

This stack now supports dynamic JSON knowledge uploads alongside PDF, CSV, Excel, and TXT files.

## Supported behavior

- Portal uploads can now include `.json` files.
- Upload validation rejects invalid JSON early with a clear `400` response.
- Original JSON files are still stored in MinIO like other uploaded knowledge files.
- Worker ingestion detects JSON and routes it through a JSON-aware parser.

## Dynamic JSON ingestion

The worker uses two paths:

1. Generic JSON handler
- Accepts any valid object or array.
- Walks nested structures recursively.
- Extracts meaningful scalar values and compact text summaries.
- Preserves metadata like `json_path`, `document_title`, and discovered identifiers.

2. YouTube transcript JSON handler
- Detects transcript-shaped JSON using fields like `video_id`, `title`, `url`, and `paragraphs`.
- Produces:
  - one video-level retrieval unit
  - paragraph-level segment units
  - merged rolling-window units for broader semantic recall
- Preserves video metadata such as title, URL, thumbnail, timestamps, and deep links.

## Retrieval behavior

JSON chunks reuse the existing embedding, Qdrant, keyword retrieval, fusion, and reranking pipeline.

YouTube transcript chunks are enriched so retrieval can:
- hit exact paragraph segments for narrow questions
- hit merged windows for broader conceptual questions
- carry timestamp metadata into grounded context and citations

## Media suggestion logic

The backend can add optional `media_suggestions` to retrieval and chat responses.

Current supported card types:
- `youtube_video`
- `youtube_segment`

Heuristics:
- narrow, high-confidence transcript hits prefer `youtube_segment`
- broader, multi-segment evidence can prefer `youtube_video`
- weak evidence returns no card

## Prompt/context behavior

Existing answer style and fine-tuned response pipeline are unchanged.

Only the grounding context builder is enriched for YouTube transcript JSON so the model sees:
- video title
- video URL
- relevant timestamp range
- cleaned transcript excerpt

This keeps the answer human-readable without exposing raw JSON structure.

## Config flags

API:
- `MEDIA_CARDS_ENABLED=true`
- `YOUTUBE_CARD_MIN_SCORE=0.45`
- `YOUTUBE_SEGMENT_MAX_SPAN_SECONDS=240`

Worker:
- `JSON_GENERIC_SUMMARY_MAX_CHARS=1600`
- `YOUTUBE_WINDOW_SIZE=3`
- `YOUTUBE_WINDOW_OVERLAP=1`

## Migration

Run:

```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5432 -U postgres -d ai_stack -f apps/api/app/sql/010_json_support.sql
```

## Validation

Compile checks:

```bash
python -m compileall apps/api apps/worker
```

JSON regression script:

```bash
python scripts/test_json_knowledge.py
```
