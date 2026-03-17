"""Tests for KaggleBootstrapIngester — TDD RED phase.

Tests cover:
- Class instantiation with bucket and region
- setup_kaggle_credentials writes ~/.kaggle/kaggle.json with chmod 600
- csv_to_matches parses standard HLTV Kaggle column names
- csv_to_matches handles alternate column name variants (team_a/team_b)
- csv_to_matches skips rows with missing team fields
- csv_to_matches falls back to index-based match_id when column absent
- csv_to_matches returns empty list for empty CSV
- ingest_csv_file calls write_parquet_to_s3 with MATCH_SCHEMA
- download_and_ingest orchestrates credential setup + download + ingest
"""

from __future__ import annotations

import csv
import json
import stat
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from cs2_analytics.ingestion.kaggle import KaggleBootstrapIngester

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ingester() -> KaggleBootstrapIngester:
    """A KaggleBootstrapIngester with a test bucket."""
    return KaggleBootstrapIngester(bucket="test-bucket", region="us-east-1")


@pytest.fixture()
def standard_csv(tmp_path: Path) -> Path:
    """A CSV using standard HLTV Kaggle column names."""
    csv_file = tmp_path / "results.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["match_id", "date", "team_1", "team_2", "map_winner", "map"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "match_id": "m1",
                "date": "2024-01-15",
                "team_1": "Natus Vincere",
                "team_2": "Team Vitality",
                "map_winner": "Natus Vincere",
                "map": "de_mirage",
            }
        )
        writer.writerow(
            {
                "match_id": "m2",
                "date": "2024-01-16",
                "team_1": "FaZe",
                "team_2": "G2",
                "map_winner": "",  # no winner recorded
                "map": "de_dust2",
            }
        )
    return csv_file


@pytest.fixture()
def alternate_columns_csv(tmp_path: Path) -> Path:
    """A CSV using alternate column name variants (team_a/team_b/winner)."""
    csv_file = tmp_path / "alt_results.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "team_a", "team_b", "winner"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2024-02-01",
                "team_a": "MOUZ",
                "team_b": "Spirit",
                "winner": "Spirit",
            }
        )
    return csv_file


@pytest.fixture()
def missing_teams_csv(tmp_path: Path) -> Path:
    """A CSV where some rows have blank team fields — should be skipped."""
    csv_file = tmp_path / "bad_rows.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["match_id", "date", "team_1", "team_2"],
        )
        writer.writeheader()
        writer.writerow({"match_id": "good", "date": "2024-03-01", "team_1": "A", "team_2": "B"})
        writer.writerow({"match_id": "bad", "date": "2024-03-02", "team_1": "", "team_2": "B"})
        writer.writerow({"match_id": "bad2", "date": "2024-03-03", "team_1": "A", "team_2": ""})
    return csv_file


@pytest.fixture()
def no_match_id_csv(tmp_path: Path) -> Path:
    """A CSV with no match_id column — should fall back to index-based IDs."""
    csv_file = tmp_path / "no_id.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "team_1", "team_2"])
        writer.writeheader()
        writer.writerow({"date": "2024-04-01", "team_1": "X", "team_2": "Y"})
    return csv_file


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestInstantiation:
    def test_stores_bucket(self, ingester: KaggleBootstrapIngester) -> None:
        assert ingester._bucket == "test-bucket"

    def test_stores_region(self, ingester: KaggleBootstrapIngester) -> None:
        assert ingester._region == "us-east-1"

    def test_default_region(self) -> None:
        ing = KaggleBootstrapIngester(bucket="b")
        assert ing._region == "us-east-1"


# ---------------------------------------------------------------------------
# setup_kaggle_credentials
# ---------------------------------------------------------------------------


