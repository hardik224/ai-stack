from fastapi import APIRouter, Depends, Query, Request

from app.controllers import utility_controller
from app.middleware.auth import get_current_identity
from app.schemas.utility import YouTubeTranscriptRequest


router = APIRouter(prefix='/utilities', tags=['utilities'])


@router.post('/youtube-transcript')
def create_youtube_transcript(
    payload: YouTubeTranscriptRequest,
    request: Request,
    current_identity: dict = Depends(get_current_identity),
):
    return utility_controller.create_youtube_transcript(
        payload=payload,
        current_identity=current_identity,
        request=request,
    )


@router.get('/youtube-transcript/download', name='download_youtube_transcript')
def download_youtube_transcript(token: str = Query(...)):
    return utility_controller.download_youtube_transcript(token=token)
