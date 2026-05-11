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
from unittest.mock import call, patch

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
            fieldnames=[
                "match_id",
                "date",
                "team_1",
                "team_2",
                "map_winner",
                "_map",
                "result_1",
                "result_2",
                "rank_1",
                "rank_2",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "match_id": "m1",
                "date": "2024-01-15",
                "team_1": "Natus Vincere",
                "team_2": "Team Vitality",
                "map_winner": "1",
                "_map": "de_mirage",
                "result_1": "16",
                "result_2": "12",
                "rank_1": "2",
                "rank_2": "1",
            }
        )
        writer.writerow(
            {
                "match_id": "m2",
                "date": "2024-01-16",
                "team_1": "FaZe",
                "team_2": "G2",
                "map_winner": "",  # no winner recorded
                "_map": "de_dust2",
                "result_1": "15",
                "result_2": "15",
                "rank_1": "",
                "rank_2": "",
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

    def test_actual_kaggle_result_columns_are_mapped(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        """The real Kaggle results.csv schema uses _map/result_1/result_2."""
        csv_file = tmp_path / "results.csv"
        csv_file.write_text(
            "date,team_1,team_2,_map,result_1,result_2,map_winner,match_id\n"
            "2020-03-18,Recon 5,TeamOne,Dust2,0,16,2,2340454\n",
            encoding="utf-8",
        )

        matches = ingester.csv_to_matches(csv_file)

        assert len(matches) == 1
        assert matches[0].team_a_id == "Recon 5"
        assert matches[0].team_b_id == "TeamOne"
        assert matches[0].winner_id == "TeamOne"
        assert matches[0].played_at == "2020-03-18"
        assert matches[0].map_name == "Dust2"
        assert matches[0].score_a == 0
        assert matches[0].score_b == 16

    def test_kaggle_rank_columns_are_mapped(
        self, ingester: KaggleBootstrapIngester, standard_csv: Path
    ) -> None:
        """Kaggle rank_1/rank_2 should feed upset features when Liquipedia is absent."""
        matches = ingester.csv_to_matches(standard_csv)

        assert matches[0].team_a_ranking == 2
        assert matches[0].team_b_ranking == 1

    def test_players_csv_maps_to_kaggle_player_records(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "players.csv"
        csv_file.write_text(
            "date,player_name,team,opponent,country,player_id,match_id,event_id,"
            "event_name,best_of,map_1,map_2,map_3,kills,assists,deaths,hs,"
            "flash_assists,kast,kddiff,adr,fkdiff,rating\n"
            "2020-02-26,Brehze,Evil Geniuses,Liquid,United States,9136,2339385,"
            "4901,IEM Katowice 2020,3,Overpass,Nuke,Inferno,57,14,61,29,0.0,"
            "71.1,-4,79.9,0,1.04\n",
            encoding="utf-8",
        )

        players = ingester.csv_to_players(csv_file)

        assert players == [
            {
                "source": "kaggle",
                "player_id": "9136",
                "display_name": "Brehze",
                "team_id": "Evil Geniuses",
                "opponent_id": "Liquid",
                "country": "United States",
                "match_id": "2339385",
                "event_id": "4901",
                "event_name": "IEM Katowice 2020",
                "best_of": 3,
                "map_1": "Overpass",
                "map_2": "Nuke",
                "map_3": "Inferno",
                "kills": 57,
                "assists": 14,
                "deaths": 61,
                "headshots": 29,
                "flash_assists": 0.0,
                "kast": 71.1,
                "kd_diff": -4,
                "adr": 79.9,
                "fk_diff": 0,
                "rating": 1.04,
                "recorded_at": "2020-02-26",
            }
        ]

    def test_picks_csv_maps_to_map_veto_records(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "picks.csv"
        csv_file.write_text(
            "date,team_1,team_2,inverted_teams,match_id,event_id,best_of,system,"
            "t1_removed_1,t1_removed_2,t1_removed_3,t2_removed_1,t2_removed_2,"
            "t2_removed_3,t1_picked_1,t2_picked_1,left_over\n"
            "2020-03-18,TeamOne,Recon 5,1,2340454,5151,3,123412,Vertigo,Train,"
            "0.0,Nuke,Overpass,0.0,Dust2,Inferno,Mirage\n",
            encoding="utf-8",
        )

        vetoes = ingester.csv_to_map_vetoes(csv_file)

        assert vetoes[0]["source"] == "kaggle"
        assert vetoes[0]["team_a_id"] == "TeamOne"
        assert vetoes[0]["team_b_id"] == "Recon 5"
        assert vetoes[0]["inverted_teams"] is True
        assert vetoes[0]["t1_removed_1"] == "Vertigo"
        assert vetoes[0]["left_over"] == "Mirage"

    def test_economy_csv_maps_round_columns_to_json(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "economy.csv"
        csv_file.write_text(
            "date,match_id,event_id,team_1,team_2,best_of,_map,t1_start,t2_start,"
            "1_t1,1_t2,1_winner,2_t1,2_t2,2_winner\n"
            "2020-03-01,2339402,4901,G2,Natus Vincere,5,Nuke,t,ct,4350.0,"
            "4250.0,2.0,1100.0,20250.0,2.0\n",
            encoding="utf-8",
        )

        economy = ingester.csv_to_economy(csv_file)
        rounds = json.loads(economy[0]["rounds_json"])

        assert economy[0]["source"] == "kaggle"
        assert economy[0]["map_name"] == "Nuke"
        assert rounds == [
            {
                "round": 1,
                "team_a_economy": 4350.0,
                "team_b_economy": 4250.0,
                "winner": 2,
            },
            {
                "round": 2,
                "team_a_economy": 1100.0,
                "team_b_economy": 20250.0,
                "winner": 2,
            },
        ]

    def test_best_of_numeric_prefix_is_parsed(self, ingester: KaggleBootstrapIngester) -> None:
        """Kaggle has dirty best_of values like 3(LAN); keep the numeric prefix."""
        assert ingester._parse_optional_int("3(LAN)") == 3
        assert ingester._parse_optional_int("1(Online)") == 1
        assert ingester._parse_optional_int("of") is None

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

    def test_ingest_players_csv_file_uses_players_prefix(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "players.csv"
        csv_file.write_text(
            "date,player_name,player_id,match_id\n2024-01-01,donk,p1,m1\n",
            encoding="utf-8",
        )

        with patch("cs2_analytics.ingestion.kaggle.write_parquet_to_s3") as mock_write:
            count = ingester.ingest_players_csv_file(csv_file, date(2024, 1, 20))

        assert count == 1
        assert mock_write.call_args.kwargs["key"].startswith("raw/kaggle/players/")

    def test_ingest_map_vetoes_csv_file_uses_map_vetoes_prefix(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "picks.csv"
        csv_file.write_text(
            "date,team_1,team_2,match_id\n2024-01-01,A,B,m1\n",
            encoding="utf-8",
        )

        with patch("cs2_analytics.ingestion.kaggle.write_parquet_to_s3") as mock_write:
            count = ingester.ingest_map_vetoes_csv_file(csv_file, date(2024, 1, 20))

        assert count == 1
        assert mock_write.call_args.kwargs["key"].startswith("raw/kaggle/map_vetoes/")

    def test_ingest_economy_csv_file_uses_economy_prefix(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "economy.csv"
        csv_file.write_text(
            "date,match_id,team_1,team_2\n2024-01-01,m1,A,B\n",
            encoding="utf-8",
        )

        with patch("cs2_analytics.ingestion.kaggle.write_parquet_to_s3") as mock_write:
            count = ingester.ingest_economy_csv_file(csv_file, date(2024, 1, 20))

        assert count == 1
        assert mock_write.call_args.kwargs["key"].startswith("raw/kaggle/economy/")


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
        (tmp_path / "results.csv").write_text("date,team_1,team_2\n2024-01-01,A,B\n")
        with (
            patch.object(ingester, "setup_kaggle_credentials"),
            patch.object(ingester, "download_dataset", return_value=tmp_path),
            patch.object(ingester, "ingest_csv_file", return_value=5),
        ):
            total = ingester.download_and_ingest("u", "k", date(2024, 1, 1))
        assert total == 5

    def test_download_and_ingest_routes_each_supported_csv(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        for name in ["results.csv", "players.csv", "picks.csv", "economy.csv"]:
            (tmp_path / name).write_text("date,team_1,team_2\n2024-01-01,A,B\n")

        with (
            patch.object(ingester, "setup_kaggle_credentials"),
            patch.object(ingester, "download_dataset", return_value=tmp_path),
            patch.object(ingester, "ingest_csv_file", return_value=5) as mock_matches,
            patch.object(ingester, "ingest_players_csv_file", return_value=7) as mock_players,
            patch.object(ingester, "ingest_map_vetoes_csv_file", return_value=11) as mock_vetoes,
            patch.object(ingester, "ingest_economy_csv_file", return_value=13) as mock_economy,
        ):
            total = ingester.download_and_ingest("u", "k", date(2024, 1, 1))

        assert total == 36
        expected = call(date(2024, 1, 1))
        mock_matches.assert_called_once_with(tmp_path / "results.csv", expected.args[0])
        mock_players.assert_called_once_with(tmp_path / "players.csv", expected.args[0])
        mock_vetoes.assert_called_once_with(tmp_path / "picks.csv", expected.args[0])
        mock_economy.assert_called_once_with(tmp_path / "economy.csv", expected.args[0])

    def test_returns_zero_when_no_csvs(
        self, ingester: KaggleBootstrapIngester, tmp_path: Path
    ) -> None:
        with (
            patch.object(ingester, "setup_kaggle_credentials"),
            patch.object(ingester, "download_dataset", return_value=tmp_path),
        ):
            total = ingester.download_and_ingest("u", "k", date(2024, 1, 1))
        assert total == 0
