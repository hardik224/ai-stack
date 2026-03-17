from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config.settings import get_settings


@contextmanager
def connection() -> Iterator[Any]:
    settings = get_settings()
    with connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


@contextmanager
def transaction() -> Iterator[Any]:
    with connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def fetch_one(query: str, params: tuple | list | None = None, conn=None) -> dict | None:
    active_conn = conn
    if active_conn is None:
        with connection() as local_conn:
            return fetch_one(query=query, params=params, conn=local_conn)

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchone()


def execute(query: str, params: tuple | list | None = None, conn=None) -> None:
    active_conn = conn
    if active_conn is None:
        with transaction() as local_conn:
            execute(query=query, params=params, conn=local_conn)
        return

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())


def to_jsonb(value: Any) -> Jsonb:
    return Jsonb(value or {})
