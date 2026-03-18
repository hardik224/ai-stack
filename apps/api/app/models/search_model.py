from app.models import retrieval_model



def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    return retrieval_model.get_chunks_by_ids(chunk_ids)
