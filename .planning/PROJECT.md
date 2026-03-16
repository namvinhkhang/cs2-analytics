# CS2 Pro Scene Analytics Platform

## What This Is

A full-stack data engineering and analytics portfolio project built around Counter-Strike 2 professional esports data. Ingests match data from Liquipedia API v3, FACEIT API, and PandaScore into AWS S3, orchestrates transformations with Airflow and dbt on Snowflake, and serves three original analytical products — Upset Tracker, Hidden Gem Scout, and Choke/Clutch Profile — via a public Streamlit dashboard.

Designed to demonstrate every high-frequency skill found in Data Analytics and Data Engineering intern job postings in the US (2025–2026), with real results deployed publicly and shareable to the CS2 community.

## Core Value

Three analytical products that answer questions HLTV.org never answers — surfaced from a production-grade pipeline that any interviewer can inspect end-to-end.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] ELT pipeline ingests match data from Liquipedia API v3, FACEIT API, and PandaScore into AWS S3 (Parquet, partitioned by date)
- [ ] Apache Airflow DAGs orchestrate daily match ingestion, weekly rankings sync, and tournament sync — with retry logic and failure alerting
- [ ] Snowflake data warehouse with star schema (fact_matches, fact_player_stats, dim_teams, dim_players, dim_maps, dim_tournaments)
- [ ] dbt models: staging → intermediate → 7 analytical marts including mart_upset_features, mart_hidden_gems, mart_choke_profile
- [ ] Upset Tracker: XGBoost classifier predicting pre-tournament upsets with SHAP explainability
- [ ] Hidden Gem Scout: SQL-only outlier detection flagging tier-2/3 players performing at tier-1 statistical levels
- [ ] Choke/Clutch Profile: conditional SQL aggregations surfacing team pressure-situation behavioral patterns
- [ ] Streamlit dashboard (4 pages) deployed publicly on Streamlit Community Cloud
- [ ] GitHub Actions CI: ruff, mypy, pytest, dbt test on every PR
- [ ] Dockerized full stack (Airflow + Postgres + Redis) with one-command spin-up
- [ ] Map meta Jupyter report: Seaborn heatmaps + chi-square significance tests, exported as PDF writing sample
- [ ] Model card documenting Upset Tracker features, evaluation metrics, and known limitations

### Out of Scope

- HLTV scraping — Cloudflare-protected, ToS risk; use Kaggle CSV bootstrap instead
- Real-time Kafka streaming — stretch goal, not in v1
- Terraform IaC provisioning — stretch goal, not in v1
- Mobile app — not applicable
- User accounts / auth — public read-only dashboard only

## Context

- **Domain:** CS2 professional esports; CS2-specific data available from Sep 2023 onward
- **Data sources:** Liquipedia API v3 (free key, tournament/roster/placement metadata), FACEIT API (free key, richest per-match stats for semi-pro), PandaScore (free tier, tier-1 pro coverage), Kaggle CSV (bootstrap historical data)
- **Internship motivation:** Portfolio project targeting Data Analytics and Data Engineering intern roles at tech, fintech, gaming, and consulting companies. Skills matrix covers ~90% of intern posting requirements.
- **Audience:** Hiring managers + the CS2 community (Reddit, Twitter, Discord) — results must be shareable and defensible

## Constraints

- **Cloud:** AWS S3 for raw storage (5 GB free tier), Snowflake for warehouse ($400 free trial credit)
- **Deployment:** Streamlit Community Cloud (free, public URL)
- **APIs:** FACEIT free tier (~1 req/s safe), PandaScore free tier (1,000 req/hour), Liquipedia free key (~10 req/s)
- **No HLTV scraping:** Must not depend on HLTV as a live pipeline source
- **Python:** 3.12, type hints throughout, `uv` + `pyproject.toml`
- **Stack locked:** Python, Airflow, dbt Core, Snowflake, AWS S3, XGBoost, Streamlit, Docker, GitHub Actions

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Snowflake over BigQuery | Better Airflow/dbt ecosystem docs; $400 credit removes trial pressure | — Pending |
| AWS S3 over GCS | Higher frequency in intern job postings (72% vs 45%); 5 GB free tier | — Pending |
| FACEIT as primary stats source | Only official API with per-match ADR/KAST/kills at semi-pro level | — Pending |
| Kaggle CSV bootstrap for HLTV data | Avoids ToS risk and Cloudflare blocking on live pipeline | — Pending |
| Streamlit over Tableau/PowerBI | Deployable as public URL; shows Python + viz proficiency simultaneously | — Pending |

---
*Last updated: 2026-03-16 after initialization*
