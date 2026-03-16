# Requirements: CS2 Pro Scene Analytics Platform

**Defined:** 2026-03-16
**Core Value:** Three analytical products that answer questions HLTV.org never answers — surfaced from a production-grade pipeline that any interviewer can inspect end-to-end.

## v1 Requirements

### Ingestion

- [x] **ING-01**: System ingests team, player, tournament, and placement data from Liquipedia API v3
- [x] **ING-02**: System ingests per-match statistics (kills, deaths, ADR, K/D, KAST, ELO) from FACEIT API
- [x] **ING-03**: System ingests tier-1 pro match results and player stats from PandaScore API
- [ ] **ING-04**: System loads historical match data from Kaggle CSV as one-time bootstrap
- [x] **ING-05**: All raw data serialized to Parquet with pyarrow and uploaded to AWS S3 under `raw/` prefix partitioned by date
- [x] **ING-06**: All API clients implement retry logic, rate limiting, and exponential backoff
- [ ] **ING-07**: pytest test suite covers all ingestion clients with mocked HTTP responses
- [x] **ING-08**: Pydantic data models defined for Match, Player, and Team entities

### Orchestration

- [ ] **ORC-01**: Airflow DAG `cs2_daily_matches` runs every 6h and ingests new match results
- [ ] **ORC-02**: Airflow DAG `cs2_weekly_rankings` runs weekly and ingests team rankings
- [ ] **ORC-03**: Airflow DAG `cs2_tournament_sync` syncs active tournament data
- [ ] **ORC-04**: All DAGs have failure alerting (email or Slack webhook)
- [ ] **ORC-05**: Docker Compose runs Airflow + Postgres metadata DB + Redis broker with one command

### Warehouse & dbt

- [ ] **WH-01**: Snowflake star schema defined: fact_matches, fact_player_stats, dim_teams, dim_players, dim_maps, dim_tournaments
- [ ] **WH-02**: dbt staging models clean raw Liquipedia, FACEIT, and PandaScore data (`stg_` prefix)
- [ ] **WH-03**: dbt intermediate models join and enrich data (`int_` prefix)
- [ ] **WH-04**: `mart_team_performance` — win rates, form, and rankings over time
- [ ] **WH-05**: `mart_player_leaderboard` — per-player stats with tier percentile rankings
- [ ] **WH-06**: `mart_map_meta` — pick/ban rates and side win rates over time
- [ ] **WH-07**: `mart_head2head` — all pairwise historical matchup records
- [ ] **WH-08**: `mart_upset_features` — pre-computed feature set for the Upset Tracker ML model
- [ ] **WH-09**: `mart_hidden_gems` — players flagged as outliers vs their tier cohort
- [ ] **WH-10**: `mart_choke_profile` — lead-blown, comeback, OT, and elimination records per team
- [ ] **WH-11**: dbt schema tests (not_null, unique, referential integrity) pass on all models
- [ ] **WH-12**: `dbt docs generate` produces full lineage documentation

### Upset Tracker

- [ ] **UP-01**: XGBoost classifier trained on mart_upset_features with temporal train/test split (no future leakage)
- [ ] **UP-02**: Model evaluated with ROC-AUC, calibration curve, and confusion matrix
- [ ] **UP-03**: SHAP values computed per prediction for explainability
- [ ] **UP-04**: Model saved with joblib and versioned in `ml/models/`
- [ ] **UP-05**: Model card (`ml/MODEL_CARD.md`) documents features, evaluation metrics, and known limitations

### Hidden Gem Scout

- [ ] **HG-01**: `mart_hidden_gems` assigns tier to each player based on team world ranking (tier-1: top 10, tier-2: 11-30, etc.)
- [ ] **HG-02**: Percentile rank computed for each player stat (rating, ADR, K/D, clutch rate) within their tier cohort
- [ ] **HG-03**: Players flagged when 3+ stats are in top 15th percentile of the tier above theirs
- [ ] **HG-04**: 90-day rolling trend computed per flagged player (gap growing or shrinking)

### Choke/Clutch Profile

- [ ] **CC-01**: `mart_choke_profile` computes lead-blown rate (lost after leading 10+ rounds)
- [ ] **CC-02**: Comeback rate computed (win % when trailing 3+ rounds at halftime)
- [ ] **CC-03**: Overtime record computed per team
- [ ] **CC-04**: Elimination match win % vs winners' bracket win % computed per team

### Dashboard

- [ ] **DASH-01**: Streamlit app has Home page explaining the project and linking to the three products
- [ ] **DASH-02**: Upset Tracker page shows upcoming matches ranked by upset probability with SHAP breakdown
- [ ] **DASH-03**: Hidden Gem Scout page shows leaderboard of flagged players with tier comparison and rolling trend sparklines
- [ ] **DASH-04**: Choke/Clutch Profile page shows team cards with all five pressure metrics, color-coded vs league average
- [ ] **DASH-05**: Dashboard deployed publicly on Streamlit Community Cloud with live URL
- [ ] **DASH-06**: `st.cache_data` with TTL aligned to Airflow schedule on all warehouse queries

