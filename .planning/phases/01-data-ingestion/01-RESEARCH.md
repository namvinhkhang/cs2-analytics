# Phase 1: Data Ingestion - Research

**Researched:** 2026-03-16
**Domain:** Python async API ingestion, Parquet/S3 serialization, Pydantic v2 validation
**Confidence:** HIGH (stack is locked; findings verified against official docs and multiple sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Project Layout & Config Management**
- Package layout: `src/cs2_analytics/` with `ingestion/`, `models/`, `utils/` subdirs — standard src layout compatible with uv + pyproject.toml
- Config: `pydantic-settings` with `.env` file and a `Settings` class — type-safe, validated at startup, all API keys and AWS creds loaded here
- HTTP client: `httpx` with `AsyncClient` — modern, async-capable, consistent API across all four source clients
- Retry/backoff: `tenacity` library — `@retry` decorator with exponential backoff, configurable per-client via constants

**Ingestion Client Design**
- Abstract base: `BaseAPIClient` ABC with `get()`, `paginate()`, and rate-limit hook — each source (Liquipedia, FACEIT, PandaScore) subclasses it
- Rate limiting: `asyncio.Semaphore` + per-client sleep tuned to each API's limit (FACEIT ~1 req/s, PandaScore ~0.27 req/s, Liquipedia ~10 req/s)
- Kaggle bootstrap: Dedicated `KaggleBootstrapIngester` class that reads local CSV and writes to same Parquet/S3 format as live clients — keeps pipeline uniform
- Logging: `structlog` for JSON-structured logs — pairs well with Airflow log capture in Phase 2

**S3 & Parquet Output Strategy**
- S3 path partitioning: `raw/{source}/{entity_type}/year={y}/month={m}/day={d}/` — Hive-compatible, works with Athena and dbt external table scanning
- Parquet writer: `pyarrow` directly — lightweight, no pandas dependency for pure ingestion layer
- Write mode: Overwrite same S3 key on re-ingestion runs — idempotent daily runs, safe for Airflow retries
- S3 client: `boto3` directly — explicit, minimal extra dependencies

**Pydantic Models & Test Strategy**
- Model scope: Shared `Match`, `Player`, `Team` canonical models + per-source raw models (e.g., `FACEITMatch`, `PandaScoreMatch`) that map to shared — clean source/domain separation
- Validation strictness: `model_config = ConfigDict(extra="ignore")` — tolerate undocumented API fields, strictly validate known fields
- pytest mocking: `respx` library — httpx-native request mocker, cleaner than `responses` for async clients
- Fixtures: `tests/fixtures/{source}/` directories with `.json` sample API response files — kept separate from test logic

### Claude's Discretion
- Internal utilities (S3 path builder, Parquet schema helpers) — implementation details at Claude's discretion
- Exact Pydantic field names for each source model — follow API response field naming with snake_case conversion
- pyproject.toml dependency grouping (dev vs runtime)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ING-01 | Ingest team, player, tournament, and placement data from Liquipedia API v3 | Liquipedia REST API covers Teams, Players, Tournaments, Placements, Matches data types; requires API key; free tier 1,000 req/hour |
| ING-02 | Ingest per-match statistics (kills, deaths, ADR, K/D, KAST, ELO) from FACEIT API | FACEIT Data API v4 has match details endpoint with per-player stats; ~1 req/s safe rate on free key |
| ING-03 | Ingest tier-1 pro match results and player stats from PandaScore API | PandaScore REST API covers CS2 under `counterstrike` game ID; free tier 1,000 req/hour (0.27 req/s) |
| ING-04 | Load historical match data from Kaggle CSV as one-time bootstrap | kaggle Python package (`kaggle.api.dataset_download_files`) handles programmatic download; local CSV read then same Parquet/S3 serialization path |
| ING-05 | Serialize all raw data to Parquet with pyarrow and upload to S3 under `raw/` prefix partitioned by date | `pq.write_table(table, buffer)` + `s3.put_object(Body=buf.getvalue())` pattern; or `pyarrow.fs.S3FileSystem` directly |
| ING-06 | All API clients implement retry logic, rate limiting, and exponential backoff | tenacity `@retry` with `wait_exponential_jitter`, `retry_if_exception_type`, `before_sleep_log`; asyncio.Semaphore for concurrency cap |
| ING-07 | pytest test suite covers all ingestion clients with mocked HTTP responses | respx `respx_mock` fixture or `@respx.mock` decorator; pytest-asyncio for async tests |
| ING-08 | Pydantic data models defined for Match, Player, and Team entities | Pydantic v2 BaseModel with `ConfigDict(extra="ignore")`; per-source raw models map to canonical shared models |
</phase_requirements>

---

## Summary

Phase 1 builds a Python-native ELT ingestion layer that pulls CS2 match data from four sources and lands it in AWS S3 as partitioned Parquet files. The stack is entirely locked: `httpx` + `tenacity` for resilient async HTTP, `pydantic v2` for schema validation, `pyarrow` for Parquet serialization, `boto3` for S3 uploads, and `structlog` for JSON-structured logs.

The key design tension is that each of the three live APIs has different rate limits (FACEIT ~1 req/s, PandaScore ~0.27 req/s from 1,000/hour free tier, Liquipedia ~1,000/hour free tier) and different authentication schemes. The `BaseAPIClient` ABC with per-client `asyncio.Semaphore` constants cleanly isolates these differences while sharing retry/serialization logic.

The Kaggle bootstrap path needs special attention: the `kaggle` Python package requires `~/.kaggle/kaggle.json` credentials at runtime; the `KaggleBootstrapIngester` reads local CSV files and routes through the same Parquet/S3 write path as live clients, ensuring schema consistency for downstream dbt models.

**Primary recommendation:** Implement the `BaseAPIClient` ABC first, then build the three live-source subclasses and the Kaggle bootstrapper against it. Write all fixture JSON files before writing tests, then wire respx mocks to those fixtures. The Parquet/S3 util and Pydantic models can be scaffolded in parallel with the client implementations.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.27 | Async HTTP client for all API calls | Modern async API, consistent with respx mocking, replaces requests for async workloads |
| tenacity | >=9.0 | Retry decorator with exponential backoff | Battle-tested, works natively with async, supports result-based retry (e.g., on HTTP 429) |
| pydantic | v2 (>=2.7) | Data validation for API response models | v2 is ~17x faster than v1, ConfigDict API is idiomatic for per-model config |
| pydantic-settings | >=2.3 | Settings management via .env file | Separate package in v2; provides SettingsConfigDict with env_file, env_prefix support |
| pyarrow | >=16.0 | Parquet serialization without pandas | Lightweight, schema-explicit, works with S3FileSystem directly |
| boto3 | >=1.35 | AWS S3 uploads | Official AWS SDK; put_object with BytesIO body covers the overwrite-on-rerun pattern |
| structlog | >=24.0 | JSON-structured logging | Contextual binding, dev/prod renderer switching, pairs with Airflow log capture |
| kaggle | >=1.6 | Kaggle dataset download CLI/API | Official package; `api.dataset_download_files()` handles auth and unzipping |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0 | Test runner | All unit and integration tests |
| pytest-asyncio | >=0.23 | Async test support | Required for async client tests |
| respx | >=0.21 | httpx-native request mocking | Test all AsyncClient calls without live API access |
| python-dotenv | >=1.0 | .env file parsing (pydantic-settings dep) | Auto-loaded by pydantic-settings |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pyarrow direct | aws-sdk-pandas (awswrangler) | awswrangler adds pandas + heavy deps; overkill for pure ingestion with no transformation |
| boto3 BytesIO put_object | pyarrow.fs.S3FileSystem | S3FileSystem is cleaner for large datasets; BytesIO + put_object is simpler and sufficient for daily partition writes |
| asyncio.Semaphore for rate limit | aiohttp-based rate limiters | Semaphore is stdlib, no extra dep; sufficient for simple per-second rate control |
| respx | pytest-httpx | respx has more expressive route matching and async context manager support |

**Installation:**
```bash
uv add httpx tenacity "pydantic>=2.7" "pydantic-settings>=2.3" pyarrow boto3 structlog kaggle
uv add --dev pytest pytest-asyncio respx
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
└── cs2_analytics/
    ├── ingestion/
    │   ├── __init__.py
    │   ├── base.py           # BaseAPIClient ABC
    │   ├── liquipedia.py     # LiquipediaClient(BaseAPIClient)
    │   ├── faceit.py         # FACEITClient(BaseAPIClient)
    │   ├── pandascore.py     # PandaScoreClient(BaseAPIClient)
    │   └── kaggle_bootstrap.py  # KaggleBootstrapIngester
    ├── models/
    │   ├── __init__.py
    │   ├── canonical.py      # Match, Player, Team shared models
    │   ├── liquipedia.py     # LiquipediaMatch, LiquipediaTeam, etc.
    │   ├── faceit.py         # FACEITMatch, FACEITPlayer, etc.
    │   └── pandascore.py     # PandaScoreMatch, PandaScorePlayer, etc.
    └── utils/
        ├── __init__.py
        ├── s3.py             # S3PathBuilder, write_parquet_to_s3()
        ├── parquet.py        # pydantic_models_to_arrow_table()
        └── config.py         # Settings (BaseSettings)

tests/
├── conftest.py
├── fixtures/
│   ├── liquipedia/
│   │   └── teams_response.json
│   ├── faceit/
│   │   └── match_stats_response.json
│   ├── pandascore/
│   │   └── matches_response.json
│   └── kaggle/
│       └── sample_matches.csv
├── test_liquipedia_client.py
├── test_faceit_client.py
├── test_pandascore_client.py
├── test_kaggle_bootstrap.py
├── test_models.py
└── test_s3_utils.py

pyproject.toml
.env.example
```

### Pattern 1: BaseAPIClient ABC
**What:** Abstract base class with shared retry/rate-limit/logging logic; subclasses override `BASE_URL`, `RATE_LIMIT_SEMAPHORE`, and entity-fetch methods.
**When to use:** All three live API clients (Liquipedia, FACEIT, PandaScore) extend this.
**Example:**
```python
# Source: Official httpx + tenacity docs
import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)
import logging

logger = structlog.get_logger()


class BaseAPIClient(ABC):
    BASE_URL: str
    _semaphore: asyncio.Semaphore  # set per subclass

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._auth_headers(),
            timeout=30.0,
        )

    @abstractmethod
    def _auth_headers(self) -> dict[str, str]: ...

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    async def get(self, path: str, **params: Any) -> dict[str, Any]:
        async with self._semaphore:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def __aenter__(self) -> "BaseAPIClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()
```

### Pattern 2: Per-Client Rate Limit Constants
**What:** Each subclass defines its own semaphore sized to its API's safe concurrency ceiling.
**When to use:** FACEIT (1 req/s → semaphore of 1), PandaScore (1,000/hour → ~1 per 3.6s → semaphore of 1 + sleep), Liquipedia (1,000/hour → semaphore of 5).
**Example:**
```python
class FACEITClient(BaseAPIClient):
    BASE_URL = "https://open.faceit.com/data/v4"
    _semaphore = asyncio.Semaphore(1)  # 1 concurrent request

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}
```

### Pattern 3: Pydantic v2 Source + Canonical Model Split
**What:** Per-source raw models (`FACEITMatch`) tolerate API-specific field names and extras; canonical models (`Match`) define the shared schema that pyarrow serializes.
**When to use:** Every source has unique field naming; downstream dbt expects a uniform schema.
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel, ConfigDict, Field


class FACEITMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    match_id: str
    game: str
    region: str
    competition_name: str
    teams: dict[str, Any]
    results: dict[str, Any] | None = None

    def to_canonical(self) -> "Match":
        # map FACEIT field names to shared schema
        ...


class Match(BaseModel):
    """Canonical shared match model written to Parquet."""
    model_config = ConfigDict(extra="forbid")  # strict on canonical

    match_id: str
    source: str          # "faceit" | "liquipedia" | "pandascore"
    team_a_id: str
    team_b_id: str
    winner_id: str | None
    played_at: str       # ISO-8601 date string for partition key
    map_name: str | None = None
```

### Pattern 4: Parquet Write to S3 via BytesIO
**What:** Build a `pa.Table` from a list of Pydantic canonical models, write to `BytesIO`, upload with `boto3.put_object`.
**When to use:** All four ingestion paths (three live APIs + Kaggle bootstrap).
**Example:**
```python
# Source: https://arrow.apache.org/docs/python/parquet.html
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq
import boto3


def write_parquet_to_s3(
    records: list[dict],
    schema: pa.Schema,
    bucket: str,
    key: str,
) -> None:
    """Write records as Parquet to S3. Overwrites existing key (idempotent)."""
    table = pa.Table.from_pylist(records, schema=schema)
    buf = BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


def build_s3_key(
    source: str,
    entity_type: str,
    year: int,
    month: int,
    day: int,
    filename: str = "data.parquet",
) -> str:
    """Build Hive-partitioned S3 key."""
    return f"raw/{source}/{entity_type}/year={year}/month={month:02d}/day={day:02d}/{filename}"
```

### Pattern 5: pydantic-settings Config
**What:** `Settings` class reads from environment variables or `.env` file; instantiated once as a module-level singleton.
**When to use:** Any code needing API keys, AWS region, S3 bucket name.
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CS2_",
    )

    faceit_api_key: str
    pandascore_api_key: str
    liquipedia_api_key: str
    aws_s3_bucket: str
    aws_region: str = "us-east-1"
    kaggle_username: str
    kaggle_key: str


settings = Settings()  # raises ValidationError at startup if keys missing
```

### Pattern 6: respx Mocking for Async httpx Tests
**What:** Use `respx_mock` pytest fixture (or `@respx.mock` decorator) to intercept httpx calls; load fixture JSON files for realistic responses.
**When to use:** All `test_*_client.py` test files.
**Example:**
```python
# Source: https://lundberg.github.io/respx/guide/
import pytest
import respx
import httpx
from pathlib import Path
import json


@pytest.fixture
def faceit_match_fixture() -> dict:
    path = Path(__file__).parent / "fixtures/faceit/match_stats_response.json"
    return json.loads(path.read_text())


@pytest.mark.asyncio
async def test_get_match_stats(respx_mock, faceit_match_fixture):
    respx_mock.get(
        "https://open.faceit.com/data/v4/matches/test-match-id/stats"
    ).mock(return_value=httpx.Response(200, json=faceit_match_fixture))

    async with FACEITClient(api_key="test-key") as client:
        result = await client.get_match_stats("test-match-id")

    assert result.match_id == "test-match-id"
```

### Anti-Patterns to Avoid
- **Sharing a single httpx.AsyncClient across all source clients:** Each subclass should own its client instance — different auth headers, base URLs, timeouts.
- **Catching bare `Exception` in retry predicates:** Use `retry_if_exception_type` with specific exceptions (`httpx.HTTPStatusError`, `httpx.TimeoutException`) — bare except hides programming errors.
- **Writing Parquet with pandas intermediary:** `pa.Table.from_pylist()` or `pa.Table.from_pydict()` is direct and keeps pandas out of the ingestion layer.
- **Hardcoding S3 paths with string concatenation:** Use the `build_s3_key()` utility so path format stays consistent across all four sources.
- **Closing httpx.AsyncClient after every request:** Reuse a single client per ingestion run; only close it in `__aexit__`.
- **Using `ConfigDict(extra="forbid")` on source raw models:** API responses add undocumented fields frequently; use `extra="ignore"` on raw models, `extra="forbid"` only on canonical models where schema stability matters.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retries with backoff | Custom retry loop with `time.sleep` | `tenacity` `@retry` | Handles async sleep, jitter, result-based retry, logging callbacks |
| Rate limiting | Manual `time.sleep` between calls | `asyncio.Semaphore` + tenacity | Semaphore prevents concurrent limit violations; sleep alone doesn't protect against burst |
| Settings from env vars | `os.environ.get()` calls scattered across codebase | `pydantic-settings` `BaseSettings` | Validates types at startup, not at call time; fails fast on missing keys |
| JSON → typed objects | `dict["field"]` access throughout | Pydantic `BaseModel` | Catches missing/wrong-type fields at ingestion boundary, not deep in pipeline |
| Parquet schema inference | Let pyarrow infer types from Python dicts | Explicit `pa.schema()` | Inferred schemas change silently when API adds/removes fields; explicit schema is the contract |
| S3 path construction | String f-formatting per source | `build_s3_key()` utility | Hive-partition format must be consistent for dbt external stage scanning |
| HTTP response mocking | monkeypatch httpx internals | `respx` | respx integrates with httpx transport layer; monkeypatching breaks with SSL/async edge cases |

**Key insight:** The three biggest rewrite triggers in data ingestion layers are schema drift (fix with explicit Pydantic models + pyarrow schemas), silent retry failures (fix with tenacity), and S3 path inconsistency (fix with a single path-builder utility).

---

## Common Pitfalls

### Pitfall 1: PandaScore 429 Handling
**What goes wrong:** PandaScore's free tier is 1,000 req/hour. A naive loop over 200 matches fires all 200 requests immediately, exhausts the hourly budget, and triggers 429s for the remaining 800 requests in the hour.
**Why it happens:** `asyncio.gather()` with no concurrency control spawns all coroutines at once.
**How to avoid:** Use `asyncio.Semaphore(1)` on `PandaScoreClient` and add `await asyncio.sleep(3.6)` inside the semaphore context to enforce ~0.27 req/s (1,000/hour).
**Warning signs:** First few runs succeed, then all subsequent requests in the same hour return 429.

### Pitfall 2: Pydantic v2 vs v1 API Confusion
**What goes wrong:** Pydantic v1 used `class Config: extra = "ignore"`; Pydantic v2 uses `model_config = ConfigDict(extra="ignore")`. Mixing the styles silently falls back to v1 compat mode in some environments but raises errors in strict v2.
**Why it happens:** Training data and older blog posts still show v1 syntax.
**How to avoid:** Always use `from pydantic import BaseModel, ConfigDict` and `model_config = ConfigDict(...)`. Never define inner `class Config`.
**Warning signs:** `UserWarning: Valid config keys have changed in V2` at import time.

### Pitfall 3: httpx AsyncClient Not Closed Properly
**What goes wrong:** `ResourceWarning: unclosed <ssl.SSLSocket>` in test output; connection pool exhaustion in long-running ingestion runs.
**Why it happens:** `httpx.AsyncClient` is not garbage-collected safely without explicit `aclose()`.
**How to avoid:** Always use `BaseAPIClient` as an async context manager (`async with LiquipediaClient(...) as client`). Implement `__aenter__`/`__aexit__` in the base class.
**Warning signs:** ResourceWarnings in pytest output; connection errors after many requests.

### Pitfall 4: pyarrow Schema Drift Between Sources
**What goes wrong:** `LiquipediaMatch` has `tournament_id: str | None` but pyarrow infers it as `string` (non-nullable) from the first batch where all values are present. Subsequent batches with null values raise `ArrowInvalid`.
**Why it happens:** `pa.Table.from_pylist()` infers schema from the first batch only.
**How to avoid:** Define explicit `pa.schema()` objects for each entity type in `utils/parquet.py`. Pass `schema=` explicitly to `pa.Table.from_pylist()`.
**Warning signs:** `ArrowInvalid: Column X expected type string but found null`.

### Pitfall 5: Kaggle CLI Credentials in CI
**What goes wrong:** Kaggle bootstrap fails in CI because `~/.kaggle/kaggle.json` is missing.
**Why it happens:** Kaggle Python package looks for credentials at `~/.kaggle/kaggle.json` or `KAGGLE_USERNAME` + `KAGGLE_KEY` environment variables.
**How to avoid:** Use `CS2_KAGGLE_USERNAME` and `CS2_KAGGLE_KEY` in the `Settings` class; write them to `~/.kaggle/kaggle.json` programmatically at bootstrap script startup (not committed to git).
**Warning signs:** `OSError: Could not find kaggle.json` on CI runs.

### Pitfall 6: respx Mock Not Catching Redirects
**What goes wrong:** Some APIs return 301/302 redirects; httpx follows them by default. respx only mocks the initial URL, so the redirect target is unmocked and hits the network.
**Why it happens:** httpx's follow_redirects=True (default) issues a second request to the redirect URL.
**How to avoid:** In `AsyncClient` constructor set `follow_redirects=False` for clients where you control the base URL. Or mock both the original and redirect URLs in tests.
**Warning signs:** `respx.MockTransport: No mock found for GET https://redirect-target.com/...`.

### Pitfall 7: Liquipedia API v3 vs MediaWiki API
**What goes wrong:** Liquipedia has two distinct APIs — the older MediaWiki API (`api.php?action=parse&...`) and the newer REST API v3. The REST API v3 requires separate API key registration and has structured JSON responses for Teams, Players, Matches, etc. The MediaWiki API is publicly accessible but returns HTML/wikitext, not structured data.
**Why it happens:** Most community examples and older Python libraries (liquipediapy) use the MediaWiki API, not v3.
**How to avoid:** Register for Liquipedia API v3 access at liquipedia.net/api. Use the REST endpoints (which return structured JSON with the 10 data types listed on the API page). Do not use `api.php` action endpoints.
**Warning signs:** Response body contains HTML tags or wiki markup instead of JSON objects.

---

## Code Examples

Verified patterns from official sources:

### tenacity @retry for 429 and timeout
```python
# Source: https://tenacity.readthedocs.io/en/stable/
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
    retry_if_result,
)
import logging


def _is_rate_limited(exc: BaseException) -> bool:
    """Retry on HTTP 429 status."""
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code == 429
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=60),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    reraise=True,
)
async def get_with_retry(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url)
    if response.status_code == 429:
        raise httpx.HTTPStatusError(
            "Rate limited", request=response.request, response=response
        )
    response.raise_for_status()
    return response.json()
```

### pydantic-settings with env_prefix
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CS2_",
    )

    faceit_api_key: str
    pandascore_api_key: str
    liquipedia_api_key: str
    aws_s3_bucket: str
    aws_region: str = "us-east-1"
    kaggle_username: str
    kaggle_key: str
