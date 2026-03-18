from uuid import UUID

from app.library.db import transaction
from app.models import chat_model



def persist_sources(*, message_id: UUID, citations: list[dict]) -> None:
    if not citations:
        return
    with transaction() as conn:
        for citation in citations:
            chat_model.create_message_source(
                message_id=message_id,
                chunk_id=citation['chunk_id'],
                file_id=citation['file_id'],
                citation_label=citation['citation_label'],
                rank=citation['rank'],
                score=float(citation['score']),
                metadata={
                    'filename': citation['filename'],
                    'page_number': citation.get('page_number'),
                    'row_number': citation.get('row_number'),
                    'chunk_index': citation.get('chunk_index'),
                    'source_type': citation.get('source_type'),
                },
                conn=conn,
            )
