---
phase: 01-data-ingestion
plan: 04
subsystem: ingestion
tags: [liquipedia, api-client, asyncio, parquet, s3, rate-limiting, pydantic-v2, tdd]

# Dependency graph
requires:
  - src/cs2_analytics/ingestion/base.py (BaseAPIClient ABC — plan 01-03)
  - src/cs2_analytics/models/liquipedia.py (LiquipediaTeam/Player/Match/Tournament/Placement — plan 01-01)
  - src/cs2_analytics/utils/parquet.py (TEAM_SCHEMA, PLAYER_SCHEMA, MATCH_SCHEMA, models_to_records — plan 01-02)
  - src/cs2_analytics/utils/s3.py (write_parquet_to_s3, build_s3_key — plan 01-02)
provides:
  - src/cs2_analytics/ingestion/liquipedia.py — LiquipediaClient(BaseAPIClient) for Liquipedia API v3
  - Five fetch methods: get_teams, get_players, get_matches, get_tournaments, get_placements
  - ingest_all(bucket, ingest_date) writes teams/players/matches to S3 as canonical Parquet
affects: [05-pandascore-client, 06-kaggle-ingest, pipeline-orchestration, analytics-products]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Liquipedia API v3 response envelope — data.get('result', []) always; never data['result']"
    - "Per-endpoint 2s sleep — asyncio.sleep(2.0) after every get() call, not just in ingest_all()"
    - "Apikey auth scheme — 'Apikey {key}' header (not 'Bearer') with Accept: application/json"
    - "Deferred persistence pattern — entities without canonical schemas are counted but not written to S3"

key-files:
  created:
    - src/cs2_analytics/ingestion/liquipedia.py
    - tests/test_liquipedia_client.py
    - tests/fixtures/liquipedia/teams_response.json
    - tests/fixtures/liquipedia/players_response.json
    - tests/fixtures/liquipedia/matches_response.json
    - tests/fixtures/liquipedia/tournaments_response.json
    - tests/fixtures/liquipedia/placements_response.json
  modified: []

key-decisions:
  - "asyncio.sleep(2.0) placed inside each fetch method (not in ingest_all()) — enforces rate limit even when methods are called standalone"
  - "Tournaments and placements counted but not written to S3 — LiquipediaTournament and LiquipediaPlacement have no to_canonical(); raw persistence deferred to a future plan"
  - "Liquipedia /match2 endpoint (not /match) — API v3 uses match2 for structured CS2 match data"
  - "wiki='counterstrike' parameter scopes all queries to CS2 competitive data"

patterns-established:
  - "Pattern: Rate limit sleep in fetch method body — sleep lives in get_teams/players/etc., not the caller, so standalone calls are also rate-limited"
  - "Pattern: Deferred persistence — entity types without canonical schemas return counts only; S3 write gated on canonical list non-empty"

requirements-completed: [ING-01]

# Metrics
duration: 6min
completed: 2026-03-16
---

# Phase 1 Plan 04: LiquipediaClient Summary

**LiquipediaClient(BaseAPIClient) for Liquipedia API v3 covering teams/players/matches/tournaments/placements with mandatory 2s per-request sleep, Apikey auth, and S3 Parquet write for the three canonical entity types.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-16T18:27:52Z
- **Completed:** 2026-03-16T18:33:30Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files created:** 8

## Accomplishments

- LiquipediaClient subclasses BaseAPIClient with BASE_URL=https://api.liquipedia.net/api/v3 and Apikey auth header
- Five fetch methods using correct API v3 endpoints: /team, /player, /match2 (not /match), /tournament, /placement
- asyncio.sleep(2.0) placed inside every fetch method — enforces Liquipedia bot rate limit even on standalone calls
- ingest_all() converts teams/players/matches to canonical models and writes to S3 via write_parquet_to_s3
- Tournaments and placements returned as count-only (no canonical schema yet — deferred persistence)
- 20 new tests passing (TDD RED-GREEN); 89 total tests passing

## Task Commits

Each task was committed atomically:

1. **Prerequisite: BaseAPIClient + FACEITClient (plan 01-03)** - `caa2261` (feat)
2. **TDD RED — LiquipediaClient failing tests** - `5f569a4` (test)
3. **Task 1: LiquipediaClient implementation** - `b66739b` (feat)

