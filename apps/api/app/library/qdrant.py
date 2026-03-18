from qdrant_client import QdrantClient

from app.config.settings import Settings


_client: QdrantClient | None = None


def init_qdrant_client(settings: Settings) -> None:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)


def get_qdrant_client() -> QdrantClient:
    if _client is None:
        raise RuntimeError('Qdrant client has not been initialized.')
    return _client


def close_qdrant_client() -> None:
    global _client
    if _client is not None:
        close_method = getattr(_client, 'close', None)
        if callable(close_method):
            close_method()
        _client = None
