from app.schemas.search import SearchRequest
from app.services import search_service



def search_chunks(payload: SearchRequest, current_identity: dict):
    return search_service.search_chunks(payload=payload, current_identity=current_identity)