class TestSetupKaggleCredentials:
    def test_writes_json_file(self, ingester: KaggleBootstrapIngester, tmp_path: Path) -> None:
        """Credential file must contain username and key as JSON."""
        creds_file = tmp_path / ".kaggle" / "kaggle.json"
        with patch("pathlib.Path.home", return_value=tmp_path):
            ingester.setup_kaggle_credentials("myuser", "mykey123")
        data = json.loads(creds_file.read_text())
        assert data["username"] == "myuser"
        assert data["key"] == "mykey123"

    def test_sets_chmod_600(self, ingester: KaggleBootstrapIngester, tmp_path: Path) -> None:
        """Credential file must be owner read/write only (chmod 600)."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            ingester.setup_kaggle_credentials("u", "k")
        creds_file = tmp_path / ".kaggle" / "kaggle.json"
        file_mode = stat.S_IMODE(creds_file.stat().st_mode)
        assert file_mode == 0o600

    def test_creates_kaggle_dir(self, ingester: KaggleBootstrapIngester, tmp_path: Path) -> None:
        """~/.kaggle directory must be created if it does not exist."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            ingester.setup_kaggle_credentials("u", "k")
        assert (tmp_path / ".kaggle").is_dir()


# ---------------------------------------------------------------------------
# csv_to_matches
# ---------------------------------------------------------------------------


