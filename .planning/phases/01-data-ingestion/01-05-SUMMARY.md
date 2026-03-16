---
phase: 01-data-ingestion
plan: 05
subsystem: ingestion
tags: [httpx, pandascore, parquet, s3, asyncio, rate-limiting, pydantic-v2, tdd]

# Dependency graph
requires:
  - plan: 01-01
    provides: PandaScoreMatch and PandaScorePlayer models with to_canonical() methods
  - plan: 01-02
    provides: write_parquet_to_s3(), build_s3_key(), MATCH_SCHEMA, PLAYER_SCHEMA, models_to_records()
  - plan: 01-03
    provides: BaseAPIClient ABC with tenacity @retry, asyncio.Semaphore, paginate(), __aenter__/__aexit__
provides:
  - src/cs2_analytics/ingestion/pandascore.py — PandaScoreClient(BaseAPIClient) for PandaScore REST API
affects: [06-tests, 07-kaggle-bootstrap]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PandaScore bare array response pattern — isinstance(data, list) check handles bare JSON arrays vs {'results': [...]} format"
    - "Sequential page fetching pattern — loop over pages with sleep inside get_*() to avoid asyncio.gather() burst exhaustion"
    - "Free tier stats None pattern — all per-match stats (kills, deaths, adr, kd_ratio, kast) default to None from profile endpoints"
    - "Rate limit in method body pattern — asyncio.sleep(3.6) inside get_recent_matches() and get_players(), NOT in ingest_*() callers"

key-files:
  created:
    - src/cs2_analytics/ingestion/pandascore.py
    - tests/test_pandascore_client.py
    - tests/fixtures/pandascore/matches_response.json
    - tests/fixtures/pandascore/players_response.json
  modified: []

key-decisions:
  - "asyncio.sleep(3.6) placed inside get_recent_matches() and get_players(), not in ingest_*() — sleep is part of the rate-limit contract, fires even on direct method calls in tests"
  - "isinstance(data, list) check for bare array response — PandaScore list endpoints return bare JSON array, not {results:[...]} wrapper; base get() type-annotates dict[str,Any] but runtime value can be list"
  - "All per-match stats None in ingest_players() — /csgo/players is a profile endpoint, not match-stat endpoint; advanced stats may be premium-only on free tier"
  - "Sequential page fetching with no asyncio.gather() — prevents burst exhaustion on 1,000 req/hour free tier"
  - "CS2 game slug is /csgo/ not /cs2/ — PandaScore uses legacy CS:GO slug for match endpoints"

patterns-established:
  - "Pattern: rate limit sleep inside individual get_*() methods, not the ingest_*() orchestrator — enforces the contract at the API boundary"
  - "Pattern: free tier stat fields None — PandaScore profile endpoints don't include per-match stats; model accepts None, downstream ML handles missing values"

requirements-completed: [ING-03]

# Metrics
duration: 3min
completed: 2026-03-16
---

# Phase 1 Plan 05: PandaScore Ingestion Client Summary

**PandaScoreClient(BaseAPIClient) with /csgo/matches/past and /csgo/players endpoints, mandatory 3.6s sleep per call enforcing 1,000 req/hour free tier, and canonical Match/Player records written to S3 Parquet.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-16T18:27:58Z
- **Completed:** 2026-03-16T18:31:00Z
- **Tasks:** 1/1 (TDD RED + GREEN)
- **Files created:** 4

## Accomplishments

- PandaScoreClient subclasses BaseAPIClient with BASE_URL `https://api.pandascore.co` and Bearer token auth
- get_recent_matches() fetches /csgo/matches/past with mandatory asyncio.sleep(3.6) after each call
- get_players() fetches /csgo/players with mandatory asyncio.sleep(3.6) after each call
- ingest_matches() fetches N pages sequentially and writes canonical Match records to S3 using MATCH_SCHEMA
- ingest_players() fetches N pages with all stat fields as None (free tier limitation) and writes canonical Player records to S3 using PLAYER_SCHEMA
- 18 new tests pass; 102 total tests green (up from 53 baseline before plans 01-03/04 were applied)

## Task Commits

TDD task committed in two stages:

