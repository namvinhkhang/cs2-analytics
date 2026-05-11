# CS2-Era Hidden Gem Scout Implementation

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

- Reworked CS API player stats to use `/matches/` plus `/matches/{matchid}/stats`
  so each row has a real match ID and match date.
- Verified targeted pytest, ruff, mypy, and the full pytest suite.
- Blocked on live dbt run/test until the two new RAW tables are created in
  Snowflake by a role with ownership/DDL privileges on `CS2_ANALYTICS.RAW`.
