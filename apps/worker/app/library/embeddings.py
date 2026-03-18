from collections.abc import Iterable

from fastembed import TextEmbedding

from app.config.settings import get_settings


_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        settings = get_settings()
        _model = TextEmbedding(model_name=settings.embedding_model_name)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return [list(vector) for vector in get_embedding_model().embed(texts)]


def get_vector_size() -> int:
    probe_vector = embed_texts(['dimension probe'])
    if not probe_vector:
        raise RuntimeError('Embedding model returned no probe vector.')
    return len(probe_vector[0])
