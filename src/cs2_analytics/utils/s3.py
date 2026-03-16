"""S3 upload utilities for CS2 analytics ingestion pipeline.

Provides two functions consumed by all four ingestion clients:
- build_s3_key(): constructs Hive-partitioned S3 paths (Athena/dbt compatible)
- write_parquet_to_s3(): serializes records to snappy Parquet and uploads via boto3

Callers pass bucket and region explicitly so this module is testable without
a real .env file or AWS credentials.
"""
from __future__ import annotations

from io import BytesIO

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

# Module-level structured logger — emits JSON-compatible log events
logger = structlog.get_logger()


def build_s3_key(
    source: str,
    entity_type: str,
    year: int,
    month: int,
    day: int,
    filename: str = "data.parquet",
) -> str:
    """Build Hive-partitioned S3 key for raw ingestion data.

    Format: raw/{source}/{entity_type}/year={y}/month={mm}/day={dd}/{filename}

    Zero-padded month and day guarantee correct lexicographic sort order, which
    is required for Athena partition projection and dbt external table scanning.
    The default filename 'data.parquet' is used for single-file daily uploads.
    """
    return (
        f"raw/{source}/{entity_type}"
        f"/year={year}/month={month:02d}/day={day:02d}"
        f"/{filename}"
    )


def write_parquet_to_s3(
    records: list[dict],
    schema: pa.Schema,
    bucket: str,
    key: str,
    *,
    region: str = "us-east-1",
) -> None:
    """Serialize records to snappy-compressed Parquet and upload to S3.

    The explicit schema= argument is MANDATORY — it prevents ArrowInvalid errors
    when a batch contains all-None values in a nullable column (pyarrow cannot
    infer nullable flags without the schema hint).

    Overwrites any existing S3 object at the given key — idempotent on re-runs.
    Uses a BytesIO buffer to avoid writing temporary files to disk.
    """
    # Serialize records to Parquet in memory using the explicit schema
    table = pa.Table.from_pylist(records, schema=schema)
    buf = BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)  # Reset position to start before reading bytes

    # Upload to S3 — ContentType for binary Parquet files
    s3 = boto3.client("s3", region_name=region)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )

    # Log after successful upload so failures that get retried don't produce log noise
    logger.info(
        "parquet_uploaded",
        bucket=bucket,
        key=key,
        row_count=len(records),
    )