class TestCsvToMatches:
    def test_parses_standard_columns(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        matches = ingester.csv_to_matches(standard_csv)
        assert len(matches) == 2

    def test_source_is_kaggle(self, ingester: KaggleBootstrapIngester, standard_csv: Path) -> None:
        matches = ingester.csv_to_matches(standard_csv)
        assert all(m.source == "kaggle" for m in matches)

    def test_maps_team_ids_correctly(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        matches = ingester.csv_to_matches(standard_csv)
        assert matches[0].team_a_id == "Natus Vincere"
        assert matches[0].team_b_id == "Team Vitality"

    def test_winner_id_populated(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        matches = ingester.csv_to_matches(standard_csv)
        assert matches[0].winner_id == "Natus Vincere"

    def test_empty_winner_becomes_none(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        """Empty string winner should be stored as None."""
        matches = ingester.csv_to_matches(standard_csv)
        assert matches[1].winner_id is None

    def test_map_name_populated(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        matches = ingester.csv_to_matches(standard_csv)
        assert matches[0].map_name == "de_mirage"

    def test_played_at_populated(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        matches = ingester.csv_to_matches(standard_csv)
        assert matches[0].played_at == "2024-01-15"

    def test_alternate_team_columns(
        self, ingester: KaggleBootstrapIngester, alternate_columns_csv: Path
    ) -> None:
        """team_a / team_b / winner column variants must be recognised."""
        matches = ingester.csv_to_matches(alternate_columns_csv)
        assert len(matches) == 1
        assert matches[0].team_a_id == "MOUZ"
        assert matches[0].team_b_id == "Spirit"
        assert matches[0].winner_id == "Spirit"

    def test_skips_rows_with_missing_teams(
        self, ingester: KaggleBootstrapIngester, missing_teams_csv: Path
    ) -> None:
        """Rows where team_a or team_b is blank must be skipped."""
        matches = ingester.csv_to_matches(missing_teams_csv)
        assert len(matches) == 1
        assert matches[0].match_id == "good"

    def test_fallback_match_id_when_column_absent(
        self, ingester: KaggleBootstrapIngester, no_match_id_csv: Path
    ) -> None:
        """When no match_id column exists, generate index-based ID."""
        matches = ingester.csv_to_matches(no_match_id_csv)
        assert len(matches) == 1
        assert "no_id" in matches[0].match_id  # stem of file name in generated ID

    def test_empty_csv_returns_empty_list(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        empty_csv = tmp_path / "empty.csv"
        with empty_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "team_1", "team_2"])
            writer.writeheader()
            # No data rows
        matches = ingester.csv_to_matches(empty_csv)
        assert matches == []


# ---------------------------------------------------------------------------
# ingest_csv_file
# ---------------------------------------------------------------------------


class TestIngestCsvFile:
    def test_calls_write_parquet_to_s3(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        """ingest_csv_file must call write_parquet_to_s3 with MATCH_SCHEMA."""
        with patch("cs2_analytics.ingestion.kaggle.write_parquet_to_s3") as mock_write:
            _ = ingester.ingest_csv_file(standard_csv, date(2024, 1, 20))
        mock_write.assert_called_once()
        _, kwargs = mock_write.call_args
        # schema kwarg must be MATCH_SCHEMA — check by checking type
        from cs2_analytics.utils.parquet import MATCH_SCHEMA

        call_args = mock_write.call_args
        assert call_args[1].get("schema") == MATCH_SCHEMA or call_args[0][1] == MATCH_SCHEMA

    def test_returns_match_count(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        with patch("cs2_analytics.ingestion.kaggle.write_parquet_to_s3"):
            count = ingester.ingest_csv_file(standard_csv, date(2024, 1, 20))
        assert count == 2

    def test_returns_zero_for_empty_csv(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        empty_csv = tmp_path / "empty.csv"
        with empty_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "team_1", "team_2"])
            writer.writeheader()
        with patch("cs2_analytics.ingestion.kaggle.write_parquet_to_s3") as mock_write:
            count = ingester.ingest_csv_file(empty_csv, date(2024, 1, 20))
        mock_write.assert_not_called()
        assert count == 0

    def test_s3_key_uses_kaggle_source(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        """S3 key must start with raw/kaggle/matches/"""
        with patch("cs2_analytics.ingestion.kaggle.write_parquet_to_s3") as mock_write:
            ingester.ingest_csv_file(standard_csv, date(2024, 1, 20))
        call_kwargs = mock_write.call_args
        # key is a positional argument (3rd: records, schema, bucket, key)
        key_arg = call_kwargs[1].get("key") or call_kwargs[0][3]
        assert key_arg.startswith("raw/kaggle/matches/")


# ---------------------------------------------------------------------------
# download_and_ingest (orchestration, mocked Kaggle API)
# ---------------------------------------------------------------------------


class TestDownloadAndIngest:
    def test_calls_setup_credentials(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        """download_and_ingest must call setup_kaggle_credentials with username/key."""
        with (
            patch.object(ingester, "setup_kaggle_credentials") as mock_creds,
            patch.object(ingester, "download_dataset", return_value=tmp_path),
            patch.object(ingester, "ingest_csv_file", return_value=0),
        ):
            ingester.download_and_ingest("user", "apikey", date(2024, 1, 1))
        mock_creds.assert_called_once_with("user", "apikey")

    def test_calls_download_dataset(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        with (
            patch.object(ingester, "setup_kaggle_credentials"),
            patch.object(ingester, "download_dataset", return_value=tmp_path) as mock_dl,
            patch.object(ingester, "ingest_csv_file", return_value=0),
        ):
            ingester.download_and_ingest("u", "k", date(2024, 1, 1))
        mock_dl.assert_called_once()

    def test_returns_total_count(self, ingester: KaggleBootstrapIngester, tmp_path: Path) -> None:
        """Total returned must be sum of per-file counts."""
        # Create two fake CSV files in tmp_path
        (tmp_path / "a.csv").write_text("date,team_1,team_2\n2024-01-01,A,B\n")
        (tmp_path / "b.csv").write_text("date,team_1,team_2\n2024-01-02,C,D\n")
        with (
            patch.object(ingester, "setup_kaggle_credentials"),
            patch.object(ingester, "download_dataset", return_value=tmp_path),
            patch.object(ingester, "ingest_csv_file", return_value=5),
        ):
            total = ingester.download_and_ingest("u", "k", date(2024, 1, 1))
        assert total == 10  # 5 per file × 2 files

    def test_returns_zero_when_no_csvs(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        with (
            patch.object(ingester, "setup_kaggle_credentials"),
            patch.object(ingester, "download_dataset", return_value=tmp_path),
        ):
            total = ingester.download_and_ingest("u", "k", date(2024, 1, 1))
        assert total == 0
