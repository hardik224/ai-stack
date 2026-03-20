from __future__ import annotations

import os
from pathlib import Path

from psycopg import connect


def main() -> None:
    database_url = os.getenv('DATABASE_URL', '').strip()
    if not database_url:
        raise RuntimeError('DATABASE_URL is required.')

    sql_dir = Path(__file__).resolve().parents[1] / 'apps' / 'api' / 'app' / 'sql'
    sql_files = sorted(sql_dir.glob('*.sql'))
    if not sql_files:
        raise RuntimeError(f'No SQL files found in {sql_dir}.')

    with connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cursor:
            for sql_file in sql_files:
                print(f'Applying {sql_file.name}')
                cursor.execute(sql_file.read_text(encoding='utf-8'))
        conn.commit()

    print('SQL migrations applied successfully.')


if __name__ == '__main__':
    main()
