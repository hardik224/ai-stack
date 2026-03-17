from io import BytesIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config.settings import Settings


_client = None


def init_storage_client(settings: Settings) -> None:
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )


def get_storage_client():
    if _client is None:
        raise RuntimeError("Storage client has not been initialized.")
    return _client


def close_storage_client() -> None:
    global _client
    _client = None


def ensure_bucket_exists(bucket_name: str) -> None:
    client = get_storage_client()
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError:
        client.create_bucket(Bucket=bucket_name)


def upload_bytes(bucket_name: str, object_key: str, content: bytes, content_type: str) -> None:
    client = get_storage_client()
    client.upload_fileobj(
        Fileobj=BytesIO(content),
        Bucket=bucket_name,
        Key=object_key,
        ExtraArgs={"ContentType": content_type},
    )
