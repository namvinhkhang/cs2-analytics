---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 4 partial completion; v1 future-work and v2 expansion plans created
last_updated: "2026-05-11T00:00:00Z"
last_activity: 2026-05-11 — Upset Tracker and Hidden Gem Scout completed; Choke/Clutch, CS API profiles, and dashboard planned
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 19
  completed_plans: 19
  percent: 62
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** Three analytical products that answer questions HLTV.org never answers — surfaced from a production-grade pipeline that any interviewer can inspect end-to-end.
**Current focus:** Phase 4 — finish Choke/Clutch Profile, then Phase 5 dashboard

## Current Position

Phase: 4 of 6 (Analytical Products)
Plan: 2 of 3 product tracks complete
Status: In progress
Last activity: 2026-05-11 — Upset Tracker and Hidden Gem Scout completed; future work planned

Progress: [██████░░░░] 62%

## Performance Metrics

**Velocity:**
- Total plans completed: 19
- Completed phases: 3 of 6
- Milestone progress: 62%

**By Phase:**

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 01-data-ingestion | 8/8 | Complete | 2026-03-17 |
| 02-orchestration | 5/5 | Complete | 2026-03-17 |
| 03-warehouse-dbt | 6/6 | Complete | 2026-03-18 |
| 04-analytical-products | 2/3 product tracks | In progress | - |
| 05-dashboard-deployment | 0/1 active plan | Planned | - |

**Recent Trend:**
- Last 5 completed work items: Kaggle removal, CS API match lineage, Upset Tracker leakage fix, Upset Tracker threshold tuning, Hidden Gem benchmark-gap trend
- Trend: Phase 4 is mostly complete; Choke/Clutch Profile is the next analytical product

