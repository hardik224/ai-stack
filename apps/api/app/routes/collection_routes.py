from fastapi import APIRouter, Depends

from app.controllers import collection_controller
from app.middleware.auth import get_current_user, require_roles
from app.schemas.collection import CollectionCreateRequest


router = APIRouter(tags=["collections"])


@router.post("/collections")
def create_collection(
    payload: CollectionCreateRequest,
    current_user: dict = Depends(require_roles("admin", "internal_user")),
):
    return collection_controller.create_collection(payload=payload, current_user=current_user)


@router.get("/collections")
def list_collections(current_user: dict = Depends(get_current_user)):
    return collection_controller.list_collections(current_user=current_user)
