---
phase: 01-data-ingestion
plan: 03
subsystem: ingestion
tags: [httpx, tenacity, asyncio, abc, respx, faceit-api-v4, rate-limiting, parquet, s3, tdd]

# Dependency graph
requires:
  - src/cs2_analytics/models/faceit.py (FACEITMatch, FACEITPlayer with to_canonical())
  - src/cs2_analytics/models/canonical.py (Match, Player canonical models)
  - src/cs2_analytics/utils/s3.py (write_parquet_to_s3, build_s3_key)
  - src/cs2_analytics/utils/parquet.py (MATCH_SCHEMA, PLAYER_SCHEMA, models_to_records)
provides:
  - src/cs2_analytics/ingestion/base.py — BaseAPIClient ABC with tenacity @retry, asyncio.Semaphore, paginate()
  - src/cs2_analytics/ingestion/faceit.py — FACEITClient(BaseAPIClient) for FACEIT Data API v4
  - tests/test_base_client.py — 16 tests for BaseAPIClient (structure, lifecycle, get, paginate)
  - tests/test_faceit_client.py — 15 tests for FACEITClient (auth, endpoints, ingest, S3 writes)
  - tests/fixtures/faceit/ — match_response.json and match_stats_response.json
affects: [01-04-liquipedia, 01-05-pandascore, 01-06-kaggle, 02-airflow]

# Tech tracking
tech-stack:
  added: []  # All libraries already in pyproject.toml from plan 01-01
  patterns:
    - "BaseAPIClient ABC pattern — subclasses define BASE_URL, _semaphore (class-level), _auth_headers()"
    - "tenacity @retry on get() — stop_after_attempt(5), wait_exponential_jitter(initial=1, max=60), reraise=True"
    - "429 explicit raise pattern — raise HTTPStatusError before raise_for_status() so tenacity catches it"
    - "asyncio.Semaphore class-level attribute — all instances of a subclass share one semaphore for global rate limiting"
    - "asyncio.sleep(1.0) in ingest loop — FACEIT ~1 req/s rate limit enforced at ingest level"
    - "follow_redirects=False on AsyncClient — prevents respx mocks breaking on redirect targets (Pitfall 6)"
    - "Resilient batch ingest — individual match failures logged and skipped, batch continues"
    - "paginate() async generator — yields pages with offset pagination until fewer items than limit"

key-files:
  created:
    - src/cs2_analytics/ingestion/base.py
    - src/cs2_analytics/ingestion/faceit.py
    - tests/test_base_client.py
    - tests/test_faceit_client.py
    - tests/fixtures/faceit/match_response.json
    - tests/fixtures/faceit/match_stats_response.json
  modified: []

key-decisions:
  - "asyncio.sleep(1.0) called TWICE per match in ingest_matches() — once after get_match(), once after get_match_stats() — ensures ~1 req/s even without tenacity retrying"
  - "_semaphore is CLASS-level attribute not instance-level — all FACEITClient instances share one Semaphore(1) for global rate limit enforcement"
  - "follow_redirects=False on httpx.AsyncClient — prevents respx mock failures on redirect targets (research Pitfall 6)"
  - "ingest_matches() logs and continues on per-match Exception — resilient batch processing over perfect-or-nothing"
  - "Stats passed as None to player.to_canonical() — player_stats fields are FACEIT-specific field names (Kills, ADR) not canonical names; to_canonical() accepts them as kwargs"

patterns-established:
  - "Pattern: BaseAPIClient subclass = define BASE_URL (str), _semaphore (Semaphore), _auth_headers() → the ABC does the rest"
  - "Pattern: respx_mock fixture with async context manager for testing — no live network in any test"
  - "Pattern: patch write_parquet_to_s3 and asyncio.sleep in ingest tests — avoids AWS calls and slow sleeps"
  - "Pattern: fixture JSON files in tests/fixtures/{source}/ — realistic API payloads separate from test logic"

requirements-completed: [ING-02, ING-06]

# Metrics
duration: 6min
completed: 2026-03-16
---

# Phase 1 Plan 03: BaseAPIClient ABC and FACEITClient Summary

**BaseAPIClient ABC with tenacity @retry (5 attempts, exponential jitter, 429+5xx+timeout) and FACEITClient for FACEIT Data API v4 per-match stats with 1 req/s rate limiting and S3 Parquet write.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-16T18:27:34Z
- **Completed:** 2026-03-16T18:33:30Z
- **Tasks:** 2/2
- **Files created:** 6

## Accomplishments

