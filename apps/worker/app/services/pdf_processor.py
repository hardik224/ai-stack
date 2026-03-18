from io import BytesIO

from pypdf import PdfReader

from app.services.chunking_service import ParsedUnit, normalize_text



def parse_pdf_bytes(content: bytes) -> dict:
    reader = PdfReader(BytesIO(content))
    units: list[ParsedUnit] = []

    for page_index, page in enumerate(reader.pages, start=1):
        extracted_text = page.extract_text() or ''
        normalized = normalize_text(extracted_text)
        if not normalized:
            continue
        units.append(
            ParsedUnit(
                source_type='pdf',
                text=normalized,
                page_number=page_index,
                source_metadata={'page_number': page_index},
            )
        )

    return {
        'source_type': 'pdf',
        'page_count': len(reader.pages),
        'row_count': None,
        'units': units,
    }