```

### pyarrow explicit schema + write to S3
```python
# Source: https://arrow.apache.org/docs/python/parquet.html
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
import boto3

MATCH_SCHEMA = pa.schema([
    pa.field("match_id", pa.string(), nullable=False),
    pa.field("source", pa.string(), nullable=False),
    pa.field("team_a_id", pa.string(), nullable=False),
    pa.field("team_b_id", pa.string(), nullable=False),
    pa.field("winner_id", pa.string(), nullable=True),
    pa.field("played_at", pa.string(), nullable=False),
    pa.field("map_name", pa.string(), nullable=True),
])


def write_matches_to_s3(
    matches: list[dict],
    bucket: str,
    s3_key: str,
) -> None:
    table = pa.Table.from_pylist(matches, schema=MATCH_SCHEMA)
    buf = BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )
```

### respx async test with fixture JSON
```python
# Source: https://lundberg.github.io/respx/guide/
import pytest
import httpx
import respx
from pathlib import Path
import json


@pytest.fixture
def pandascore_matches_fixture() -> dict:
    p = Path(__file__).parent / "fixtures/pandascore/matches_response.json"
    return json.loads(p.read_text())


@pytest.mark.asyncio
async def test_pandascore_get_matches(respx_mock, pandascore_matches_fixture):
    url = "https://api.pandascore.co/csgo/matches"
    respx_mock.get(url).mock(
        return_value=httpx.Response(200, json=pandascore_matches_fixture)
    )

    async with PandaScoreClient(api_key="test-token") as client:
        matches = await client.get_recent_matches()

    assert len(matches) > 0
    assert all(isinstance(m, PandaScoreMatch) for m in matches)
