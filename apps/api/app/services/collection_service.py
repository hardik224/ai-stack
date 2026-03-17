from fastapi import HTTPException, status

from app.library.security import slugify
from app.models import collection_model
from app.services.activity_service import record_activity


def create_collection(*, payload, current_user: dict) -> dict:
    slug = payload.slug or slugify(payload.name)
    existing = collection_model.get_collection_by_slug(slug)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection slug already exists.")

    collection = collection_model.create_collection(
        name=payload.name,
        slug=slug,
        description=payload.description,
        visibility=payload.visibility,
        metadata={"created_from": "portal"},
        created_by=current_user["id"],
    )
    record_activity(
        actor_user_id=current_user["id"],
        activity_type="collection.created",
        target_type="collection",
        target_id=collection["id"] if collection else None,
        description=f"Collection '{payload.name}' created.",
        visibility="foreground",
        metadata={"slug": slug},
    )
    return collection


def list_collections(*, current_user: dict) -> dict:
    return {"items": collection_model.list_collections(), "viewer_role": current_user["role"]}
