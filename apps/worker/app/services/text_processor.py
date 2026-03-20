from app.services.chunking_service import ParsedUnit, normalize_text


def parse_text_bytes(content: bytes) -> dict:
    decoded = content.decode('utf-8-sig', errors='replace')
    normalized = normalize_text(decoded)

    units: list[ParsedUnit] = []
    if normalized:
        units.append(
            ParsedUnit(
                source_type='txt',
                text=normalized,
                source_metadata={'encoding': 'utf-8-sig'},
            )
        )

    return {
        'source_type': 'txt',
        'page_count': None,
        'row_count': 1 if units else 0,
        'units': units,
    }
