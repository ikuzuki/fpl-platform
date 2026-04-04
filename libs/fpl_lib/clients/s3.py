"""S3 client wrapper for data lake operations."""

import io
import json
import logging
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


class S3Client:
    """Wrapper around boto3 S3 client for common data lake operations."""

    def __init__(self, region: str = "eu-west-2") -> None:
        self._client = boto3.client("s3", region_name=region)

    def put_json(self, bucket: str, key: str, data: dict[str, Any] | list[Any]) -> None:
        """Write JSON data to S3."""
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, default=str),
            ContentType="application/json",
        )
        logger.info("Wrote JSON to s3://%s/%s", bucket, key)

    def read_json(self, bucket: str, key: str) -> dict[str, Any] | list[Any]:
        """Read JSON data from S3."""
        response = self._client.get_object(Bucket=bucket, Key=key)
        result: dict[str, Any] | list[Any] = json.loads(response["Body"].read().decode("utf-8"))
        return result

    def write_parquet(
        self,
        bucket: str,
        key: str,
        table: pa.Table,
        compression: str = "zstd",
    ) -> None:
        """Write a PyArrow table as Parquet to S3."""
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression=compression)
        buffer.seek(0)
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=buffer.getvalue(),
            ContentType="application/octet-stream",
        )
        logger.info("Wrote Parquet to s3://%s/%s", bucket, key)

    def read_parquet(self, bucket: str, key: str) -> pa.Table:
        """Read a Parquet file from S3 as a PyArrow table."""
        response = self._client.get_object(Bucket=bucket, Key=key)
        buffer = io.BytesIO(response["Body"].read())
        return pq.read_table(buffer)

    def object_exists(self, bucket: str, key: str) -> bool:
        """Check if an object exists in S3."""
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except self._client.exceptions.ClientError:
            return False

    def list_objects(self, bucket: str, prefix: str) -> list[str]:
        """List object keys under a prefix."""
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys
