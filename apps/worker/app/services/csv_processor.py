import csv
from io import StringIO

from app.services.chunking_service import ParsedUnit, normalize_text



def parse_csv_bytes(content: bytes) -> dict:
    decoded = content.decode('utf-8-sig', errors='replace')
    reader = csv.reader(StringIO(decoded, newline=''))

    try:
        headers = next(reader)
    except StopIteration:
        headers = []

    normalized_headers = [header.strip() or f'column_{index + 1}' for index, header in enumerate(headers)]
    units: list[ParsedUnit] = []
    row_count = 0

    for row_number, row in enumerate(reader, start=1):
        if not any(str(value).strip() for value in row):
            continue

        row_count += 1
        row_pairs = []
        for index, value in enumerate(row):
            header = normalized_headers[index] if index < len(normalized_headers) else f'column_{index + 1}'
            cell_value = str(value).strip()
            if cell_value:
                row_pairs.append(f'{header}: {cell_value}')

        row_text = normalize_text(' | '.join(row_pairs))
        if not row_text:
            continue

        units.append(
            ParsedUnit(
                source_type='csv',
                text=row_text,
                row_number=row_count,
                source_metadata={
                    'row_number': row_count,
                    'columns': normalized_headers,
                },
            )
        )

    return {
        'source_type': 'csv',
        'page_count': None,
        'row_count': row_count,
        'headers': normalized_headers,
        'units': units,
    }