1. **TDD RED — failing pandascore tests** - `84a1a59` (test)
2. **GREEN — PandaScoreClient implementation** - `9640b94` (feat)

## Files Created

- `src/cs2_analytics/ingestion/pandascore.py` — PandaScoreClient(BaseAPIClient) with get_recent_matches(), get_players(), ingest_matches(), ingest_players()
- `tests/test_pandascore_client.py` — 18 tests: class attributes, auth header, get_*() deserialization, asyncio.sleep(3.6) enforcement, ingest_*() S3 write path, free tier stats None
- `tests/fixtures/pandascore/matches_response.json` — 2-match fixture with full opponent/winner structure
- `tests/fixtures/pandascore/players_response.json` — 2-player fixture with one having null current_team

## PandaScore API Details

### Endpoint Paths
| Method | Endpoint | Returns |
|--------|----------|---------|
| GET | /csgo/matches/past | Bare JSON array of PandaScoreMatch objects |
| GET | /csgo/players | Bare JSON array of PandaScorePlayer objects |

### Rate Limit Configuration
- Free tier: 1,000 req/hour = ~0.27 req/s
- Enforcement: `asyncio.sleep(3.6)` after EVERY API call in get_recent_matches() and get_players()
- Concurrency: `_semaphore = asyncio.Semaphore(1)` at class level
- Page fetching: Sequential only — never asyncio.gather() across pages

### Response Format
PandaScore list endpoints return a **bare JSON array** (not `{"results": [...]}`). The base `get()` method annotates the return as `dict[str, Any]` but the runtime value is a `list` for list endpoints. The `isinstance(data, list)` check in each get_*() method handles this correctly.

### Free Tier Stats Availability
| Field | Available from /csgo/players | Notes |
|-------|------------------------------|-------|
| id, name, nationality | Yes | Profile data |
| current_team | Yes | Nested dict |
| kills, deaths | No | Per-match endpoints only |
| adr, kast | Unknown | May be premium-only |
| kd_ratio | No | Calculated from per-match data |

All stat fields default to None in ingest_players() — a future plan can add per-match stat fetching against specific match IDs.

### CS2 Game Slug
PandaScore uses `/csgo/` (legacy CS:GO slug) for CS2 match endpoints. Do NOT use `/cs2/` — PandaScore has not migrated to the new game slug for match/player endpoints.

## Decisions Made

- asyncio.sleep(3.6) belongs inside get_recent_matches() and get_players(), not the ingest_*() orchestrators — this makes the rate-limit contract clear and testable even when methods are called directly
- All per-match stats (kills, deaths, adr, kd_ratio, kast) default to None in ingest_players() — the /csgo/players profile endpoint does not include match stats; these require match-specific endpoints
- isinstance(data, list) check handles bare array responses — PandaScore list endpoints return a raw JSON array, not a wrapped object; Python's json.loads() converts this to a list

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] base.py existed but wasn't in file listing — resolved by reading it directly**
- **Found during:** Start of Task 1
- **Issue:** The initial `ls` of the ingestion directory showed only `__init__.py`, suggesting base.py was missing. However, `base.py` and `faceit.py` actually existed (git history confirms plans 01-03 were applied). Reading the files directly confirmed they were present and correct.
- **Fix:** Read base.py and faceit.py to confirm their signatures before implementing PandaScoreClient. No code changes needed.
- **Files modified:** None
- **Verification:** `uv run python -c "from cs2_analytics.ingestion.base import BaseAPIClient; print('ok')"` succeeded

---

**Total deviations:** 1 (non-code — directory listing discrepancy; auto-resolved by direct file read)
**Impact on plan:** No scope creep. Plan executed as specified.

## Issues Encountered

None beyond the directory listing discrepancy noted above.

## Next Phase Readiness

- PandaScoreClient ready for use in orchestration layer (Phase 2 — Airflow DAGs)
- Remaining ingestion clients from Phase 1: LiquipediaClient (plan 01-04), KaggleBootstrapIngester (plan 01-06/07)
- All four ingestion clients share the same write path (write_parquet_to_s3 + canonical models) — schema consistency guaranteed

---
*Phase: 01-data-ingestion*
*Completed: 2026-03-16*

## Self-Check: PASSED
