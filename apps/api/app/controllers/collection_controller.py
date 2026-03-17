from app.schemas.collection import CollectionCreateRequest
from app.services import collection_service


def create_collection(payload: CollectionCreateRequest, current_user: dict):
    return collection_service.create_collection(payload=payload, current_user=current_user)


def list_collections(current_user: dict):
    return collection_service.list_collections(current_user=current_user)
