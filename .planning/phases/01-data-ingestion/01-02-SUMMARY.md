---
phase: 01-data-ingestion
plan: 02
subsystem: utils
tags: [pyarrow, parquet, s3, boto3, hive-partitioning, snappy, tdd]

# Dependency graph
requires:
  - src/cs2_analytics/models/canonical.py (Match, Player, Team field contracts)
  - src/cs2_analytics/utils/config.py (settings.aws_s3_bucket, settings.aws_region — callers use these)
provides:
  - src/cs2_analytics/utils/parquet.py — MATCH_SCHEMA, PLAYER_SCHEMA, TEAM_SCHEMA, models_to_records()
  - src/cs2_analytics/utils/s3.py — write_parquet_to_s3(), build_s3_key()
affects: [02-ingestion-clients]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explicit pyarrow schema pattern — pa.field(name, type, nullable=True/False) prevents ArrowInvalid on all-None nullable columns (Pitfall 4)"
    - "BytesIO buffer pattern — pq.write_table to BytesIO, seek(0), getvalue() avoids temp files on disk"
    - "Hive partition key format — raw/{source}/{entity}/year={y}/month={mm}/day={dd}/ with zero-padded month/day for Athena compat"
    - "boto3 explicit region — region_name passed to boto3.client() so callers control endpoint"
    - "TDD RED-GREEN pattern — failing tests committed before each implementation"

key-files:
  created:
    - src/cs2_analytics/utils/parquet.py
    - src/cs2_analytics/utils/s3.py
    - tests/test_parquet.py
    - tests/test_s3.py
  modified: []

key-decisions:
  - "Callers pass bucket and region to write_parquet_to_s3() explicitly — module does not import settings, keeping it testable without .env"
  - "pa.int64() used for all integer fields (not pa.int32()) — forward-safe for large ELO and ranking values"
  - "structlog.info() called after successful put_object — avoids log noise for retried failures"

# Metrics
duration: 3min
completed: 2026-03-16
---

# Phase 1 Plan 02: S3 Upload and Parquet Serialization Utilities Summary

**Explicit pyarrow schemas for Match/Player/Team entities plus BytesIO+boto3 S3 upload utility with Hive-partitioned key builder — shared write path for all four ingestion clients.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-16T18:22:07Z
- **Completed:** 2026-03-16T18:24:47Z
- **Tasks:** 2/2
- **Files created:** 4

## Accomplishments

- MATCH_SCHEMA (7 fields), PLAYER_SCHEMA (13 fields), TEAM_SCHEMA (6 fields) defined with explicit nullable flags mirroring canonical models
- models_to_records() converts any list of Pydantic BaseModel instances to plain dicts via model_dump()
- build_s3_key() produces Hive-partitioned paths with zero-padded month/day — Athena partition projection compatible
- write_parquet_to_s3() serializes records to snappy-compressed Parquet via BytesIO buffer then calls boto3 put_object
- 53 total tests passing (29 original + 14 parquet + 10 s3); no pandas dependency anywhere in utils/

## Task Commits

Each task was committed atomically:

1. **TDD RED — parquet tests** - `9c18aa7` (test)
2. **Task 1: Parquet serialization utility** - `4170bb3` (feat)
3. **TDD RED — s3 tests** - `70bde56` (test)
4. **Task 2: S3 upload utility** - `fa1fd37` (feat)

## Files Created

- `src/cs2_analytics/utils/parquet.py` — MATCH_SCHEMA, PLAYER_SCHEMA, TEAM_SCHEMA, models_to_records()
- `src/cs2_analytics/utils/s3.py` — build_s3_key(), write_parquet_to_s3()
- `tests/test_parquet.py` — 14 tests: schema field counts, nullable flags, type assertions, round-trip Parquet buffer
- `tests/test_s3.py` — 10 tests: path builder formatting, mocked boto3 put_object, snappy compression, region propagation

## Function Signatures (for Wave 2 clients)

### parquet.py exports

```python
# Explicit pyarrow schemas — pass as schema= argument to pa.Table.from_pylist()
MATCH_SCHEMA: pa.Schema    # 7 fields: match_id, source, team_a_id, team_b_id, winner_id, played_at, map_name
PLAYER_SCHEMA: pa.Schema   # 13 fields: player_id, source, display_name, team_id, nationality, kills, deaths, adr, kd_ratio, kast, elo, match_id, recorded_at
TEAM_SCHEMA: pa.Schema     # 6 fields: team_id, source, name, region, world_ranking, ingested_at

def models_to_records(models: list[BaseModel]) -> list[dict[str, Any]]:
    """Convert Pydantic model list to plain dicts for pyarrow. Returns [] for empty input."""
```

### s3.py exports

```python
def build_s3_key(
    source: str,           # "faceit" | "liquipedia" | "pandascore" | "kaggle"
    entity_type: str,      # "matches" | "players" | "teams"
    year: int,
    month: int,
    day: int,
    filename: str = "data.parquet",
) -> str:
    """Returns: raw/{source}/{entity_type}/year={y}/month={mm}/day={dd}/{filename}"""

def write_parquet_to_s3(
    records: list[dict],   # output of models_to_records()
    schema: pa.Schema,     # MATCH_SCHEMA | PLAYER_SCHEMA | TEAM_SCHEMA
    bucket: str,           # settings.aws_s3_bucket
    key: str,              # output of build_s3_key()
    *,
    region: str = "us-east-1",  # settings.aws_region
) -> None:
    """Serializes to snappy Parquet in BytesIO, uploads via boto3 put_object. Idempotent."""
```

### Typical Wave 2 usage pattern

```python
from cs2_analytics.utils.config import settings
from cs2_analytics.utils.parquet import MATCH_SCHEMA, models_to_records
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3
from datetime import date

today = date.today()
records = models_to_records(canonical_matches)
key = build_s3_key("faceit", "matches", today.year, today.month, today.day)
write_parquet_to_s3(records, MATCH_SCHEMA, settings.aws_s3_bucket, key, region=settings.aws_region)
```

## pyarrow Schema Field Reference

### MATCH_SCHEMA

| Field | Type | Nullable |
|-------|------|----------|
| match_id | string | False |
| source | string | False |
| team_a_id | string | False |
| team_b_id | string | False |
| winner_id | string | True |
| played_at | string | False |
| map_name | string | True |

### PLAYER_SCHEMA

| Field | Type | Nullable |
|-------|------|----------|
| player_id | string | False |
| source | string | False |
| display_name | string | False |
| team_id | string | True |
| nationality | string | True |
| kills | int64 | True |
| deaths | int64 | True |
| adr | float64 | True |
| kd_ratio | float64 | True |
| kast | float64 | True |
| elo | int64 | True |
| match_id | string | True |
| recorded_at | string | False |

### TEAM_SCHEMA

| Field | Type | Nullable |
|-------|------|----------|
| team_id | string | False |
| source | string | False |
| name | string | False |
| region | string | True |
| world_ranking | int64 | True |
| ingested_at | string | False |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
