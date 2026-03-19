import json
from uuid import UUID, uuid4

from app.config.settings import get_settings
from app.library.cache import bump_retrieval_cache_versions
from app.library.qdrant import close_qdrant_client, ensure_chunks_collection, init_qdrant_client, delete_file_points
from app.library.queue import pop_job
from app.library.redis_client import close_redis_client, init_redis_client
from app.library.storage import close_storage_client, download_bytes, init_storage_client
from app.services.chunking_service import chunk_parsed_units, chunk_to_dict
from app.services.csv_processor import parse_csv_bytes
from app.services.excel_processor import parse_excel_bytes
from app.services.embedding_service import embed_in_batches
from app.services.indexing_service import upsert_chunk_vectors
from app.services.pdf_processor import parse_pdf_bytes
from app.services.progress_service import JobTracker, get_job_context, mark_chunks_indexed, utcnow, replace_file_chunks


SUPPORTED_CONTENT_TYPES = {
    'application/pdf': 'pdf',
    'text/csv': 'csv',
    'application/csv': 'csv',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel',
    'application/vnd.ms-excel': 'excel',
    'application/excel': 'excel',
    'application/x-excel': 'excel',
    'application/x-msexcel': 'excel',
}



def run_worker_loop() -> None:
    settings = get_settings()
    init_redis_client(settings.redis_url)
    init_storage_client(settings)
    init_qdrant_client(settings)
    ensure_chunks_collection()

    print(
        json.dumps(
            {
                'service': 'worker',
                'status': 'started',
                'worker_id': settings.worker_id,
                'queue_name': settings.ingestion_queue_name,
                'qdrant_collection': settings.qdrant_chunks_collection,
                'timestamp': utcnow().isoformat(),
            }
        ),
        flush=True,
    )

    try:
        while True:
            job_payload = pop_job(settings.ingestion_queue_name, settings.block_timeout_seconds)
            if not job_payload:
                continue
            process_job(job_payload)
    finally:
        close_storage_client()
        close_qdrant_client()
        close_redis_client()



def process_job(job_payload: dict) -> None:
    settings = get_settings()
    job_id = UUID(job_payload['job_id'])
    job = get_job_context(job_id)
    if not job:
        print(json.dumps({'service': 'worker', 'status': 'missing_job', 'job_id': str(job_id)}), flush=True)
        return

    started_at = utcnow()
    job['attempts'] = int(job['attempts']) + 1
    tracker = JobTracker(job=job, worker_id=settings.worker_id, started_at=started_at)

    try:
        tracker.stage(
            stage_name='downloading',
            progress_percent=10,
            message='Downloading file from MinIO.',
            stage_status='running',
            details={'object_key': job['minio_object_key']},
        )
        content = download_bytes(job['minio_bucket'], job['minio_object_key'])
        tracker.stage(
            stage_name='downloading',
            progress_percent=15,
            message='File downloaded from MinIO.',
            stage_status='completed',
            details={'size_bytes': len(content)},
        )

        tracker.stage(
            stage_name='parsing',
            progress_percent=25,
            message='Parsing source document.',
            stage_status='running',
        )
        parsed = _parse_file(job=job, content=content)
        tracker.stage(
            stage_name='parsing',
            progress_percent=35,
            message='Source document parsed successfully.',
            stage_status='completed',
            details={'unit_count': len(parsed['units'])},
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
        )

        tracker.stage(
            stage_name='chunking',
            progress_percent=45,
            message='Chunking parsed content.',
            stage_status='running',
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
        )
        chunk_rows = _build_chunk_rows(chunk_parsed_units(parsed['units']))
        replace_file_chunks(job=tracker.job, chunk_rows=chunk_rows)
        total_chunks = len(chunk_rows)
        tracker.stage(
            stage_name='chunking',
            progress_percent=55,
            message=f'Persisted {total_chunks} chunks to PostgreSQL.',
            stage_status='completed',
            details={'total_chunks': total_chunks},
            total_chunks=total_chunks,
            processed_chunks=0,
            indexed_chunks=0,
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
        )

        tracker.stage(
            stage_name='embedding',
            progress_percent=60,
            message='Generating chunk embeddings.',
            stage_status='running',
            total_chunks=total_chunks,
            processed_chunks=0,
            indexed_chunks=0,
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
        )
        _embed_chunks(tracker=tracker, chunk_rows=chunk_rows)
        tracker.stage(
            stage_name='embedding',
            progress_percent=80,
            message='Chunk embeddings generated successfully.',
            stage_status='completed',
            total_chunks=total_chunks,
            processed_chunks=total_chunks,
            indexed_chunks=0,
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
        )

        tracker.stage(
            stage_name='indexing',
            progress_percent=82,
            message='Indexing chunk vectors in Qdrant.',
            stage_status='running',
            total_chunks=total_chunks,
            processed_chunks=total_chunks,
            indexed_chunks=0,
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
        )
        _index_chunks(tracker=tracker, chunk_rows=chunk_rows)
        cache_versions = bump_retrieval_cache_versions(collection_id=tracker.job.get('collection_id'))
        completed_at = utcnow()
        tracker.stage(
            stage_name='indexing',
            progress_percent=95,
            message='Chunk vectors indexed in Qdrant.',
            stage_status='completed',
            total_chunks=total_chunks,
            processed_chunks=total_chunks,
            indexed_chunks=total_chunks,
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
        )
        tracker.stage(
            stage_name='completed',
            progress_percent=100,
            message='Ingestion completed successfully.',
            stage_status='completed',
            details={'result': 'success', 'cache_versions': cache_versions},
            total_chunks=total_chunks,
            processed_chunks=total_chunks,
            indexed_chunks=total_chunks,
            page_count=parsed['page_count'],
            row_count=parsed['row_count'],
            source_type=parsed['source_type'],
            completed_at=completed_at,
        )
        print(json.dumps({'service': 'worker', 'status': 'completed', 'job_id': str(job_id), 'cache_versions': cache_versions}), flush=True)
    except Exception as exc:
        failed_at = utcnow()
        tracker.stage(
            stage_name='failed',
            progress_percent=float(tracker.job.get('progress_percent', 0) or 0),
            message='Ingestion failed.',
            stage_status='failed',
            details={'failed_stage': tracker.job.get('current_stage'), 'error': str(exc)},
            total_chunks=int(tracker.job.get('total_chunks', 0) or 0),
            processed_chunks=int(tracker.job.get('processed_chunks', 0) or 0),
            indexed_chunks=int(tracker.job.get('indexed_chunks', 0) or 0),
            page_count=tracker.job.get('page_count'),
            row_count=tracker.job.get('row_count'),
            source_type=tracker.job.get('source_type'),
            completed_at=failed_at,
            failed_at=failed_at,
            error_message=str(exc),
        )
        print(
            json.dumps(
                {
                    'service': 'worker',
                    'status': 'failed',
                    'job_id': str(job_id),
                    'current_stage': tracker.job.get('current_stage'),
                    'error': str(exc),
                }
            ),
            flush=True,
        )



