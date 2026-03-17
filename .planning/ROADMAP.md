# Roadmap: CS2 Pro Scene Analytics Platform

## Overview

Six phases that deliver a production-grade ELT pipeline with three original analytical products, progressing from raw API ingestion through warehouse transformation, ML and SQL analytics, a public dashboard, and CI/documentation polish. Each phase is independently verifiable and unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data Ingestion** - Raw data from Liquipedia, FACEIT, PandaScore, and Kaggle lands in AWS S3 as Parquet (completed 2026-03-17)
- [ ] **Phase 2: Orchestration** - Airflow DAGs automate pipeline execution in a Docker-composed local stack
- [ ] **Phase 3: Warehouse & dbt** - Snowflake star schema with full dbt model lineage from staging to analytical marts
- [ ] **Phase 4: Analytical Products** - Upset Tracker (ML), Hidden Gem Scout (SQL), and Choke/Clutch Profile (SQL) are computed
- [ ] **Phase 5: Dashboard & Deployment** - Public Streamlit app on Streamlit Community Cloud serves all three products
- [ ] **Phase 6: CI & Polish** - GitHub Actions CI, map meta notebook, and portfolio-ready README finalize the project

## Phase Details

### Phase 1: Data Ingestion
**Goal**: Raw CS2 match data from all four sources lands reliably in S3 with validated schemas
**Depends on**: Nothing (first phase)
**Requirements**: ING-01, ING-02, ING-03, ING-04, ING-05, ING-06, ING-07, ING-08
**Success Criteria** (what must be TRUE):
  1. Running ingestion scripts for Liquipedia, FACEIT, and PandaScore produces `.parquet` files in S3 under `raw/` partitioned by date
  2. Kaggle CSV bootstrap loads historical data into S3 via a one-time script without errors
  3. All API clients retry on transient failures and respect rate limits without manual intervention
  4. `pytest` test suite runs green against all ingestion clients using mocked HTTP responses
  5. Pydantic models reject malformed Match, Player, and Team payloads with validation errors
**Plans**: 8 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold, Pydantic data models (ING-08)
- [ ] 01-02-PLAN.md — S3 upload utility + Parquet serialization utility (ING-05)
- [ ] 01-03-PLAN.md — BaseAPIClient ABC + FACEITClient with retry (ING-02, ING-06 partial)
- [ ] 01-04-PLAN.md — LiquipediaClient with 5 CS2 entity types (ING-01)
- [ ] 01-05-PLAN.md — PandaScoreClient with match and player ingestion (ING-03)
- [ ] 01-06-PLAN.md — Kaggle CSV bootstrap ingester + script (ING-04)
- [ ] 01-07-PLAN.md — Full pytest suite with respx + moto mocks (ING-06, ING-07)
- [ ] 01-08-PLAN.md — Gap closure: fix 45 ruff lint errors, apply ruff format (ING-01 through ING-08)

### Phase 2: Orchestration
**Goal**: Pipeline execution is automated, monitored, and reproducible via a one-command local stack
**Depends on**: Phase 1
**Requirements**: ORC-01, ORC-02, ORC-03, ORC-04, ORC-05
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts Airflow webserver, Postgres metadata DB, and Redis broker with no manual steps
  2. `cs2_daily_matches` DAG runs on schedule, ingests new matches, and appears green in Airflow UI
  3. `cs2_weekly_rankings` and `cs2_tournament_sync` DAGs run on their respective schedules without errors
  4. A deliberately failed DAG task triggers a failure alert (email or Slack webhook)
**Plans**: 5 plans

Plans:
- [ ] 02-01-PLAN.md — Wave 0: Test scaffolding, pyproject.toml Airflow deps (ORC-01..05)
- [ ] 02-02-PLAN.md — Docker Compose stack: Dockerfile + docker-compose.yml (ORC-05)
- [ ] 02-03-PLAN.md — Slack alerts utils + fail_intentionally DAG (ORC-04)
- [ ] 02-04-PLAN.md — cs2_daily_matches DAG + idempotency tests (ORC-01)
- [ ] 02-05-PLAN.md — cs2_weekly_rankings + cs2_tournament_sync DAGs (ORC-02, ORC-03)