## Files Created

- `src/cs2_analytics/ingestion/liquipedia.py` — LiquipediaClient with 5 fetch methods + ingest_all()
- `tests/test_liquipedia_client.py` — 20 tests: class attrs, auth headers, all 5 entity methods, ingest_all() S3 behavior
- `tests/fixtures/liquipedia/teams_response.json` — mock API response fixture
- `tests/fixtures/liquipedia/players_response.json` — mock API response fixture
- `tests/fixtures/liquipedia/matches_response.json` — mock API response fixture
- `tests/fixtures/liquipedia/tournaments_response.json` — mock API response fixture
- `tests/fixtures/liquipedia/placements_response.json` — mock API response fixture

## API Reference (for downstream plans)

### Endpoint paths

| Entity | Endpoint | Notes |
|--------|----------|-------|
| Teams | `/team` | wiki=counterstrike |
| Players | `/player` | wiki=counterstrike |
| Matches | `/match2` | NOT /match — v3 uses match2 for CS2 |
| Tournaments | `/tournament` | wiki=counterstrike |
| Placements | `/placement` | wiki=counterstrike |

### Auth header format

```
Authorization: Apikey {api_key}
Accept: application/json
```

### Response envelope

```python
data = await self.get("/team", wiki="counterstrike", limit=50)
results = data.get("result", [])  # ALWAYS use .get() — missing key crashes on empty response
```

### Rate limit

```python
await asyncio.sleep(2.0)  # MANDATORY after every API call
```

Liquipedia's bot rate limit policy blocks IPs that exceed the limit. Never remove or reduce the 2.0s sleep without checking their current policy.

### S3 key patterns

```
raw/liquipedia/teams/year={y}/month={mm}/day={dd}/data.parquet
raw/liquipedia/players/year={y}/month={mm}/day={dd}/data.parquet
raw/liquipedia/matches/year={y}/month={mm}/day={dd}/data.parquet
```

## Decisions Made

- **asyncio.sleep(2.0) in fetch method bodies** — placing the sleep inside get_teams(), get_players() etc. rather than in ingest_all() ensures the rate limit is enforced even when methods are called standalone (e.g., in scripts or tests that call get_teams() directly)
- **Tournaments and placements: count-only** — LiquipediaTournament and LiquipediaPlacement have no to_canonical() method and no corresponding pyarrow schema. Writing raw dicts without an explicit schema risks ArrowInvalid on all-None columns (Pitfall 4 from research). Deferred to a future plan when canonical schemas are defined.
- **wiki="counterstrike" as class constant** — stored as `_WIKI: str = "counterstrike"` to avoid hardcoding in every method call and make it easy to extend to other Liquipedia games

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Executed plan 01-03 (BaseAPIClient + FACEITClient) first**
- **Found during:** Pre-execution context check
- **Issue:** Plan 01-04 depends on 01-03 (`depends_on: [01-02, 01-03]`), but `src/cs2_analytics/ingestion/base.py` did not exist — plan 01-03 had not been executed. LiquipediaClient cannot subclass BaseAPIClient without base.py
- **Fix:** Executed plan 01-03 fully before starting 01-04: created base.py (BaseAPIClient ABC) and faceit.py (FACEITClient), verified 16 base client tests pass
- **Files created:** src/cs2_analytics/ingestion/base.py, src/cs2_analytics/ingestion/faceit.py, tests/test_base_client.py
- **Commit:** caa2261 (feat(01-03))

---

**Total deviations:** 1 auto-fixed (blocking prerequisite)
**Impact on plan:** Prerequisite was required for plan 01-04 to compile. No scope creep — plan 01-03 was already specified in the project plan.

## Issues Encountered

None — implementation matched plan specification exactly after prerequisite was satisfied.

## Next Phase Readiness

- LiquipediaClient complete: teams, players, matches fetch and write to S3
- Plan 01-05 (PandaScoreClient) can proceed using same BaseAPIClient pattern
- Tournaments and placements need canonical schemas before S3 persistence can be added

---
*Phase: 01-data-ingestion*
*Completed: 2026-03-16*
