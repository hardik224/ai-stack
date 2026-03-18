from fastapi import APIRouter, Depends

from app.controllers import search_controller
from app.middleware.auth import require_chat_access
from app.schemas.search import SearchRequest


router = APIRouter(tags=['search'])


@router.post('/search')
@router.post('/retrieve')
def search_chunks(
    payload: SearchRequest,
    current_identity: dict = Depends(require_chat_access()),
):
    return search_controller.search_chunks(payload=payload, current_identity=current_identity)
