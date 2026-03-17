---
phase: 03-warehouse-dbt
plan: 04
subsystem: database
tags: [dbt, snowflake, star-schema, fact-tables, dimension-tables, dbt_utils, surrogate-keys]

# Dependency graph
requires:
  - phase: 03-warehouse-dbt-02
    provides: staging models (stg_liquipedia_teams) and intermediate models (int_matches_unioned, int_players_unioned)
provides:
  - Star schema core layer: 2 fact tables + 4 dimension tables in dbt_project/models/marts/core/
  - Surrogate keys on all fact/dim tables via dbt_utils.generate_surrogate_key
  - Referential integrity schema tests in core.yml
affects: [03-warehouse-dbt-05, analytics-marts, dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "row_number() window function dedup pattern for dimension table latest-record selection"
    - "dbt_utils.generate_surrogate_key for stable hash-based PKs on fact and dim tables"
    - "data_tests: syntax (dbt v1.6+) with relationships test for referential integrity"
    - "Placeholder dimension pattern for deferred upstream data (dim_tournaments)"

key-files:
  created:
    - dbt_project/models/marts/core/dim_teams.sql
    - dbt_project/models/marts/core/dim_players.sql
    - dbt_project/models/marts/core/dim_maps.sql
    - dbt_project/models/marts/core/dim_tournaments.sql
    - dbt_project/models/marts/core/fact_matches.sql
    - dbt_project/models/marts/core/fact_player_stats.sql
    - dbt_project/models/marts/core/core.yml
  modified: []

key-decisions:
  - "dim_tournaments is a placeholder (single unknown row) — Liquipedia tournament canonical schema deferred to Phase 4"
  - "dim_players sources from int_players_unioned (not stg_) to inherit FACEIT-priority dedup logic from intermediate layer"
  - "fact_player_stats filters where match_id is not null — separates profile records from per-match stat records"
  - "fact_player_stats includes computed_kd and kill_share derived columns for downstream analytics convenience"

patterns-established:
  - "Dimension dedup pattern: row_number() over (partition by <id> order by <timestamp> desc) where _row_num = 1"
  - "Fact table grain always documented in header comment (e.g., one row per match per source)"
  - "Surrogate keys always first column, named <entity>_sk"

requirements-completed: [WH-01, WH-11]

# Metrics
duration: 5min
completed: 2026-03-17
---

# Phase 3 Plan 04: Core Star Schema Summary

**Star schema foundation with 2 fact tables (fact_matches, fact_player_stats) and 4 dimension tables, surrogate keys via dbt_utils, and referential integrity tests linking player stats back to dim_players**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-17T21:10:07Z
- **Completed:** 2026-03-17T21:15:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Created 4 dimension tables with deduplication logic (row_number window function for latest-record-wins per entity)
- Created 2 fact tables with surrogate keys (match_sk, player_stat_sk) via dbt_utils.generate_surrogate_key
- Authored core.yml with comprehensive schema tests: unique/not_null on all PKs, relationships test linking fact_player_stats.player_id to dim_players

## Task Commits

Each task was committed atomically:

1. **Task 1: Create 4 dimension tables** - `8626b3c` (feat)
2. **Task 2: Create 2 fact tables + core.yml schema tests** - `7d9a846` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `dbt_project/models/marts/core/dim_teams.sql` - Latest team ranking per team_id with row_number dedup on ingested_at
- `dbt_project/models/marts/core/dim_players.sql` - Latest player profile per player_id with row_number dedup on recorded_at
- `dbt_project/models/marts/core/dim_maps.sql` - Distinct CS2 maps from int_matches_unioned with map_sk surrogate key
- `dbt_project/models/marts/core/dim_tournaments.sql` - Placeholder (single unknown row) pending Phase 4 Liquipedia enrichment
- `dbt_project/models/marts/core/fact_matches.sql` - Match results grain (match_id+source), joins to dim_maps for map_sk, passes score_a/score_b/is_overtime
- `dbt_project/models/marts/core/fact_player_stats.sql` - Per-match player stats grain (player_id+match_id+source), derived computed_kd and kill_share columns
- `dbt_project/models/marts/core/core.yml` - Schema tests: unique/not_null on all surrogate keys, relationships test for player_id FK

## Decisions Made
- dim_tournaments is a placeholder with a single "unknown" row — Liquipedia tournament data was count-only in Phase 1 (no canonical S3 schema for tournaments), enrichment deferred to a future phase
- dim_players pulls from int_players_unioned rather than staging directly, so it inherits the FACEIT-priority source deduplication already built into the intermediate layer
- fact_player_stats adds computed_kd and kill_share as derived columns at the mart level — cheap to compute and eliminates repeated logic in downstream analytics models

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Core star schema complete and ready for Plan 03-05 (analytics marts)
- All 6 core models reference intermediate/staging layers established in Plan 03-02
- core.yml tests will validate referential integrity when dbt test runs against Snowflake

---
*Phase: 03-warehouse-dbt*
*Completed: 2026-03-17*