```

### structlog JSON configuration (production)
```python
# Source: https://www.structlog.org/en/stable/logging-best-practices.html
import structlog
import logging
import sys


def configure_logging(json_output: bool = True) -> None:
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
```

### pyproject.toml structure with uv + src layout
```toml
# Source: https://docs.astral.sh/uv/concepts/projects/config/
[project]
name = "cs2-analytics"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "tenacity>=9.0",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "pyarrow>=16.0",
    "boto3>=1.35",
    "structlog>=24.0",
    "kaggle>=1.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "ruff>=0.4",
    "mypy>=1.10",
    "boto3-stubs[s3]>=1.35",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/cs2_analytics"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
strict = true
python_version = "3.12"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests` library | `httpx.AsyncClient` | 2022+ for async workloads | Native async, HTTP/2 support, consistent sync/async API |
| Pydantic v1 `class Config` | Pydantic v2 `ConfigDict` | 2023 (v2.0 release) | 17x validation speedup; different import paths |
| `pip` + `requirements.txt` | `uv` + `pyproject.toml` | 2024+ | 10-100x faster installs; lock file, workspace support |
| `pandas.read_parquet` → S3 | `pyarrow` direct | Ongoing preference | Removes heavy pandas dep from ingestion-only code |
| `responses` library for httpx mocking | `respx` | 2021+ | `responses` was designed for `requests`; respx integrates with httpx transport layer |

**Deprecated/outdated:**
- `liquipediapy` package: Uses old MediaWiki API (`api.php` endpoints), not Liquipedia API v3 REST — do not use
- Pydantic v1 `from pydantic import validator`: Replaced by `@field_validator` in v2
- `asyncio.get_event_loop().run_until_complete()`: Replaced by `asyncio.run()` in modern Python

---

## Open Questions

1. **Liquipedia API v3 exact endpoint paths and field names**
   - What we know: The REST API covers 10 data types (Teams, Players, Matches, Placements, Tournaments, etc.); free tier is 1,000 req/hour; requires API key registration at liquipedia.net/api
   - What's unclear: The exact REST endpoint URL structure (e.g., `/v3/counterstrike/teams?...` vs `/counterstrike/v3/teams`) is not publicly documented without an approved API key
   - Recommendation: Register for API key before implementing LiquipediaClient. Build the client with configurable endpoint paths as constants; fill them in once the API key is approved and endpoint docs are accessible. Use the `classicstrike/liquipedia-api-demo` GitHub repo and Liquipedia Discord `#api-help` as reference while waiting.

