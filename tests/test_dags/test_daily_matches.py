"""Unit tests for cs2_daily_matches DAG task logic.

Tests the S3 idempotency helper _s3_key_exists in isolation.
Does NOT call asyncio.run() directly — tests the synchronous helper only.
The async ingestion functions are covered indirectly by Phase 1 tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def test_s3_key_exists_returns_true_on_200() -> None:
    """_s3_key_exists() returns True when head_object succeeds (key present)."""
    from airflow.dags.cs2_daily_matches import _s3_key_exists

    with patch("airflow.dags.cs2_daily_matches.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.head_object.return_value = {"ContentLength": 1024}

        result = _s3_key_exists("test-bucket", "raw/matches/faceit/2024-01-01/matches.parquet")

    assert result is True


def test_s3_key_exists_returns_false_on_404() -> None:
    """_s3_key_exists() returns False when head_object raises ClientError 404."""
    from airflow.dags.cs2_daily_matches import _s3_key_exists

    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    with patch("airflow.dags.cs2_daily_matches.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")

        result = _s3_key_exists("test-bucket", "raw/matches/faceit/2024-01-01/missing.parquet")

    assert result is False


def test_s3_key_exists_reraises_non_404_errors() -> None:
    """_s3_key_exists() re-raises ClientError for non-404 error codes (e.g., 403 Forbidden)."""
    from airflow.dags.cs2_daily_matches import _s3_key_exists

    error_response = {"Error": {"Code": "403", "Message": "Forbidden"}}
    with patch("airflow.dags.cs2_daily_matches.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")

        with pytest.raises(ClientError):
            _s3_key_exists("test-bucket", "raw/matches/faceit/2024-01-01/forbidden.parquet")
