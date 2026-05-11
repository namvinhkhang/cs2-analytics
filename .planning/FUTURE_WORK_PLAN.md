# v1 Future Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining v1 product work by building a trustworthy Choke/Clutch team profile, adding daily and weekly CS API bootstrap profiles, and shipping one dashboard that presents Upset Tracker, Hidden Gem Scout, and Choke/Clutch Profile.

**Architecture:** Keep Snowflake and dbt as the source of truth. Ingestion profiles write raw Parquet, dbt converts raw data into stable marts, and the dashboard reads only marts plus versioned ML artifacts.

**Tech Stack:** Python, Pydantic, boto3, CS API, Snowflake, dbt, XGBoost, SHAP, Streamlit, Plotly, pytest.

---

## Current State

- Upset Tracker is trained from CS API-backed `mart_upset_features`.
- Hidden Gem Scout uses CS API player stats, current-team snapshots, team ranking tiers, tier-above thresholds, 90-day benchmark-gap trends, and a 20-row recent eligibility floor.
- Choke/Clutch Profile exists as a mart placeholder/proxy, but true lead-blown and halftime comeback metrics need round or half-level source data before they should be presented as exact.
- The dashboard is not started.

## Workstream 1: Choke/Clutch Team Profile

**Goal:** Produce a team-level pressure profile that is honest about data quality and upgrades from proxy metrics to exact metrics when source data exists.

**Files:**
- Modify: `src/cs2_analytics/ingestion/csapi.py`
- Modify: `src/cs2_analytics/models/csapi.py`
- Modify: `scripts/bootstrap_csapi.py`
- Modify or create: `dbt_project/models/staging/stg_csapi_rounds.sql`
- Modify: `dbt_project/models/marts/analytics/mart_choke_profile.sql`
- Modify: `dbt_project/models/marts/analytics/analytics.yml`
- Test: `tests/test_csapi_client.py`
- Test: `tests/test_marts/test_choke_profile_sql.py`

- [ ] Audit CS API, PandaScore, and FACEIT payloads for round score, halftime score, overtime, bracket stage, and elimination-match signals.
- [ ] Document which pressure metrics can be exact and which must remain proxy-based.
- [ ] Add failing tests for the chosen source payloads.
- [ ] Add typed raw model fields for the chosen round/half/bracket data.
- [ ] Extend `bootstrap_csapi.py` to ingest the selected pressure-profile source.
- [ ] Add raw Snowflake table, `COPY INTO`, dbt source, and staging model.
- [ ] Rebuild `mart_choke_profile` with:
  - lead-blown rate when leading by 10+ rounds,
  - comeback rate when trailing by 3+ rounds at halftime,
  - overtime win/loss record,
  - elimination-match win rate,
  - winners' bracket or non-elimination win rate,
  - metric quality flags when a metric is proxy-based.
- [ ] Add dbt schema tests for accepted values, non-negative counts, and one row per team grain.
- [ ] Verify with `uv run pytest tests/test_marts/test_choke_profile_sql.py tests/test_csapi_client.py`.
- [ ] Verify with `uv run dbt run --select mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project`.
- [ ] Verify with `uv run dbt test --select mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project`.
- [ ] Commit as `feat(choke-profile): compute team pressure metrics`.

## Workstream 2: CS API Bootstrap Profiles

**Goal:** Make `bootstrap_csapi.py` safe to run frequently by supporting explicit daily and weekly profiles with bounded API volume, clear logs, and environment overrides.

**Files:**
- Modify: `scripts/bootstrap_csapi.py`
- Modify: `airflow/dags/cs2_daily_matches.py` if daily orchestration exists
- Modify: `airflow/dags/cs2_weekly_rankings.py` if weekly orchestration exists
- Modify: `airflow/dags/cs2_dbt_run.py` if copy/dbt tasks need profile-specific raw tables
- Test: `tests/test_bootstrap_csapi.py` or nearest existing script test module

- [ ] Add CLI flags: `--profile daily`, `--profile weekly`, and `--profile backfill`.
- [ ] Keep all profile defaults overrideable through environment variables.
- [ ] Daily profile default:
  - ingest current team rankings,
  - refresh current player profile snapshots,
  - ingest recent matches and player stats with a small page cap,
  - run in less than one Snowflake credit cycle when followed by targeted dbt models.
- [ ] Weekly profile default:
  - ingest a deeper match window,
  - refresh rankings and player snapshots,
  - collect enough recent player stats for Hidden Gem rolling windows,
  - support continuation without duplicating existing S3 objects.
- [ ] Backfill profile default:
  - explicit opt-in only,
  - larger page caps,
  - resumable chunk logging,
  - no scheduled Airflow trigger by default.
- [ ] Add profile summary logging before ingestion starts.
- [ ] Add unit tests that each profile maps to the expected page limits and ingestion calls.
- [ ] Wire Airflow schedules so daily and weekly runs call the matching profile.
- [ ] Document recommended manual commands in `README.md` or setup docs.
- [ ] Verify with targeted pytest and `uv run ruff check .`.
- [ ] Commit as `feat(csapi): add bootstrap profiles`.

## Workstream 3: Product Dashboard

**Goal:** Build a public dashboard that presents every v1 feature without re-querying Snowflake on every page refresh.

**Files:**
- Create: `dashboard/Home.py`
- Create: `dashboard/pages/1_Upset_Tracker.py`
- Create: `dashboard/pages/2_Hidden_Gem_Scout.py`
- Create: `dashboard/pages/3_Choke_Clutch_Profile.py`
- Create: `dashboard/lib/snowflake.py`
- Create: `dashboard/lib/ml.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] Add Streamlit, Plotly, and dashboard-specific Snowflake dependencies.
- [ ] Add a shared Snowflake query helper that reads credentials from Streamlit secrets locally and in cloud.
- [ ] Add `st.cache_data` wrappers with TTL aligned to daily or weekly ingestion profile cadence.
- [ ] Home page:
  - show project status,
  - link to the three analytical products,
  - expose data freshness from the marts.
- [ ] Upset Tracker page:
  - show matches ranked by upset probability,
  - show model threshold and current model card summary,
  - show SHAP feature breakdown per selected match,
  - label predictions as watchlist signals, not certainties.
- [ ] Hidden Gem Scout page:
  - filter by tier, team, stat floor, and trend direction,
  - show current team, tier, ranking, prospect score, recent sample size, and benchmark-gap trend,
  - chart recent versus previous 90-day gap.
- [ ] Choke/Clutch Profile page:
  - show team pressure cards,
  - compare each team to league average,
  - expose metric quality flags.
- [ ] Add a smoke test or import test for every dashboard page.
- [ ] Run the app locally with `uv run streamlit run dashboard/Home.py`.
- [ ] Verify desktop and mobile layouts with screenshots before deployment.
- [ ] Deploy to Streamlit Community Cloud and add the URL to `README.md`.
- [ ] Commit as `feat(dashboard): add product dashboard`.

## Release Gate

- [ ] `uv run ruff check .` passes.
- [ ] `uv run pytest` passes.
- [ ] `uv run dbt run --project-dir dbt_project --profiles-dir dbt_project` passes against Snowflake.
- [ ] `uv run dbt test --project-dir dbt_project --profiles-dir dbt_project` passes against Snowflake.
- [ ] Dashboard smoke test passes.
- [ ] README has manual run commands for ingestion, dbt, ML training, and dashboard.
