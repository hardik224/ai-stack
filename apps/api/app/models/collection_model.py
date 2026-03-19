from uuid import UUID

from app.library.db import execute_returning, fetch_all, fetch_one, to_jsonb


INSERT_COLLECTION = """
INSERT INTO collections (
    name,
    slug,
    description,
    visibility,
    metadata,
    created_by
)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id, name, slug, description, visibility, metadata, created_by, created_at;
"""

GET_COLLECTION = """
SELECT
    c.id,
    c.name,
    c.slug,
    c.description,
    c.visibility,
    c.metadata,
    c.created_by,
    c.created_at,
    c.updated_at,
    COALESCE(f.file_count, 0) AS file_count
FROM collections c
LEFT JOIN (
    SELECT collection_id, COUNT(*) AS file_count
    FROM files
    GROUP BY collection_id
) f ON f.collection_id = c.id
WHERE c.id = %s AND c.is_active = TRUE;
"""

GET_COLLECTION_BY_SLUG = """
SELECT id, name, slug, description, visibility, metadata, created_by, created_at
FROM collections
WHERE slug = %s;
"""

LIST_COLLECTIONS = """
SELECT
    c.id,
    c.name,
    c.slug,
    c.description,
    c.visibility,
    c.metadata,
    c.created_by,
    c.created_at,
    c.updated_at,
    COALESCE(f.file_count, 0) AS file_count
FROM collections c
LEFT JOIN (
    SELECT collection_id, COUNT(*) AS file_count
    FROM files
    GROUP BY collection_id
) f ON f.collection_id = c.id
WHERE c.is_active = TRUE
ORDER BY c.created_at DESC;
"""

UPSERT_COLLECTION_BY_SLUG = """
INSERT INTO collections (
    name,
    slug,
    description,
    visibility,
    metadata,
    created_by
)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    visibility = EXCLUDED.visibility,
    metadata = collections.metadata || EXCLUDED.metadata,
    is_active = TRUE
RETURNING id, name, slug, description, visibility, metadata, created_by, created_at, updated_at;
"""


def create_collection(
    *,
    name: str,
    slug: str,
    description: str | None,
    visibility: str,
    metadata: dict | None,
    created_by: UUID,
) -> dict | None:
    return execute_returning(
        INSERT_COLLECTION,
        (name, slug, description, visibility, to_jsonb(metadata), str(created_by)),
    )


def get_collection(collection_id: UUID) -> dict | None:
    return fetch_one(GET_COLLECTION, (str(collection_id),))


def get_collection_by_slug(slug: str) -> dict | None:
    return fetch_one(GET_COLLECTION_BY_SLUG, (slug,))


def list_collections() -> list[dict]:
    return fetch_all(LIST_COLLECTIONS)



def upsert_collection_by_slug(
    *,
    name: str,
    slug: str,
    description: str | None,
    visibility: str,
    metadata: dict | None,
    created_by: UUID,
    conn=None,
) -> dict | None:
    return execute_returning(
        UPSERT_COLLECTION_BY_SLUG,
        (name, slug, description, visibility, to_jsonb(metadata), str(created_by)),
        conn=conn,
    )