### Phase 3: Warehouse & dbt
**Goal**: All raw data is cleaned, joined, and surfaced as seven analytical marts in Snowflake with full lineage
**Depends on**: Phase 2
**Requirements**: WH-01, WH-02, WH-03, WH-04, WH-05, WH-06, WH-07, WH-08, WH-09, WH-10, WH-11, WH-12
**Success Criteria** (what must be TRUE):
  1. Snowflake contains fact_matches, fact_player_stats, dim_teams, dim_players, dim_maps, dim_tournaments with no referential integrity violations
  2. `dbt run` completes successfully through staging, intermediate, and all seven mart layers
  3. `dbt test` passes all not_null, unique, and referential integrity tests across every model
  4. `dbt docs generate && dbt docs serve` renders a full lineage DAG viewable in a browser
  5. mart_upset_features, mart_hidden_gems, and mart_choke_profile contain non-empty data queryable from Snowflake
**Plans**: TBD

### Phase 4: Analytical Products
**Goal**: All three analytical products are computed and return correct, explainable results from warehouse data
**Depends on**: Phase 3
**Requirements**: UP-01, UP-02, UP-03, UP-04, UP-05, HG-01, HG-02, HG-03, HG-04, CC-01, CC-02, CC-03, CC-04
**Success Criteria** (what must be TRUE):
  1. XGBoost Upset Tracker trains on mart_upset_features with a temporal split, produces ROC-AUC and calibration curve outputs, and saves a versioned model file under `ml/models/`
  2. SHAP values are computed for each Upset Tracker prediction and are queryable per match
  3. Hidden Gem Scout flags at least one tier-2/3 player with 3+ stats in the top 15th percentile of the tier above, with a 90-day trend direction
  4. Choke/Clutch Profile returns lead-blown rate, comeback rate, OT record, and elimination vs winners' bracket win % for any queried team
  5. `ml/MODEL_CARD.md` documents Upset Tracker features, evaluation metrics, and known limitations
**Plans**: TBD

### Phase 5: Dashboard & Deployment
**Goal**: All three products are publicly accessible via a live Streamlit URL with correct caching and UX
**Depends on**: Phase 4
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06
**Success Criteria** (what must be TRUE):
  1. A public Streamlit Community Cloud URL loads the Home page explaining the project and linking to all three products
  2. Upset Tracker page displays upcoming matches ranked by upset probability with SHAP feature breakdowns visible
  3. Hidden Gem Scout page shows a leaderboard of flagged players with tier comparison and rolling trend sparklines
  4. Choke/Clutch Profile page shows team cards with all five pressure metrics color-coded against league average
  5. All warehouse queries use `st.cache_data` with TTL aligned to Airflow schedule, so repeated page loads do not re-query Snowflake
**Plans**: TBD

### Phase 6: CI & Polish
**Goal**: The project passes automated quality gates on every PR and is fully presentable to hiring managers and the CS2 community
**Depends on**: Phase 5
**Requirements**: CI-01, CI-02, CI-03
**Success Criteria** (what must be TRUE):
  1. Opening a PR triggers GitHub Actions CI that runs ruff, mypy, pytest, and `dbt test`, blocking merge on any failure
  2. README contains an architecture diagram, setup instructions, and demo screenshots or GIFs covering all three products
  3. Map meta Jupyter notebook runs end-to-end and exports a PDF containing Seaborn heatmaps with chi-square significance test results
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Ingestion | 8/8 | Complete    | 2026-03-17 |
| 2. Orchestration | 0/5 | Not started | - |
| 3. Warehouse & dbt | 0/TBD | Not started | - |
| 4. Analytical Products | 0/TBD | Not started | - |
| 5. Dashboard & Deployment | 0/TBD | Not started | - |
| 6. CI & Polish | 0/TBD | Not started | - |
