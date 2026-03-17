---
phase: 03-warehouse-dbt
plan: "03"
subsystem: dbt-staging-intermediate
tags: [dbt, snowflake, staging, intermediate, union, deduplication]
dependency_graph:
  requires: [03-02]
  provides: [staging models, intermediate models]
  affects: [03-04, 03-05]
tech_stack:
  added: []
  patterns: [source-renamed-CTE pattern, UNION ALL with ROW_NUMBER deduplication]
key_files:
  created:
    - dbt_project/models/staging/stg_faceit_matches.sql
    - dbt_project/models/staging/stg_pandascore_matches.sql
    - dbt_project/models/staging/stg_kaggle_matches.sql
    - dbt_project/models/staging/stg_faceit_players.sql
    - dbt_project/models/staging/stg_pandascore_players.sql
    - dbt_project/models/staging/stg_liquipedia_teams.sql
    - dbt_project/models/staging/staging.yml
    - dbt_project/models/intermediate/int_matches_unioned.sql
    - dbt_project/models/intermediate/int_players_unioned.sql
    - dbt_project/models/intermediate/intermediate.yml
  modified: []
decisions:
  - "[03-03]: coalesce(match_id, '__profile__') in int_players_unioned partition — handles player records with null match_id (profile-level) without treating them all as duplicates"
  - "[03-03]: source column hard-coded as string literal in staging models — not read from raw table to prevent source drift from upstream API changes"
metrics:
  duration: 3 min
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_created: 10
---

# Phase 3 Plan 03: Staging and Intermediate Models Summary

**One-liner:** 6 source-renamed staging models + 2 UNION ALL intermediate models with FACEIT-priority ROW_NUMBER deduplication for unified CS2 match and player datasets.

## What Was Built

### Staging Layer (6 models)

Each staging model follows the `source → renamed → select *` CTE pattern:
- Single source table reference via `{{ source('raw', 'raw_*') }}`
- Column rename/cast only — no aggregations, no joins
- NULL filter on primary key (match_id or player_id or team_id)
- Source column hard-coded as string literal for lineage safety

| Model | Source Table | PK |
|---|---|---|
| stg_faceit_matches | raw_faceit_matches | match_id |
| stg_pandascore_matches | raw_pandascore_matches | match_id |
| stg_kaggle_matches | raw_kaggle_matches | match_id |
| stg_faceit_players | raw_faceit_players | player_id |
| stg_pandascore_players | raw_pandascore_players | player_id |
| stg_liquipedia_teams | raw_liquipedia_teams | team_id (unique) |

`staging.yml` defines `data_tests:` (not deprecated `tests:`) with `not_null` and `accepted_values` constraints on all primary keys and source columns.

### Intermediate Layer (2 models)

**int_matches_unioned:** UNION ALL of all three match staging models. Source column preserved for downstream lineage and cross-source deduplication in mart models. Exactly 2 `union all` occurrences (3 sources = 2 unions).

**int_players_unioned:** UNION ALL of faceit + pandascore player models, then deduplicated via `ROW_NUMBER()` partitioned on `(player_id, coalesce(match_id, '__profile__'))`. FACEIT gets priority (order value 1) over PandaScore (order value 2) because FACEIT provides richer stats (ELO, KAST, ADR) unavailable in PandaScore.

`intermediate.yml` defines `data_tests:` with `not_null` and `accepted_values` for both models.

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | 6 staging models + staging.yml | 8c8cfd1 | 6 SQL + 1 YAML + .gitkeep removed |
| 2 | int_matches_unioned + int_players_unioned + intermediate.yml | cd07f38 | 2 SQL + 1 YAML + .gitkeep removed |

## Self-Check: PASSED