- BaseAPIClient ABC with `@retry(stop_after_attempt(5), wait_exponential_jitter, retry_if_exception_type((HTTPStatusError, TimeoutException)), reraise=True)` on `get()`
- asyncio.Semaphore class-level attribute for global rate limiting across all subclass instances
- `paginate()` async generator with offset pagination — stops on empty results or partial page
- FACEITClient extends BaseAPIClient with Bearer auth, Semaphore(1), GET /matches/{id} and GET /matches/{id}/stats endpoints
- `ingest_matches()` writes canonical Match + Player records to S3 via write_parquet_to_s3; 1.0s sleep between requests
- 84 tests passing (original 53 + 16 base client + 15 faceit client)

## Task Commits

Each task was committed atomically:

1. **Task 1: BaseAPIClient ABC (from prior session)** - `caa2261` (feat)
2. **Task 2: FACEITClient + tests + fixtures** - `6a0b451` (test)

## BaseAPIClient Method Signatures (for plans 01-04 and 01-05)

```python
class BaseAPIClient(ABC):
    BASE_URL: str                           # set by subclass
    _semaphore: asyncio.Semaphore           # class-level, set by subclass

    def __init__(self, api_key: str) -> None: ...

    @abstractmethod
    def _auth_headers(self) -> dict[str, str]: ...

    @retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(initial=1, max=60),
           retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
           before_sleep=before_sleep_log(..., WARNING), reraise=True)
    async def get(self, path: str, **params: Any) -> dict[str, Any]: ...

    async def paginate(
        self,
        path: str,
        *,
        offset_key: str = "offset",    # query param name for page offset
        limit: int = 100,
        results_key: str = "items",    # JSON key containing the list
    ) -> AsyncIterator[list[dict[str, Any]]]: ...

    async def __aenter__(self) -> BaseAPIClient: ...
    async def __aexit__(self, *_: Any) -> None: ...  # calls self._client.aclose()
```

## FACEITClient Endpoint Reference

```python
class FACEITClient(BaseAPIClient):
    BASE_URL = "https://open.faceit.com/data/v4"
    _semaphore = asyncio.Semaphore(1)  # 1 concurrent request

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def get_match(self, match_id: str) -> FACEITMatch:
        # GET /matches/{match_id}

    async def get_match_stats(self, match_id: str) -> list[FACEITPlayer]:
        # GET /matches/{match_id}/stats
        # Response: {"rounds": [{"teams": [{"players": [...]}]}]}
        # player_stats dict merged into player top-level before FACEITPlayer.model_validate()

    async def ingest_matches(
        self,
        match_ids: list[str],
        bucket: str,
        ingest_date: date,
        *,
        region: str = "us-east-1",
    ) -> tuple[int, int]:  # (match_count, player_count)
        # asyncio.sleep(1.0) called after get_match() AND after get_match_stats()
        # Failed matches logged and skipped (resilient batch)
        # Returns (0, 0) for empty match_ids
```

## Rate Limit Configuration

- `asyncio.Semaphore(1)` — max 1 concurrent request
- `asyncio.sleep(1.0)` after get_match() + asyncio.sleep(1.0) after get_match_stats() per match
- Effective throughput: ~0.5 matches/second (2 requests + 2 sleeps per match)
- FACEIT free tier: ~1 req/s — configuration is conservative and safe

## Files Created

- `src/cs2_analytics/ingestion/base.py` — BaseAPIClient ABC with tenacity retry, semaphore, paginate(), aenter/aexit
- `src/cs2_analytics/ingestion/faceit.py` — FACEITClient with Bearer auth, match stats endpoints, ingest_matches()
- `tests/test_base_client.py` — 16 tests: abstract structure, lifecycle, get(), paginate(), follow_redirects
- `tests/test_faceit_client.py` — 15 tests: class attrs, auth headers, get_match, get_match_stats, ingest_matches
- `tests/fixtures/faceit/match_response.json` — realistic FACEIT match API response fixture
- `tests/fixtures/faceit/match_stats_response.json` — realistic FACEIT stats response (3 players across 2 teams)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `TestClient` naming collision with pytest collection (pytest tries to collect classes starting with `Test`) — renamed the concrete test subclass to `ConcreteClient` to avoid the warning.

## Next Phase Readiness

- Plans 01-04 (LiquipediaClient) and 01-05 (PandaScoreClient) can subclass BaseAPIClient directly
- Both need to define BASE_URL, _semaphore, and _auth_headers() — the ABC enforces these contracts
- RED tests for plans 01-04/01-05 are already committed and failing (expected — implementations pending)

## Self-Check: PASSED

---
*Phase: 01-data-ingestion*
*Completed: 2026-03-16*
