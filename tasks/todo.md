# CS2-Era Hidden Gem Scout Implementation

- [x] Remove historical Kaggle data from CS2 mart lineage.
  - [x] Add regression tests that Kaggle no longer feeds match/player unions or team rankings.
  - [x] Remove Kaggle from `int_matches_unioned` and `int_players_unioned`.
  - [x] Remove Kaggle-derived team IDs/rankings from `dim_teams`.
  - [x] Update accepted source tests for modern-only intermediate models.
  - [x] Verify targeted SQL tests and full pytest.

- [x] Remove Kaggle pipeline completely.
  - [x] Delete Kaggle bootstrap script, ingestion module, fixtures, and tests.
  - [x] Remove Kaggle raw/staging dbt models, sources, Snowflake DDL, and Airflow COPY statements.
  - [x] Remove Kaggle settings and dependency from project metadata/lockfile.
  - [x] Update docs and remaining source examples away from Kaggle.
  - [x] Verify no Kaggle implementation references remain outside negative regression tests.

- [x] Investigate Hidden Gem Scout player/team/ranking mismatch for player ID 11893.
  - [x] Reproduce source truth with live CS API: player 11893 is ZywOo on Vitality, and Vitality is rank 1.
  - [x] Trace player team assignment from CS API raw data into `dim_players`, `fact_player_stats`, and `mart_hidden_gems`.
  - [x] Trace team ranking/tier assignment from VRS rankings into `dim_teams` and Hidden Gem Scout marts.
  - [x] Add a regression test for stale or incorrect CS API player-team/ranking joins.
  - [x] Implement the smallest root-cause fix and rerun targeted verification.

- [x] Add CS API bootstrap progress logging and chunk controls after rate-limit/hang report.

- [x] Confirm product direction: use Valve VRS + PandaScore + CS API before HLTV scraping.
- [x] Add failing tests for CS API VRS ranking parsing.
- [x] Add failing tests for CS API player-stat parsing.
- [x] Add typed canonical/Parquet schemas for modern team rankings and player stats.
- [x] Implement CS API VRS ingestion into `raw/csapi/team_rankings/`.
- [x] Implement CS API match-driven player-stat ingestion into `raw/csapi/player_stats/`.
- [x] Add Snowflake raw tables and `COPY INTO` commands.
- [x] Add dbt sources/staging models for CS API.
- [x] Patch `dim_teams` to prefer Liquipedia, then CS API VRS, then Kaggle legacy rankings.
- [x] Patch `fact_player_stats`/player union so CS API can feed modern Hidden Gem Scout stats.
- [x] Patch `mart_player_leaderboard` to use four tiers.
- [x] Patch `mart_hidden_gems` to expose `prospect_score` and remove the tier-4 fallback.
- [ ] Run dbt run/test and Snowflake distribution checks after RAW tables are created by ACCOUNTADMIN.
- [ ] Update `.planning/REQUIREMENTS.md` and phase docs after verification.

## Commit Batching Plan

- [x] Inspect working tree and identify local-only files to exclude.
- [x] Commit safety ignores for secrets/local generated caches.
- [x] Commit optional Liquipedia/config/Airflow changes.
- [x] Commit Kaggle multi-table ingestion.
- [x] Commit CS API ranking/player-stat ingestion.
- [x] Commit dbt marts for upset tracker, hidden gems, and choke profile.
- [x] Commit ML upset tracker training, prediction, artifacts, and tests.
- [x] Commit Airflow import cleanup.
- [x] Commit project docs/planning/graph artifacts.
- [x] Push commits to GitHub.

## Design

Hidden Gem Scout remains SQL-first. Modern data should come from:

1. CS API's VRS ranking endpoint for team ranking/points from the CS2 era.
2. PandaScore for recent match/team metadata already supported by the project.
3. CS API for current player/team stats if the public endpoint shape is stable.
4. Kaggle rankings only as legacy fallback for pre-CS2 historical rows.

The dashboard-facing output stays `mart_hidden_gems`: one row per flagged
tier-2/3/4 prospect, with tier-above thresholds, trend direction, and a numeric
`prospect_score` for sorting.

## Review

- Fixed Hidden Gem Scout current-team correctness by ingesting CS API `/players/stats/raw`
  rows as current player profile snapshots with `match_id = null`, so they update
  `dim_players` without becoming fake match facts.
- Updated `mart_hidden_gems` and `mart_player_leaderboard` to tier/rank players by
  `dim_players` current team first, falling back to the historical match team only
  when no current profile exists.
- Updated `int_players_unioned` so CS API current profile snapshots survive
  profile-level deduplication ahead of older provider profile rows.
- Verified live CS API on 2026-05-11: player `11893` is `zywoo`, team `9565`
  Vitality; CS API rankings have Vitality rank 1.
- Verification: `uv run ruff check .` passed; `uv run pytest` passed with
  230 tests and 1 existing Airflow warning. `uv run dbt parse --project-dir
  dbt_project --profiles-dir dbt_project` is blocked locally by missing
  `SNOWFLAKE_ACCOUNT`. `uv run mypy .` still fails on existing broad DAG/test
  typing issues and third-party stub gaps unrelated to this change.
- Removed historical Kaggle rows from modern mart lineage because Kaggle team IDs
  can be team-name strings while CS API player/team IDs are numeric HLTV-style
  IDs. `int_matches_unioned`, `int_players_unioned`, and `dim_teams` now exclude
  Kaggle, while raw/staging Kaggle loaders remain available for archival use.
- Verification after Kaggle removal: `uv run ruff check .` passed; `uv run
  pytest` passed with 231 tests and 1 existing Airflow warning; `dbt parse`
  passed with dummy Snowflake env vars and only existing accepted_values
  deprecation warnings.
- Removed the Kaggle pipeline entirely: bootstrap script, ingestion client,
  dbt raw/staging definitions, Snowflake setup tables/COPY statements, Airflow
  COPY statements, pytest fixtures/tests, config fields, dependency, and docs.
  The only remaining Kaggle text is in negative regression tests that assert the
  removed source does not re-enter modern marts. Verification: targeted pytest
  passed with 36 tests; `uv run ruff check .` passed; `uv run pytest` passed
  with 190 tests and 1 existing Airflow warning; `dbt parse --no-partial-parse`
  passed with dummy Snowflake env vars and existing accepted_values deprecation
  warnings.

- Reworked CS API player stats to use `/matches/` plus `/matches/{matchid}/stats`
  so each row has a real match ID and match date.
- Verified targeted pytest, ruff, mypy, and the full pytest suite.
- Blocked on live dbt run/test until the two new RAW tables are created in
  Snowflake by a role with ownership/DDL privileges on `CS2_ANALYTICS.RAW`.
