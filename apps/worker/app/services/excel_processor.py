from io import BytesIO

import pandas as pd

from app.services.chunking_service import ParsedUnit, normalize_text


def parse_excel_bytes(content: bytes) -> dict:
    workbook = pd.read_excel(BytesIO(content), sheet_name=None, dtype=str)

    units: list[ParsedUnit] = []
    row_count = 0
    sheet_names: list[str] = []

    for sheet_name, frame in workbook.items():
        sheet_names.append(str(sheet_name))
        prepared = frame.fillna('')
        normalized_headers = [str(column).strip() or f'column_{index + 1}' for index, column in enumerate(prepared.columns)]

        for sheet_row_number, row in enumerate(prepared.itertuples(index=False, name=None), start=1):
            row_pairs = []
            for index, value in enumerate(row):
                cell_value = str(value).strip()
                if not cell_value:
                    continue
                header = normalized_headers[index] if index < len(normalized_headers) else f'column_{index + 1}'
                row_pairs.append(f'{header}: {cell_value}')

            row_text = normalize_text(' | '.join(row_pairs))
            if not row_text:
                continue

            row_count += 1
            units.append(
                ParsedUnit(
                    source_type='excel',
                    text=f'Sheet: {sheet_name} | {row_text}',
                    row_number=row_count,
                    source_metadata={
                        'row_number': row_count,
                        'sheet_name': str(sheet_name),
                        'sheet_row_number': sheet_row_number,
                        'columns': normalized_headers,
                    },
                )
            )

    return {
        'source_type': 'excel',
        'page_count': None,
        'row_count': row_count,
        'sheet_count': len(sheet_names),
        'sheet_names': sheet_names,
        'units': units,
    }
