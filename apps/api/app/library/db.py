from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


_pool: ConnectionPool | None = None


def init_db_pool(database_url: str) -> None:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=10,
            timeout=10,
            kwargs={"row_factory": dict_row},
        )


def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    return _pool


@contextmanager
def connection() -> Iterator[Any]:
    with get_pool().connection() as conn:
        yield conn


@contextmanager
def transaction() -> Iterator[Any]:
    with get_pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def fetch_one(query: str, params: tuple[Any, ...] | list[Any] | None = None, conn: Any | None = None) -> dict[str, Any] | None:
    active_conn = conn
    if active_conn is None:
        with connection() as local_conn:
            return fetch_one(query=query, params=params, conn=local_conn)

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchone()


def fetch_all(query: str, params: tuple[Any, ...] | list[Any] | None = None, conn: Any | None = None) -> list[dict[str, Any]]:
    active_conn = conn
    if active_conn is None:
        with connection() as local_conn:
            return fetch_all(query=query, params=params, conn=local_conn)

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return list(cursor.fetchall())


def execute(query: str, params: tuple[Any, ...] | list[Any] | None = None, conn: Any | None = None) -> None:
    active_conn = conn
    if active_conn is None:
        with transaction() as local_conn:
            execute(query=query, params=params, conn=local_conn)
        return

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())


def execute_returning(
    query: str,
    params: tuple[Any, ...] | list[Any] | None = None,
    conn: Any | None = None,
) -> dict[str, Any] | None:
    active_conn = conn
    if active_conn is None:
        with transaction() as local_conn:
            return execute_returning(query=query, params=params, conn=local_conn)

    with active_conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchone()


def scalar(query: str, params: tuple[Any, ...] | list[Any] | None = None, conn: Any | None = None) -> Any:
    row = fetch_one(query=query, params=params, conn=conn)
    if not row:
        return None
    return next(iter(row.values()))


def to_jsonb(value: Any) -> Jsonb:
    return Jsonb(value or {})
