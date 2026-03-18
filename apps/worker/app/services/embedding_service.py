from app.config.settings import get_settings
from app.library.embeddings import embed_texts



def embed_in_batches(texts: list[str]):
    settings = get_settings()
    batch_size = max(settings.embedding_batch_size, 1)

    for start in range(0, len(texts), batch_size):
        batch_texts = texts[start:start + batch_size]
        yield start, embed_texts(batch_texts)
