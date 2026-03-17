"""Tests for KaggleBootstrapIngester using the tests/fixtures/kaggle/sample_matches.csv fixture.

Covers:
- csv_to_matches parses all rows from the fixture file
- csv_to_matches produces correct canonical Match fields
- csv_to_matches handles empty map_winner (produces winner_id=None)
- csv_to_matches skips rows with missing team_1 or team_2
- setup_kaggle_credentials writes correct JSON to the target path
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest.mock as mock
from pathlib import Path

import pytest

from cs2_analytics.ingestion.kaggle import KaggleBootstrapIngester


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_csv_path() -> Path:
    """Path to the realistic sample CSV fixture with 3 data rows."""
    return Path(__file__).parent / "fixtures/kaggle/sample_matches.csv"


@pytest.fixture
def ingester() -> KaggleBootstrapIngester:
    """KaggleBootstrapIngester configured with a test bucket."""
    return KaggleBootstrapIngester(bucket="test-bucket")


# ---------------------------------------------------------------------------
# csv_to_matches — fixture file tests
# ---------------------------------------------------------------------------


def test_csv_to_matches_parses_all_rows(
    ingester: KaggleBootstrapIngester, sample_csv_path: Path
) -> None:
    """csv_to_matches should return one Match per valid row in the fixture (3 rows)."""
    matches = ingester.csv_to_matches(sample_csv_path)
    assert len(matches) == 3
    assert all(m.source == "kaggle" for m in matches)


def test_csv_to_matches_correct_fields(
    ingester: KaggleBootstrapIngester, sample_csv_path: Path
) -> None:
    """First fixture row must map to canonical Match fields correctly."""
    matches = ingester.csv_to_matches(sample_csv_path)
    first = matches[0]
    assert first.match_id == "kaggle-001"
    assert first.team_a_id == "Natus Vincere"
    assert first.team_b_id == "Team Vitality"
    assert first.winner_id == "Natus Vincere"
    assert first.map_name == "de_mirage"
    assert first.played_at == "2024-01-15"


def test_csv_to_matches_empty_winner_is_none(
    ingester: KaggleBootstrapIngester, sample_csv_path: Path
) -> None:
    """Third fixture row has empty map_winner — winner_id must be None."""
    matches = ingester.csv_to_matches(sample_csv_path)
    third = matches[2]
    assert third.winner_id is None


# ---------------------------------------------------------------------------
# csv_to_matches — skipping rows with missing teams
# ---------------------------------------------------------------------------


def test_csv_to_matches_skips_rows_without_teams(
    ingester: KaggleBootstrapIngester,
) -> None:
    """Rows with blank team_1 are skipped; rows with valid teams are kept."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=["match_id", "date", "team_1", "team_2", "map_winner"]
        )
        writer.writeheader()
        # Row with missing team_1 — should be skipped
        writer.writerow(
            {
                "match_id": "bad-row",
                "date": "2024-01-01",
                "team_1": "",
                "team_2": "TeamB",
                "map_winner": "",
            }
        )
        # Valid row — should be included
        writer.writerow(
            {
                "match_id": "good-row",
                "date": "2024-01-01",
                "team_1": "TeamA",
                "team_2": "TeamB",
                "map_winner": "TeamA",
            }
        )
        tmp = Path(f.name)

    matches = ingester.csv_to_matches(tmp)
    tmp.unlink()
    assert len(matches) == 1
    assert matches[0].match_id == "good-row"


# ---------------------------------------------------------------------------
# setup_kaggle_credentials
# ---------------------------------------------------------------------------


def test_setup_credentials_writes_json(ingester: KaggleBootstrapIngester) -> None:
    """setup_kaggle_credentials must write correct JSON to ~/.kaggle/kaggle.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        kaggle_dir = Path(tmpdir) / ".kaggle"
        with mock.patch("pathlib.Path.home", return_value=Path(tmpdir)):
            ingester.setup_kaggle_credentials("testuser", "testapikey")

        creds_file = kaggle_dir / "kaggle.json"
        assert creds_file.exists()
        data = json.loads(creds_file.read_text())
        assert data["username"] == "testuser"
        assert data["key"] == "testapikey"
