---
phase: 01-data-ingestion
plan: 06
subsystem: ingestion
tags: [kaggle, csv, parquet, s3, bootstrap, tdd]

# Dependency graph
requires:
  - src/cs2_analytics/models/canonical.py (Match model)
  - src/cs2_analytics/utils/parquet.py (MATCH_SCHEMA, models_to_records)
  - src/cs2_analytics/utils/s3.py (build_s3_key, write_parquet_to_s3)
  - src/cs2_analytics/utils/config.py (settings.kaggle_username, settings.kaggle_key, settings.aws_s3_bucket)
provides:
  - src/cs2_analytics/ingestion/kaggle.py — KaggleBootstrapIngester class
  - scripts/bootstrap_kaggle.py — runnable one-time bootstrap script
affects: [02-dbt-transformation, ML-training-set-bootstrap]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred import pattern — import kaggle inside download_dataset() so credential file exists before package reads it at import time"
    - "utf-8-sig encoding for csv.open() — handles BOM in Windows-exported CSVs from the Kaggle dataset"
    - "Multi-key column helper _get(*keys) — tries team_1/team_a/team1 variants so one ingester handles all CSV schemas in the dataset"
    - "Row-level except Exception with continue — bootstrap must not abort entire CSV on a malformed row"
    - "CSV stem in Parquet filename — prevents S3 overwrite when multiple CSVs from same download are ingested"

key-files:
  created:
    - src/cs2_analytics/ingestion/kaggle.py
    - scripts/bootstrap_kaggle.py
    - scripts/__init__.py
    - tests/test_kaggle_ingester.py
  modified: []

key-decisions:
  - "kaggle import deferred inside download_dataset() — package reads ~/.kaggle/kaggle.json at import time, so credentials must be written first"
  - "sys.path.insert in bootstrap_kaggle.py — allows direct script execution without pip install -e ."
  - "Row-level except Exception only at csv_to_matches row loop — acceptable here to keep bootstrap resilient to malformed rows"

# Metrics
duration: 12min
completed: 2026-03-16
---

# Phase 1 Plan 06: Kaggle Bootstrap Ingester Summary

**KaggleBootstrapIngester downloads Kaggle CSV dataset and converts rows to canonical Match Parquet files under raw/kaggle/matches/ in S3 — same layout as live API clients.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-16T18:42:26Z
- **Completed:** 2026-03-16T18:54:32Z
- **Tasks:** 2/2
- **Files created:** 4

## Accomplishments

- KaggleBootstrapIngester class with 5 methods: setup_kaggle_credentials, download_dataset, csv_to_matches, ingest_csv_file, download_and_ingest
- setup_kaggle_credentials writes ~/.kaggle/kaggle.json with chmod 600 (required by kaggle CLI)
- csv_to_matches handles team_1/team_a/team1 and map_winner/winner/team_winner column variants via _get() helper
- Empty strings in winner/map columns are normalised to None so MATCH_SCHEMA nullable constraints are satisfied
- ingest_csv_file uses CSV stem as Parquet filename to prevent overwrite when multiple CSVs exist in same download
- bootstrap_kaggle.py reads all config from Settings (CS2_* env vars), prints human-readable completion summary
- 147 tests passing (122 pre-existing + 25 new Kaggle ingester tests)

## Task Commits

Each task was committed atomically:

1. **TDD RED — Kaggle ingester tests** - `c91eb90` (test)
2. **Task 1: KaggleBootstrapIngester** - `9933cea` (feat)
3. **Task 2: bootstrap script** - `8829af6` (feat)

## Files Created

- `src/cs2_analytics/ingestion/kaggle.py` — KaggleBootstrapIngester with full CSV-to-Parquet-to-S3 pipeline
- `scripts/bootstrap_kaggle.py` — runnable one-time bootstrap script
- `scripts/__init__.py` — empty package marker
- `tests/test_kaggle_ingester.py` — 25 tests covering all public methods

## Function Signatures

### KaggleBootstrapIngester

```python
class KaggleBootstrapIngester:
    DEFAULT_DATASET = "mateusdmachado/csgo-professional-matches"
    DEFAULT_DOWNLOAD_PATH = Path("/tmp/cs2_kaggle_data")

    def __init__(self, bucket: str, region: str = "us-east-1") -> None: ...

    def setup_kaggle_credentials(self, username: str, key: str) -> None:
        """Write ~/.kaggle/kaggle.json with chmod 600."""

    def download_dataset(
        self,
        dataset_slug: str = DEFAULT_DATASET,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
    ) -> Path:
        """Download and unzip Kaggle dataset. Returns path with extracted CSVs."""

    def csv_to_matches(self, csv_path: Path) -> list[Match]:
        """Parse CSV, map rows to canonical Match objects with source='kaggle'."""

    def ingest_csv_file(self, csv_path: Path, ingest_date: date) -> int:
        """Parse one CSV, write Parquet to S3, return match count."""

    def download_and_ingest(
        self,
        username: str,
        key: str,
        ingest_date: date,
        *,
        dataset_slug: str = DEFAULT_DATASET,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
    ) -> int:
        """Full bootstrap pipeline. Returns total records written."""
```

## CSV Column Name Mapping

| Canonical Field | Columns tried (in order)           | Fallback               |
|----------------|------------------------------------|------------------------|
| match_id       | match_id                           | kaggle_{stem}_{index}  |
| team_a_id      | team_1, team_a, team1              | skip row               |
| team_b_id      | team_2, team_b, team2              | skip row               |
| winner_id      | map_winner, winner, team_winner    | None                   |
| played_at      | date                               | "unknown"              |
| map_name       | map, map_name                      | None                   |

## Default Dataset

`mateusdmachado/csgo-professional-matches` — HLTV historical CS:GO/CS2 professional match results.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