2. **FACEIT API field names for ADR/KAST in match stats response**
   - What we know: FACEIT Data API v4 has match details and stats endpoints; returns per-player performance data
   - What's unclear: The exact JSON field names for ADR, KAST (these are CS2-specific advanced stats) may differ from documentation if they were added post-CS2 migration
   - Recommendation: Fetch one live match stats response during development with `extra="ignore"` config; record the actual field names into the `FACEITMatch` fixture file before writing the model.

3. **PandaScore CS2 player stats field availability on free tier**
   - What we know: PandaScore's CS2 game ID is `counterstrike`; free tier is 1,000 req/hour; per-player kills/deaths available
   - What's unclear: Whether ADR and KAST are available on the free tier vs paid plans; some per-player stats may be premium-only
   - Recommendation: Use `ConfigDict(extra="ignore")` on `PandaScorePlayer` and make all advanced stats fields `Optional[float] = None`. Validate what's actually present in the first real response.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 + pytest-asyncio >= 0.23 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` section (Wave 0 — does not exist yet) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ --tb=short -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ING-01 | LiquipediaClient fetches teams, players, tournaments, placements | unit | `uv run pytest tests/test_liquipedia_client.py -x` | Wave 0 |
| ING-02 | FACEITClient fetches match stats with kills/deaths/ADR/KAST/ELO | unit | `uv run pytest tests/test_faceit_client.py -x` | Wave 0 |
| ING-03 | PandaScoreClient fetches match results and player stats | unit | `uv run pytest tests/test_pandascore_client.py -x` | Wave 0 |
| ING-04 | KaggleBootstrapIngester reads CSV and writes to same Parquet/S3 format | unit | `uv run pytest tests/test_kaggle_bootstrap.py -x` | Wave 0 |
| ING-05 | write_parquet_to_s3 produces valid Parquet under correct Hive-partitioned key | unit | `uv run pytest tests/test_s3_utils.py -x` | Wave 0 |
| ING-06 | BaseAPIClient retries on 5xx/429/timeout and respects semaphore | unit | `uv run pytest tests/test_base_client.py -x` | Wave 0 |
| ING-07 | All client tests use respx mocks; no live network calls | unit | `uv run pytest tests/ -x --no-header` | Wave 0 |
| ING-08 | Match/Player/Team canonical models reject malformed payloads | unit | `uv run pytest tests/test_models.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ --tb=short -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — shared fixtures (settings mock, boto3 mock)
- [ ] `tests/test_liquipedia_client.py` — covers ING-01
- [ ] `tests/test_faceit_client.py` — covers ING-02
- [ ] `tests/test_pandascore_client.py` — covers ING-03
- [ ] `tests/test_kaggle_bootstrap.py` — covers ING-04
- [ ] `tests/test_s3_utils.py` — covers ING-05
- [ ] `tests/test_base_client.py` — covers ING-06
- [ ] `tests/test_models.py` — covers ING-08
- [ ] `tests/fixtures/faceit/match_stats_response.json` — realistic FACEIT API response
- [ ] `tests/fixtures/pandascore/matches_response.json` — realistic PandaScore API response
- [ ] `tests/fixtures/liquipedia/teams_response.json` — realistic Liquipedia API v3 response
- [ ] `tests/fixtures/kaggle/sample_matches.csv` — small historical CSV sample
- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`
- [ ] Framework install: `uv add --dev pytest pytest-asyncio respx`

