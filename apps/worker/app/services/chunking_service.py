import hashlib
import re
from dataclasses import asdict, dataclass

from app.config.settings import get_settings


WHITESPACE_RE = re.compile(r'\s+')


@dataclass(slots=True)
class ParsedUnit:
    source_type: str
    text: str
    page_number: int | None = None
    row_number: int | None = None
    source_metadata: dict | None = None


@dataclass(slots=True)
class ChunkRecord:
    chunk_index: int
    content: str
    token_count: int
    content_hash: str
    source_type: str
    page_number: int | None
    row_number: int | None
    source_metadata: dict


def chunk_parsed_units(units: list[ParsedUnit]) -> list[ChunkRecord]:
    settings = get_settings()
    chunk_size = max(settings.chunk_size_chars, 200)
    overlap = max(min(settings.chunk_overlap_chars, chunk_size // 2), 0)
    chunks: list[ChunkRecord] = []

    for unit in units:
        normalized_text = normalize_text(unit.text)
        if not normalized_text:
            continue

        chunk_texts = split_text(normalized_text, chunk_size=chunk_size, overlap=overlap)
        for content in chunk_texts:
            chunks.append(
                ChunkRecord(
                    chunk_index=len(chunks),
                    content=content,
                    token_count=estimate_token_count(content),
                    content_hash=hashlib.sha256(content.encode('utf-8')).hexdigest(),
                    source_type=unit.source_type,
                    page_number=unit.page_number,
                    row_number=unit.row_number,
                    source_metadata=unit.source_metadata or {},
                )
            )

    return chunks


def normalize_text(text: str) -> str:
    if not text:
        return ''

    text = text.replace('\x00', ' ')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.split('\n')]
    compact = '\n'.join(line for line in lines if line)
    return compact.strip()


def split_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    text_length = len(text)
    minimum_breakpoint = max(chunk_size // 2, 1)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        if end < text_length:
            breakpoint = _find_breakpoint(text, start, end, minimum_breakpoint)
            if breakpoint > start:
                end = breakpoint

        candidate = text[start:end].strip()
        if candidate:
            chunks.append(candidate)

        if end >= text_length:
            break

        next_start = max(end - overlap, start + 1)
        start = next_start

    return chunks


def _find_breakpoint(text: str, start: int, end: int, minimum_breakpoint: int) -> int:
    for marker in ('\n\n', '\n', '. ', '; ', ', ', ' '):
        breakpoint = text.rfind(marker, start + minimum_breakpoint, end)
        if breakpoint != -1:
            return breakpoint + len(marker.strip())
    return end


def estimate_token_count(text: str) -> int:
    return len(WHITESPACE_RE.findall(text)) + 1 if text else 0


def chunk_to_dict(chunk: ChunkRecord) -> dict:
    return asdict(chunk)
