from fastapi import Request

from app.config.settings import get_settings
from app.services import youtube_transcript_service


def create_youtube_transcript(payload, current_identity: dict, request: Request):
    download_base_url = _resolve_download_base_url(request)
    return youtube_transcript_service.create_transcript_file(
        youtube_url=str(payload.youtube_url),
        current_identity=current_identity,
        download_base_url=download_base_url,
    )


def download_youtube_transcript(token: str):
    return youtube_transcript_service.download_transcript_from_token(token)


def _resolve_download_base_url(request: Request) -> str:
    settings = get_settings()
    if settings.public_api_base_url:
        return f"{settings.public_api_base_url}/utilities/youtube-transcript/download"

    forwarded_proto = request.headers.get('x-forwarded-proto')
    forwarded_host = request.headers.get('x-forwarded-host') or request.headers.get('host')
    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}/utilities/youtube-transcript/download"

    return str(request.url_for('download_youtube_transcript'))
