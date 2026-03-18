from io import BytesIO

import boto3
from botocore.client import Config

from app.config.settings import Settings


_client = None


def init_storage_client(settings: Settings) -> None:
    global _client
    if _client is None:
        _client = boto3.client(
            's3',
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1',
        )


def get_storage_client():
    if _client is None:
        raise RuntimeError('Storage client has not been initialized.')
    return _client


def close_storage_client() -> None:
    global _client
    _client = None


def download_bytes(bucket_name: str, object_key: str) -> bytes:
    buffer = BytesIO()
    get_storage_client().download_fileobj(bucket_name, object_key, buffer)
    return buffer.getvalue()
