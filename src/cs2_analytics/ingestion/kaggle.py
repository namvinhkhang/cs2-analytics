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
import os
import stat
from datetime import date
from pathlib import Path
from typing import Any

import structlog

from cs2_analytics.models.canonical import Match
from cs2_analytics.utils.parquet import MATCH_SCHEMA, models_to_records
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

# Module-level structured logger
logger = structlog.get_logger()


class KaggleBootstrapIngester:
    """One-time historical data bootstrap from Kaggle CSV datasets.

    Writes through the same Parquet/S3 path as live API clients so
    downstream dbt models see a uniform raw/ prefix layout.

    Default dataset: mateusdmachado/csgo-professional-matches
    Expected CSV columns: match_id (or row index), date, team_1, team_2,
    map, map_winner (or winner), and various stats columns.
    Extra columns are silently ignored.
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
        import kaggle  # deferred import — credentials must be set up first

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
        - winner_id: "map_winner", "winner", "team_winner"
        - played_at: "date" (any ISO-compatible format), fallback "unknown"
        - map_name:  "map", "map_name"

        Rows with blank team IDs are skipped with a debug log.
        Rows that fail Match validation are skipped with a warning log.
        """
        matches: list[Match] = []

        def _get(row: dict[str, str], *keys: str, default: str | None = None) -> str | None:
            """Return first non-empty value found among the given column keys."""
            for key in keys:
                val = row.get(key, "").strip()
                if val:
                    return val
            return default

        # utf-8-sig handles BOM (byte order mark) in Windows-exported CSVs
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                team_a = _get(row, "team_1", "team_a", "team1")
                team_b = _get(row, "team_2", "team_b", "team2")

                # Skip rows where either team is missing — cannot form a valid match
                if not team_a or not team_b:
                    logger.debug("csv_row_skipped_missing_teams", row_index=idx)
                    continue

                match_id = _get(row, "match_id") or f"kaggle_{csv_path.stem}_{idx}"
                winner_id = _get(row, "map_winner", "winner", "team_winner")
                played_at = _get(row, "date") or "unknown"
                map_name = _get(row, "map", "map_name")

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
                        )
                    )
                except Exception:
                    # Row-level guard: log and continue to keep bootstrap resilient
                    # to malformed rows without aborting the entire CSV file.
                    logger.warning("csv_row_parse_failed", row_index=idx)
                    continue

        return matches

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

        csv_files = list(data_path.glob("*.csv"))
        if not csv_files:
            logger.warning("no_csv_files_found", path=str(data_path))
            return 0

        total = 0
        for csv_path in csv_files:
            total += self.ingest_csv_file(csv_path, ingest_date)

        logger.info(
            "kaggle_bootstrap_complete",
            total_records=total,
            files=len(csv_files),
        )
        return total