def _parse_file(*, job: dict, content: bytes) -> dict:
    source_type = job.get('source_type') or SUPPORTED_CONTENT_TYPES.get(job['content_type'])
    if source_type == 'pdf':
        return parse_pdf_bytes(content)
    if source_type == 'csv':
        return parse_csv_bytes(content)
    if source_type == 'excel':
        return parse_excel_bytes(content)
    raise ValueError(f"Unsupported content type '{job['content_type']}'.")



def _build_chunk_rows(chunk_records) -> list[dict]:
    chunk_rows: list[dict] = []
    for chunk_record in chunk_records:
        row = chunk_to_dict(chunk_record)
        row['id'] = uuid4()
        row['qdrant_point_id'] = uuid4()
        row['embedding'] = None
        chunk_rows.append(row)
    return chunk_rows



def _embed_chunks(*, tracker: JobTracker, chunk_rows: list[dict]) -> None:
    total_chunks = len(chunk_rows)
    if total_chunks == 0:
        return

    texts = [chunk['content'] for chunk in chunk_rows]
    for start, vectors in embed_in_batches(texts):
        for offset, vector in enumerate(vectors):
            chunk_rows[start + offset]['embedding'] = vector

        processed_chunks = start + len(vectors)
        progress = 60 + ((processed_chunks / total_chunks) * 20)
        tracker.stage(
            stage_name='embedding',
            progress_percent=round(progress, 2),
            message=f'Generated embeddings for {processed_chunks} of {total_chunks} chunks.',
            stage_status='running',
            total_chunks=total_chunks,
            processed_chunks=processed_chunks,
            indexed_chunks=0,
            emit_event=False,
        )



def _index_chunks(*, tracker: JobTracker, chunk_rows: list[dict]) -> None:
    total_chunks = len(chunk_rows)
    if total_chunks == 0:
        return

    delete_file_points(str(tracker.job['file_id']))
    upserted = 0
    settings = get_settings()
    batch_size = max(settings.indexing_batch_size, 1)

    for start in range(0, total_chunks, batch_size):
        batch = chunk_rows[start:start + batch_size]
        upsert_chunk_vectors(
            file_id=tracker.job['file_id'],
            collection_id=tracker.job['collection_id'],
            file_name=tracker.job['original_name'],
            chunks=batch,
        )
        upserted += len(batch)
        mark_chunks_indexed(
            chunk_ids=[str(chunk['id']) for chunk in batch],
            embedding_model_name=settings.embedding_model_name,
            indexed_at=utcnow(),
        )
        progress = 82 + ((upserted / total_chunks) * 13)
        tracker.stage(
            stage_name='indexing',
            progress_percent=round(progress, 2),
            message=f'Indexed {upserted} of {total_chunks} chunks in Qdrant.',
            stage_status='running',
            total_chunks=total_chunks,
            processed_chunks=total_chunks,
            indexed_chunks=upserted,
            emit_event=False,
        )
