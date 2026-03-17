"""Tests for S3 utility functions using moto mock_aws decorator.

Covers:
- build_s3_key: Hive-partitioned path format, zero-padding, custom filename
- write_parquet_to_s3: uploads valid Parquet to mocked S3 bucket (no real AWS calls)
"""

from __future__ import annotations

import boto3
from moto import mock_aws

from cs2_analytics.utils.parquet import MATCH_SCHEMA
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

# ---------------------------------------------------------------------------
# build_s3_key tests
# ---------------------------------------------------------------------------


def test_build_s3_key_standard_format() -> None:
    """Verify full Hive-partitioned path with zero-padded single-digit month/day."""
    key = build_s3_key("faceit", "matches", 2024, 1, 15)
    assert key == "raw/faceit/matches/year=2024/month=01/day=15/data.parquet"


def test_build_s3_key_zero_pads_month_and_day() -> None:
    """Single-digit month and day must be zero-padded to two characters."""
    key = build_s3_key("pandascore", "players", 2024, 3, 7)
    assert "month=03" in key
    assert "day=07" in key


def test_build_s3_key_custom_filename() -> None:
    """Custom filename= replaces default 'data.parquet' in the path."""
    key = build_s3_key("kaggle", "matches", 2024, 1, 15, filename="part-0.parquet")
    assert key.endswith("part-0.parquet")
    assert "data.parquet" not in key


def test_build_s3_key_structure() -> None:
    """Path segments must follow raw/{source}/{entity}/year=/month=/day=/{file} order."""
    key = build_s3_key("liquipedia", "teams", 2024, 12, 31)
    parts = key.split("/")
    assert parts[0] == "raw"
    assert parts[1] == "liquipedia"
    assert parts[2] == "teams"
    assert parts[3] == "year=2024"
    assert parts[4] == "month=12"
    assert parts[5] == "day=31"


# ---------------------------------------------------------------------------
# write_parquet_to_s3 tests — use moto mock_aws to avoid real AWS calls
# ---------------------------------------------------------------------------


@mock_aws
def test_write_parquet_to_s3_uploads_object() -> None:
    """write_parquet_to_s3 must create a valid S3 object inside moto mock."""
    bucket = "test-cs2-bucket"
    region = "us-east-1"

    # Create bucket inside the moto mock context
    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(Bucket=bucket)

    records = [
        {
            "match_id": "test-001",
            "source": "faceit",
            "team_a_id": "team-a",
            "team_b_id": "team-b",
            "winner_id": "team-a",
            "played_at": "2024-01-15",
            "map_name": "de_mirage",
        }
    ]
    key = build_s3_key("faceit", "matches", 2024, 1, 15)
    write_parquet_to_s3(records, MATCH_SCHEMA, bucket, key, region=region)

    # Verify the object was created with non-zero content
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    assert len(body) > 0
    # Parquet files start with magic bytes: PAR1
    assert body[:4] == b"PAR1"


@mock_aws
def test_write_parquet_to_s3_empty_records() -> None:
    """write_parquet_to_s3 with empty records still uploads a valid Parquet file (0 rows)."""
    bucket = "test-cs2-bucket"
    region = "us-east-1"
    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(Bucket=bucket)

    key = build_s3_key("faceit", "matches", 2024, 1, 15, filename="empty.parquet")
    write_parquet_to_s3([], MATCH_SCHEMA, bucket, key, region=region)

    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    # Empty Parquet still has valid magic bytes
    assert body[:4] == b"PAR1"