### CI & Polish

- [ ] **CI-01**: GitHub Actions CI runs ruff, mypy, pytest, and `dbt test` on every PR
- [ ] **CI-02**: README includes architecture diagram, setup instructions, and demo screenshots/GIFs of all three products
- [ ] **CI-03**: Map meta Jupyter notebook produces Seaborn heatmaps with chi-square significance tests, exported as PDF

## v2 Requirements

### Streaming

- **STR-01**: Apache Kafka stream for live match events during active tournaments
- **STR-02**: Real-time dashboard updates during live matches

### Infrastructure

- **INF-01**: Terraform provisions all AWS infrastructure as code
- **INF-02**: Great Expectations data quality suite on raw ingested data
- **INF-03**: MLflow experiment tracking for Upset Tracker model iterations

### BI Layer

- **BI-01**: Metabase or Apache Superset as alternative BI layer over Snowflake
- **BI-02**: dbt Semantic Layer exposes metrics via dbt Cloud

### Integrations

- **INT-01**: Discord bot that queries the warehouse for CS2 stats on demand

## Out of Scope

| Feature | Reason |
|---------|--------|
| HLTV live scraping | Cloudflare-protected, ToS risk — use Kaggle CSV bootstrap instead |
| User accounts / authentication | Public read-only dashboard, no auth needed |
| Mobile app | Web-first only |
| R language | Python covers all needed analytics |
| Google Analytics integration | Not relevant to this project |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ING-01 | Phase 1 — Data Ingestion | Complete |
| ING-02 | Phase 1 — Data Ingestion | Complete |
| ING-03 | Phase 1 — Data Ingestion | Complete |
| ING-04 | Phase 1 — Data Ingestion | Pending |
| ING-05 | Phase 1 — Data Ingestion | Complete |
| ING-06 | Phase 1 — Data Ingestion | Complete |
| ING-07 | Phase 1 — Data Ingestion | Pending |
| ING-08 | Phase 1 — Data Ingestion | Complete |
| ORC-01 | Phase 2 — Orchestration | Pending |
| ORC-02 | Phase 2 — Orchestration | Pending |
| ORC-03 | Phase 2 — Orchestration | Pending |
| ORC-04 | Phase 2 — Orchestration | Pending |
| ORC-05 | Phase 2 — Orchestration | Pending |
| WH-01 | Phase 3 — Warehouse & dbt | Pending |
| WH-02 | Phase 3 — Warehouse & dbt | Pending |
| WH-03 | Phase 3 — Warehouse & dbt | Pending |
| WH-04 | Phase 3 — Warehouse & dbt | Pending |
| WH-05 | Phase 3 — Warehouse & dbt | Pending |
| WH-06 | Phase 3 — Warehouse & dbt | Pending |
| WH-07 | Phase 3 — Warehouse & dbt | Pending |
| WH-08 | Phase 3 — Warehouse & dbt | Pending |
| WH-09 | Phase 3 — Warehouse & dbt | Pending |
| WH-10 | Phase 3 — Warehouse & dbt | Pending |
| WH-11 | Phase 3 — Warehouse & dbt | Pending |
| WH-12 | Phase 3 — Warehouse & dbt | Pending |
| UP-01 | Phase 4 — Analytical Products | Pending |
| UP-02 | Phase 4 — Analytical Products | Pending |
| UP-03 | Phase 4 — Analytical Products | Pending |
| UP-04 | Phase 4 — Analytical Products | Pending |
| UP-05 | Phase 4 — Analytical Products | Pending |
| HG-01 | Phase 4 — Analytical Products | Pending |
| HG-02 | Phase 4 — Analytical Products | Pending |
| HG-03 | Phase 4 — Analytical Products | Pending |
| HG-04 | Phase 4 — Analytical Products | Pending |
| CC-01 | Phase 4 — Analytical Products | Pending |
| CC-02 | Phase 4 — Analytical Products | Pending |
| CC-03 | Phase 4 — Analytical Products | Pending |
| CC-04 | Phase 4 — Analytical Products | Pending |
| DASH-01 | Phase 5 — Dashboard & Deployment | Pending |
| DASH-02 | Phase 5 — Dashboard & Deployment | Pending |
| DASH-03 | Phase 5 — Dashboard & Deployment | Pending |
| DASH-04 | Phase 5 — Dashboard & Deployment | Pending |
| DASH-05 | Phase 5 — Dashboard & Deployment | Pending |
| DASH-06 | Phase 5 — Dashboard & Deployment | Pending |
| CI-01 | Phase 6 — CI & Polish | Pending |
| CI-02 | Phase 6 — CI & Polish | Pending |
| CI-03 | Phase 6 — CI & Polish | Pending |

**Coverage:**
- v1 requirements: 42 total
- Mapped to phases: 42
- Unmapped: 0

---
*Requirements defined: 2026-03-16*
*Last updated: 2026-03-16 — traceability updated to 6-phase roadmap structure*
