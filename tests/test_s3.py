"""TDD tests for cs2_analytics.utils.s3 — S3 upload and Hive path utilities.

RED phase: these tests are written before the implementation exists.
They define the exact contract the implementation must satisfy.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pyarrow.parquet as pq

# ---------------------------------------------------------------------------
# build_s3_key() tests
# ---------------------------------------------------------------------------


def test_build_s3_key_basic() -> None:
    """Standard faceit/matches path with single-digit month and day."""
    from cs2_analytics.utils.s3 import build_s3_key

    key = build_s3_key("faceit", "matches", 2024, 1, 15)
    assert key == "raw/faceit/matches/year=2024/month=01/day=15/data.parquet"


def test_build_s3_key_double_digit_month_day() -> None:
    """Double-digit month and day should not add extra padding."""
    from cs2_analytics.utils.s3 import build_s3_key

    key = build_s3_key("liquipedia", "teams", 2024, 12, 5)
    assert key == "raw/liquipedia/teams/year=2024/month=12/day=05/data.parquet"


def test_build_s3_key_single_digit_day_zero_padded() -> None:
    """Single-digit day must be zero-padded to two characters."""
    from cs2_analytics.utils.s3 import build_s3_key

    key = build_s3_key("pandascore", "matches", 2024, 3, 7)
    assert key == "raw/pandascore/matches/year=2024/month=03/day=07/data.parquet"


def test_build_s3_key_custom_filename() -> None:
    """Custom filename= argument replaces the default 'data.parquet'."""
    from cs2_analytics.utils.s3 import build_s3_key

    key = build_s3_key("pandascore", "matches", 2024, 3, 7, filename="part-0.parquet")
    assert key == "raw/pandascore/matches/year=2024/month=03/day=07/part-0.parquet"


def test_build_s3_key_kaggle_source() -> None:
    """Kaggle source should produce valid Hive-partitioned path."""
    from cs2_analytics.utils.s3 import build_s3_key

    key = build_s3_key("kaggle", "players", 2023, 11, 30)
    assert key == "raw/kaggle/players/year=2023/month=11/day=30/data.parquet"


def test_build_s3_key_default_filename_is_data_parquet() -> None:
    """Default filename must be 'data.parquet' when not specified."""
    from cs2_analytics.utils.s3 import build_s3_key

    key = build_s3_key("faceit", "matches", 2024, 6, 1)
    assert key.endswith("/data.parquet")


# ---------------------------------------------------------------------------
# write_parquet_to_s3() tests — use mocked boto3 to avoid real AWS calls
# ---------------------------------------------------------------------------


def test_write_parquet_to_s3_calls_put_object() -> None:
    """write_parquet_to_s3 must call boto3 s3.put_object with correct Bucket and Key."""
    from cs2_analytics.models.canonical import Match
    from cs2_analytics.utils.parquet import MATCH_SCHEMA, models_to_records
    from cs2_analytics.utils.s3 import write_parquet_to_s3

    match = Match(
        match_id="m1",
        source="faceit",
        team_a_id="ta",
        team_b_id="tb",
        winner_id=None,
        played_at="2024-01-15",
    )
    records = models_to_records([match])

    mock_s3 = MagicMock()
    with patch("cs2_analytics.utils.s3.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        write_parquet_to_s3(
            records,
            MATCH_SCHEMA,
            bucket="test-bucket",
            key="raw/faceit/matches/year=2024/month=01/day=15/data.parquet",
        )

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"] == "raw/faceit/matches/year=2024/month=01/day=15/data.parquet"
    assert isinstance(call_kwargs["Body"], bytes)
    assert call_kwargs["ContentType"] == "application/octet-stream"


def test_write_parquet_to_s3_empty_records() -> None:
    """write_parquet_to_s3 with empty records must still upload a valid Parquet file."""
    from cs2_analytics.utils.parquet import MATCH_SCHEMA
    from cs2_analytics.utils.s3 import write_parquet_to_s3

    mock_s3 = MagicMock()
    with patch("cs2_analytics.utils.s3.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        write_parquet_to_s3(
            [],
            MATCH_SCHEMA,
            bucket="test-bucket",
            key="raw/faceit/matches/year=2024/month=01/day=15/data.parquet",
        )

    mock_s3.put_object.assert_called_once()
    body_bytes = mock_s3.put_object.call_args.kwargs["Body"]
    # Body must be valid Parquet — read it back to confirm
    buf = BytesIO(body_bytes)
    table = pq.read_table(buf)
    assert table.num_rows == 0


def test_write_parquet_to_s3_uses_snappy_compression() -> None:
    """Uploaded body must be snappy-compressed Parquet (not uncompressed or gzip)."""
    from cs2_analytics.models.canonical import Player
    from cs2_analytics.utils.parquet import PLAYER_SCHEMA, models_to_records
    from cs2_analytics.utils.s3 import write_parquet_to_s3

    player = Player(
        player_id="p1",
        source="faceit",
        display_name="player_one",
        recorded_at="2024-01-15",
    )
    records = models_to_records([player])

    mock_s3 = MagicMock()
    with patch("cs2_analytics.utils.s3.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        write_parquet_to_s3(records, PLAYER_SCHEMA, bucket="b", key="k")

    body_bytes = mock_s3.put_object.call_args.kwargs["Body"]
    buf = BytesIO(body_bytes)
    pf = pq.ParquetFile(buf)
    # pyarrow records compression at row group level
    metadata = pf.metadata
    col_meta = metadata.row_group(0).column(0)
    assert col_meta.compression == "SNAPPY"


def test_write_parquet_to_s3_boto3_client_uses_region() -> None:
    """boto3.client must be called with the correct region_name."""
    from cs2_analytics.utils.parquet import TEAM_SCHEMA
    from cs2_analytics.utils.s3 import write_parquet_to_s3

    mock_s3 = MagicMock()
    with patch("cs2_analytics.utils.s3.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        write_parquet_to_s3([], TEAM_SCHEMA, bucket="b", key="k", region="eu-west-1")

    mock_boto3.client.assert_called_once_with("s3", region_name="eu-west-1")