---

## Sources

### Primary (HIGH confidence)
- https://docs.pydantic.dev/latest/concepts/models/ — Pydantic v2 BaseModel, ConfigDict
- https://docs.pydantic.dev/latest/concepts/pydantic_settings/ — BaseSettings, SettingsConfigDict, env_file
- https://arrow.apache.org/docs/python/parquet.html — pyarrow write_table, S3FileSystem, BytesIO
- https://tenacity.readthedocs.io/en/stable/ — retry decorator, async support, wait strategies, before_sleep_log
- https://lundberg.github.io/respx/guide/ — respx route matching, async mock patterns, pytest fixture
- https://www.structlog.org/en/stable/logging-best-practices.html — JSON renderer, configure() pattern
- https://docs.astral.sh/uv/concepts/projects/config/ — uv pyproject.toml src layout, dependency groups

### Secondary (MEDIUM confidence)
- https://liquipedia.net/api — Liquipedia REST API v3 covers 10 CS2 data types; 1,000 req/hour free tier (verified from official API landing page, exact endpoint paths require API key)
- https://developers.pandascore.co/docs/introduction — PandaScore free tier 1,000 req/hour; CS2 game ID = `counterstrike` (confirmed)
- https://pypi.org/project/respx/ — respx version history and httpx compatibility matrix

### Tertiary (LOW confidence)
- Community posts on FACEIT API field names for ADR/KAST — needs verification against live API response once key is in hand
- PandaScore advanced player stat availability on free tier — not confirmed from official docs; treat as LOW until first real API call

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against official docs; versions confirmed current
- Architecture: HIGH — patterns verified against httpx, pydantic v2, pyarrow, respx official docs
- API field names: MEDIUM — Liquipedia v3, FACEIT v4, PandaScore CS2 field names need real key to fully verify
- Pitfalls: HIGH — most pitfalls sourced from official docs, PyPI changelogs, or confirmed architectural patterns

**Research date:** 2026-03-16
**Valid until:** 2026-04-15 (30 days — stack is stable; Pydantic v2 and pyarrow have slow release cycles)