*Updated after each plan completion*
- Most recent completion: Upset Tracker and Hidden Gem Scout
- Next milestone target: implement Choke/Clutch Profile and CS API bootstrap profiles

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Snowflake over BigQuery — better Airflow/dbt ecosystem docs
- [Init]: AWS S3 over GCS — higher intern posting frequency (72% vs 45%)
- [Init]: FACEIT as primary stats source — only official API with per-match ADR/KAST at semi-pro level
- [Init]: Kaggle CSV bootstrap for HLTV data — avoids ToS risk and Cloudflare blocking
- [Init]: Streamlit over Tableau/PowerBI — public URL + shows Python proficiency simultaneously
- [01-01]: Added pydantic.mypy plugin — resolves mypy strict-mode false positives on Settings() singleton
- [01-01]: conftest.py sets dummy env vars at collection time — allows test imports without .env present
- [Phase 01-02]: Callers pass bucket and region to write_parquet_to_s3() explicitly — module does not import settings, keeping it testable without .env
- [Phase 01-02]: pa.int64() used for all integer fields (not pa.int32()) — forward-safe for large ELO and ranking values
- [Phase 01-02]: structlog.info() called after successful put_object — avoids log noise for retried failures
- [Phase 01-data-ingestion]: asyncio.sleep(3.6) inside get_*() methods not ingest_*() callers — rate-limit contract at API boundary
- [Phase 01-data-ingestion]: PandaScore /csgo/ legacy slug — do NOT use /cs2/ for match/player endpoints
- [Phase 01-data-ingestion]: isinstance(data, list) check for bare array responses from PandaScore list endpoints
- [Phase 01-data-ingestion]: asyncio.sleep(2.0) inside each LiquipediaClient fetch method body — enforces rate limit on standalone calls
- [Phase 01-data-ingestion]: Tournaments and placements count-only in LiquipediaClient — no canonical schema yet, raw S3 persistence deferred
- [Phase 01-data-ingestion]: asyncio.sleep(1.0) called twice per match in ingest_matches() — after get_match() and after get_match_stats() — ensures ~1 req/s even without tenacity retrying
- [Phase 01-data-ingestion]: _semaphore is class-level on BaseAPIClient subclasses — all instances share one Semaphore(1) for global rate limit enforcement
- [Phase 01-data-ingestion]: follow_redirects=False on httpx.AsyncClient — prevents respx mock failures on redirect targets (Pitfall 6 from research)
- [Phase 01-data-ingestion]: moto[s3] added as dev dependency for @mock_aws S3 tests verifying PAR1 magic bytes
- [Phase 01-data-ingestion]: test_kaggle.py uses tests/fixtures/kaggle/sample_matches.csv — validates production CSV parsing path from static reference data
- [Phase 01-data-ingestion]: Sequence[BaseModel] over list[BaseModel] in models_to_records — list is invariant in mypy strict mode, Sequence is covariant
- [Phase 01-data-ingestion]: type: ignore[import-untyped] inline per-import for pyarrow and kaggle — precise suppression over global ignore_missing_imports
- [Phase 02-orchestration]: Build context = project root in docker-compose.yml — allows COPY pyproject.toml and COPY src to work from repo root
- [Phase 02-orchestration]: env_file: ../.env with relative path since docker-compose.yml lives in airflow/ subdirectory
- [Phase 02-orchestration]: restart: no on airflow-init prevents re-running users create after first successful init
- [Phase 02-orchestration]: AIRFLOW__CORE__UNIT_TEST_MODE=True set in conftest — disables scheduler and external connections during tests
- [Phase 02-orchestration]: CS2_SLACK_WEBHOOK_URL injected at module level before DagBag loads — ensures Airflow config env var present at import time
- [Phase 02-orchestration]: module-scoped dagbag fixture — avoids repeated DagBag instantiation overhead across structural tests
- [Phase 02-orchestration]: CS2_SLACK_WEBHOOK_URL read directly from os.environ in function body — no Airflow Connections, no module-level Settings import
- [Phase 02-orchestration]: fail_intentionally uses schedule=None and manual trigger only — prevents accidental scheduled runs
- [Phase 02-orchestration]: dagbag.dags.get() instead of dagbag.get_dag() in structural tests — avoids SQLite DB query on uninitialized test database
- [Phase 02-orchestration]: _s3_key_exists() placed at module level in DAG files — enables unit testing without Airflow context
- [Phase 02-orchestration]: FACEITClient.ingest_matches called with match_ids=[] in DAG — match ID discovery is a separate future concern; PandaScoreClient fetches internally
- [Phase 02-orchestration]: cs2_tournament_sync calls LiquipediaClient.ingest_matches() not ingest_tournaments() — tournaments/placements count-only in Phase 1, no canonical S3 schema yet
- [Phase 03-warehouse-dbt]: Typed raw tables + MATCH_BY_COLUMN_NAME over VARIANT — avoids $1:field::type syntax in staging models, makes column lineage visible in dbt docs
- [Phase 03-warehouse-dbt]: AUTO_SUSPEND=60 + INITIALLY_SUSPENDED=TRUE on CS2_WH — prevents Snowflake free trial credit burn from idle warehouse
- [Phase 03-01]: Overtime detection: score_a > 15 AND score_b > 15 (both exceed MR15 limit), not sum > 24
- [Phase 03-01]: score_a/score_b/is_overtime default to None on canonical Match — fully backward-compatible with existing to_canonical() callers
- [Phase 03-03]: coalesce(match_id, '__profile__') in int_players_unioned partition handles player records with null match_id without treating all as duplicates
- [Phase 03-03]: source column hard-coded as string literal in staging models to prevent source drift from upstream API changes
- [Phase 03-warehouse-dbt]: dim_tournaments is a placeholder (single unknown row) — Liquipedia tournament canonical schema deferred to Phase 4
- [Phase 03-warehouse-dbt]: fact_player_stats filters where match_id is not null — separates profile records from per-match stat records
- [Phase 03-warehouse-dbt]: fact_player_stats includes computed_kd and kill_share derived columns for downstream analytics convenience
- [Phase 03-06]: BashOperator for dbt tasks (not Cosmos) — simpler, matches existing DAG patterns
- [Phase 03-06]: snowflake.connector imported inside @task() body — avoids DagBag load-time ImportError
- [Phase 03-06]: PURGE = FALSE on all COPY INTO statements — raw S3 layer remains intact as immutable source of truth
- [2026-05-11]: Kaggle historical data removed from default modern marts — stale player/team mappings polluted CS API-backed features
- [2026-05-11]: Upset Tracker feature set limited to pre-match fields — final scores and winner-derived fields caused perfect leakage
- [2026-05-11]: Hidden Gem Scout skips clutch rate until a trustworthy clutch-event source is persisted
- [2026-05-11]: Hidden Gem Scout requires at least 20 recent 90-day stat rows to avoid one-off outliers

### Pending Todos

- Implement Choke/Clutch Profile from exact round/half/bracket data where available.
- Add daily, weekly, and backfill profiles to `scripts/bootstrap_csapi.py`.
- Build Streamlit dashboard for Upset Tracker, Hidden Gem Scout, and Choke/Clutch Profile.
- Use `.planning/V2_PLAN.md` for post-v1 platform expansion.

### Blockers/Concerns

- API rate limits: FACEIT ~1 req/s, PandaScore 1,000 req/hour — ingestion clients must implement backoff
- Snowflake $400 free trial credit is finite — avoid wasteful queries during development

## Session Continuity

Last session: 2026-05-11T00:00:00.000Z
Stopped at: Phase 4 partial completion; v1 future-work and v2 expansion plans created
Resume file: None
