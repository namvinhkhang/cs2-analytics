"""Kaggle historical CSV bootstrap ingester for CS2 analytics pipeline.

Downloads the HLTV professional match dataset from Kaggle, converts CSV rows
to canonical Match objects, serialises to Parquet, and uploads to S3 under the
same raw/kaggle/matches/ prefix layout used by the live API clients.

This is a one-time bootstrap operation — callers should use bootstrap_kaggle.py
or call download_and_ingest() directly.

NOTE: `import kaggle` is deferred to inside download_dataset() because the
kaggle package reads ~/.kaggle/kaggle.json at import time.  Importing at module
level would raise FileNotFoundError before setup_kaggle_credentials() has run.
"""

from __future__ import annotations

import csv
import json
import re
import stat
from datetime import date
from pathlib import Path
from typing import Any

import structlog

from cs2_analytics.models.canonical import Match
from cs2_analytics.utils.parquet import (
    KAGGLE_ECONOMY_SCHEMA,
    KAGGLE_MAP_VETO_SCHEMA,
    KAGGLE_PLAYER_SCHEMA,
    MATCH_SCHEMA,
    models_to_records,
)
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

# Module-level structured logger
logger = structlog.get_logger()


class KaggleBootstrapIngester:
    """One-time historical data bootstrap from Kaggle CSV datasets.

    Writes through the same Parquet/S3 path as live API clients so
    downstream dbt models see a uniform raw/ prefix layout.

    Default dataset: mateusdmachado/csgo-professional-matches
    Expected result CSV columns: match_id (or row index), date, team_1,
    team_2, _map, result_1, result_2, and map_winner. Extra columns are
    silently ignored.
    """

    DEFAULT_DATASET = "mateusdmachado/csgo-professional-matches"
    DEFAULT_DOWNLOAD_PATH = Path("/tmp/cs2_kaggle_data")

    def __init__(self, bucket: str, region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._region = region

    def setup_kaggle_credentials(self, username: str, key: str) -> None:
        """Write Kaggle credentials to ~/.kaggle/kaggle.json.

        Required before any kaggle.api calls.
        Sets file permissions to 600 (owner read/write only) as required by
        the kaggle CLI — it refuses credentials with looser permissions.
        """
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        creds_path = kaggle_dir / "kaggle.json"
        creds_path.write_text(
            json.dumps({"username": username, "key": key}),
            encoding="utf-8",
        )
        # chmod 600: owner read + write only
        creds_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        logger.info("kaggle_credentials_written", path=str(creds_path))

    def download_dataset(
        self,
        dataset_slug: str = DEFAULT_DATASET,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
    ) -> Path:
        """Download and unzip Kaggle dataset to download_path.

        Returns the path containing the extracted CSV files.
        Requires setup_kaggle_credentials() to have been called first.

        kaggle is imported here (not at module top) because it reads
        ~/.kaggle/kaggle.json at import time — credentials must exist first.
        """
        import kaggle  # type: ignore[import-untyped]  # deferred import — credentials must be set up first

        download_path.mkdir(parents=True, exist_ok=True)
        kaggle.api.authenticate()
        kaggle.api.dataset_download_files(
            dataset=dataset_slug,
            path=str(download_path),
            unzip=True,
        )
        logger.info(
            "kaggle_dataset_downloaded",
            dataset=dataset_slug,
            path=str(download_path),
        )
        return download_path

    def csv_to_matches(self, csv_path: Path) -> list[Match]:
        """Parse a CSV file and map rows to canonical Match objects.

        Column name mapping (flexible — handles multiple naming conventions):
        - match_id:  "match_id", fallback to "kaggle_{stem}_{row_index}"
        - team_a_id: "team_1", "team_a", "team1"
        - team_b_id: "team_2", "team_b", "team2"
        - winner_id: "map_winner", "match_winner", "winner", "team_winner"
        - played_at: "date" (any ISO-compatible format), fallback "unknown"
        - map_name:  "_map", "map", "map_name"

        Rows with blank team IDs are skipped with a debug log.
        Rows that fail Match validation are skipped with a warning log.
        """
        matches: list[Match] = []

        # utf-8-sig handles BOM (byte order mark) in Windows-exported CSVs
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                team_a = self._get(row, "team_1", "team_a", "team1")
                team_b = self._get(row, "team_2", "team_b", "team2")

                # Skip rows where either team is missing — cannot form a valid match
                if not team_a or not team_b:
                    logger.debug("csv_row_skipped_missing_teams", row_index=idx)
                    continue

                match_id = self._get(row, "match_id") or f"kaggle_{csv_path.stem}_{idx}"
                winner_raw = self._get(row, "map_winner", "match_winner", "winner", "team_winner")
                winner_id = self._normalize_winner_id(winner_raw, team_a, team_b)
                played_at = self._get(row, "date") or "unknown"
                map_name = self._get(row, "_map", "map", "map_name")

                # Extract map win scores if available (Kaggle CSV columns)
                score_a_raw = self._get(
                    row,
                    "result_1",
                    "_map_wins_team_1",
                    "score_team_1",
                    "t1_score",
                )
                score_b_raw = self._get(
                    row,
                    "result_2",
                    "_map_wins_team_2",
                    "score_team_2",
                    "t2_score",
                )
                score_a_val = self._parse_optional_int(score_a_raw)
                score_b_val = self._parse_optional_int(score_b_raw)
                team_a_ranking = self._parse_optional_int(
                    self._get(row, "rank_1", "team_a_ranking")
                )
                team_b_ranking = self._parse_optional_int(
                    self._get(row, "rank_2", "team_b_ranking")
                )
                is_overtime_val: bool | None = None
                if score_a_val is not None and score_b_val is not None:
                    # Overtime when both teams exceed regulation limit (MR15: both > 15)
                    is_overtime_val = score_a_val > 15 and score_b_val > 15

                try:
                    matches.append(
                        Match(
                            match_id=match_id,
                            source="kaggle",
                            team_a_id=team_a,
                            team_b_id=team_b,
                            winner_id=winner_id,
                            played_at=played_at,
                            map_name=map_name,
                            score_a=score_a_val,
                            score_b=score_b_val,
                            is_overtime=is_overtime_val,
                            team_a_ranking=team_a_ranking,
                            team_b_ranking=team_b_ranking,
                        )
                    )
                except Exception:
                    # Row-level guard: log and continue to keep bootstrap resilient
                    # to malformed rows without aborting the entire CSV file.
                    logger.warning("csv_row_parse_failed", row_index=idx)
                    continue

        return matches

    def csv_to_players(self, csv_path: Path) -> list[dict[str, Any]]:
        """Parse Kaggle players.csv rows into typed player-stat records."""
        players: list[dict[str, Any]] = []
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                player_name = self._get(row, "player_name", "display_name") or "unknown"
                player_id = self._get(row, "player_id") or f"kaggle_player_{csv_path.stem}_{idx}"
                players.append(
                    {
                        "source": "kaggle",
                        "player_id": player_id,
                        "display_name": player_name,
                        "team_id": self._get(row, "team"),
                        "opponent_id": self._get(row, "opponent"),
                        "country": self._get(row, "country"),
                        "match_id": self._get(row, "match_id"),
                        "event_id": self._get(row, "event_id"),
                        "event_name": self._get(row, "event_name"),
                        "best_of": self._parse_optional_int(self._get(row, "best_of")),
                        "map_1": self._get(row, "map_1"),
                        "map_2": self._get(row, "map_2"),
                        "map_3": self._get(row, "map_3"),
                        "kills": self._parse_optional_int(self._get(row, "kills")),
                        "assists": self._parse_optional_int(self._get(row, "assists")),
                        "deaths": self._parse_optional_int(self._get(row, "deaths")),
                        "headshots": self._parse_optional_int(self._get(row, "hs", "headshots")),
                        "flash_assists": self._parse_optional_float(
                            self._get(row, "flash_assists")
                        ),
                        "kast": self._parse_optional_float(self._get(row, "kast")),
                        "kd_diff": self._parse_optional_int(self._get(row, "kddiff", "kd_diff")),
                        "adr": self._parse_optional_float(self._get(row, "adr")),
                        "fk_diff": self._parse_optional_int(self._get(row, "fkdiff", "fk_diff")),
                        "rating": self._parse_optional_float(self._get(row, "rating")),
                        "recorded_at": self._get(row, "date"),
                    }
                )
        return players

    def csv_to_map_vetoes(self, csv_path: Path) -> list[dict[str, Any]]:
        """Parse Kaggle picks.csv rows into map veto records."""
        vetoes: list[dict[str, Any]] = []
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                match_id = self._get(row, "match_id") or f"kaggle_veto_{csv_path.stem}_{idx}"
                vetoes.append(
                    {
                        "source": "kaggle",
                        "match_id": match_id,
                        "event_id": self._get(row, "event_id"),
                        "played_at": self._get(row, "date"),
                        "team_a_id": self._get(row, "team_1", "team_a", "team1"),
                        "team_b_id": self._get(row, "team_2", "team_b", "team2"),
                        "inverted_teams": self._parse_optional_bool(
                            self._get(row, "inverted_teams")
                        ),
                        "best_of": self._parse_optional_int(self._get(row, "best_of")),
                        "system": self._get(row, "system"),
                        "t1_removed_1": self._clean_map_value(self._get(row, "t1_removed_1")),
                        "t1_removed_2": self._clean_map_value(self._get(row, "t1_removed_2")),
                        "t1_removed_3": self._clean_map_value(self._get(row, "t1_removed_3")),
                        "t2_removed_1": self._clean_map_value(self._get(row, "t2_removed_1")),
                        "t2_removed_2": self._clean_map_value(self._get(row, "t2_removed_2")),
                        "t2_removed_3": self._clean_map_value(self._get(row, "t2_removed_3")),
                        "t1_picked_1": self._clean_map_value(self._get(row, "t1_picked_1")),
                        "t2_picked_1": self._clean_map_value(self._get(row, "t2_picked_1")),
                        "left_over": self._clean_map_value(self._get(row, "left_over")),
                    }
                )
        return vetoes

    def csv_to_economy(self, csv_path: Path) -> list[dict[str, Any]]:
        """Parse Kaggle economy.csv rows with round details stored as JSON."""
        economy_rows: list[dict[str, Any]] = []
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                match_id = self._get(row, "match_id") or f"kaggle_economy_{csv_path.stem}_{idx}"
                rounds = []
                for round_number in range(1, 31):
                    team_a_economy = self._parse_optional_float(
                        self._get(row, f"{round_number}_t1")
                    )
                    team_b_economy = self._parse_optional_float(
                        self._get(row, f"{round_number}_t2")
                    )
                    winner = self._parse_optional_int(self._get(row, f"{round_number}_winner"))
                    if team_a_economy is None and team_b_economy is None and winner is None:
                        continue
                    rounds.append(
                        {
                            "round": round_number,
                            "team_a_economy": team_a_economy,
                            "team_b_economy": team_b_economy,
                            "winner": winner,
                        }
                    )

                economy_rows.append(
                    {
                        "source": "kaggle",
                        "match_id": match_id,
                        "event_id": self._get(row, "event_id"),
                        "played_at": self._get(row, "date"),
                        "team_a_id": self._get(row, "team_1", "team_a", "team1"),
                        "team_b_id": self._get(row, "team_2", "team_b", "team2"),
                        "best_of": self._parse_optional_int(self._get(row, "best_of")),
                        "map_name": self._get(row, "_map", "map", "map_name"),
                        "team_a_start_side": self._get(row, "t1_start"),
                        "team_b_start_side": self._get(row, "t2_start"),
                        "rounds_json": json.dumps(rounds, sort_keys=True),
                    }
                )
        return economy_rows

    @staticmethod
    def _normalize_winner_id(winner_raw: str | None, team_a: str, team_b: str) -> str | None:
        """Map Kaggle's 1/2 winner encoding to the canonical team identifier."""
        if winner_raw is None:
            return None
        normalized = winner_raw.strip().lower()
        if normalized in {"1", "team_1", "team_a"}:
            return team_a
        if normalized in {"2", "team_2", "team_b"}:
            return team_b
        return winner_raw

    @staticmethod
    def _get(row: dict[str, str], *keys: str, default: str | None = None) -> str | None:
        """Return first non-empty value found among the given column keys."""
        for key in keys:
            val = row.get(key, "").strip()
            if val:
                return val
        return default

    @staticmethod
    def _clean_map_value(value: str | None) -> str | None:
        """Treat Kaggle's numeric placeholders as missing map names."""
        if value is None or value in {"0", "0.0", "nan", "NaN"}:
            return None
        return value

    @staticmethod
    def _parse_optional_int(value: str | None) -> int | None:
        """Parse optional integer CSV values without aborting a full bootstrap."""
        if value is None:
            return None
        try:
            return int(float(value))
        except ValueError:
            match = re.match(r"^\s*(\d+)", value)
            if match is not None:
                return int(match.group(1))
            return None

    @staticmethod
    def _parse_optional_float(value: str | None) -> float | None:
        """Parse optional float CSV values without aborting a full bootstrap."""
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            logger.warning("csv_float_parse_failed", value=value)
            return None

    @staticmethod
    def _parse_optional_bool(value: str | None) -> bool | None:
        """Parse Kaggle's 1/0 boolean-ish fields."""
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized in {"1", "1.0", "true", "yes"}:
            return True
        if normalized in {"0", "0.0", "false", "no"}:
            return False
        return None

    def ingest_csv_file(self, csv_path: Path, ingest_date: date) -> int:
        """Parse one CSV, write Parquet to S3, return count of matches written.

        Uses the CSV file's stem as part of the S3 filename so multiple CSV
        files in the same dataset download don't overwrite each other.
        """
        matches = self.csv_to_matches(csv_path)
        if not matches:
            logger.warning("csv_produced_no_matches", path=str(csv_path))
            return 0

        y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
        # Include CSV stem in filename to avoid collision when multiple CSVs are present
        filename = f"{csv_path.stem}.parquet"
        write_parquet_to_s3(
            records=models_to_records(matches),
            schema=MATCH_SCHEMA,
            bucket=self._bucket,
            key=build_s3_key("kaggle", "matches", y, m, d, filename=filename),
            region=self._region,
        )
        logger.info("kaggle_csv_ingested", file=csv_path.name, count=len(matches))
        return len(matches)

    def ingest_players_csv_file(self, csv_path: Path, ingest_date: date) -> int:
        """Parse players.csv, write typed player-stat Parquet to S3, return row count."""
        players = self.csv_to_players(csv_path)
        return self._write_records(
            records=players,
            schema=KAGGLE_PLAYER_SCHEMA,
            entity_type="players",
            filename=csv_path.with_suffix(".parquet").name,
            ingest_date=ingest_date,
        )

    def ingest_map_vetoes_csv_file(self, csv_path: Path, ingest_date: date) -> int:
        """Parse picks.csv, write map-veto Parquet to S3, return row count."""
        vetoes = self.csv_to_map_vetoes(csv_path)
        return self._write_records(
            records=vetoes,
            schema=KAGGLE_MAP_VETO_SCHEMA,
            entity_type="map_vetoes",
            filename=csv_path.with_suffix(".parquet").name,
            ingest_date=ingest_date,
        )

    def ingest_economy_csv_file(self, csv_path: Path, ingest_date: date) -> int:
        """Parse economy.csv, write economy Parquet to S3, return row count."""
        economy_rows = self.csv_to_economy(csv_path)
        return self._write_records(
            records=economy_rows,
            schema=KAGGLE_ECONOMY_SCHEMA,
            entity_type="economy",
            filename=csv_path.with_suffix(".parquet").name,
            ingest_date=ingest_date,
        )

    def _write_records(
        self,
        *,
        records: list[dict[str, Any]],
        schema: Any,
        entity_type: str,
        filename: str,
        ingest_date: date,
    ) -> int:
        """Write a typed Kaggle raw record batch to its entity-specific S3 prefix."""
        if not records:
            logger.warning("csv_produced_no_records", entity_type=entity_type)
            return 0

        y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
        write_parquet_to_s3(
            records=records,
            schema=schema,
            bucket=self._bucket,
            key=build_s3_key("kaggle", entity_type, y, m, d, filename=filename),
            region=self._region,
        )
        logger.info("kaggle_csv_ingested", entity_type=entity_type, count=len(records))
        return len(records)

    def download_and_ingest(
        self,
        username: str,
        key: str,
        ingest_date: date,
        *,
        dataset_slug: str = DEFAULT_DATASET,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
    ) -> int:
        """Full bootstrap pipeline: credentials → download → parse CSVs → S3.

        Returns the total number of Match records written to S3 across all CSVs.
        """
        self.setup_kaggle_credentials(username, key)
        data_path = self.download_dataset(dataset_slug, download_path)

        csv_routes = [
            ("results.csv", self.ingest_csv_file),
            ("players.csv", self.ingest_players_csv_file),
            ("picks.csv", self.ingest_map_vetoes_csv_file),
            ("economy.csv", self.ingest_economy_csv_file),
        ]
        available_routes = [
            (data_path / filename, ingester)
            for filename, ingester in csv_routes
            if (data_path / filename).exists()
        ]
        if not available_routes:
            logger.warning("no_supported_csv_files_found", path=str(data_path))
            return 0

        total = 0
        for csv_path, ingester in available_routes:
            total += ingester(csv_path, ingest_date)

        logger.info(
            "kaggle_bootstrap_complete",
            total_records=total,
            files=len(available_routes),
        )
        return total
