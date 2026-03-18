from collections.abc import Iterator, Sequence
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


def fetch_all(query: str, params: tuple | list | None = None, conn=None) -> list[dict]:
    active_conn = conn
    if active_conn is None:
        with connection() as local_conn:
            return fetch_all(query=query, params=params, conn=local_conn)

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return list(cursor.fetchall())


def execute(query: str, params: tuple | list | None = None, conn=None) -> None:
    active_conn = conn
    if active_conn is None:
        with transaction() as local_conn:
            execute(query=query, params=params, conn=local_conn)
        return

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())


def executemany(query: str, params_seq: Sequence[tuple | list], conn=None) -> None:
    if not params_seq:
        return

    active_conn = conn
    if active_conn is None:
        with transaction() as local_conn:
            executemany(query=query, params_seq=params_seq, conn=local_conn)
        return

    with active_conn.cursor() as cursor:
        cursor.executemany(query, params_seq)


def execute_returning(query: str, params: tuple | list | None = None, conn=None) -> dict | None:
    active_conn = conn
    if active_conn is None:
        with transaction() as local_conn:
            return execute_returning(query=query, params=params, conn=local_conn)

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchone()


def to_jsonb(value: Any) -> Jsonb:
    return Jsonb(value or {})
