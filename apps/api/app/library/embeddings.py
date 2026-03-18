from fastembed import TextEmbedding

from app.config.settings import get_settings


_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        settings = get_settings()
        _model = TextEmbedding(model_name=settings.embedding_model_name)
    return _model


def embed_query(text: str) -> list[float]:
    vectors = list(get_embedding_model().embed([text]))
    if not vectors:
        raise RuntimeError('Embedding model returned no vector for query.')
    return list(vectors[0])
