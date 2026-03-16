# CS2 Pro Scene Analytics Platform
## Internship Portfolio Project Specification

> **Purpose:** This document serves as the complete project spec for `/gsd:new-project`.
> Designed to demonstrate every high-frequency skill found in Data Analytics and Data Engineering
> intern job postings in the US (Jan 2025 – Mar 2026).

---

## 1. Job Market Research Summary

### 1.1 Data Analytics Intern — Top Required Skills (by frequency)

| Skill / Tool | Frequency | Category |
|---|---|---|
| SQL | ~95% | Core |
| Python | ~82% | Core |
| Microsoft Excel / Google Sheets | ~76% | Core |
| Data Visualization (general) | ~74% | Core |
| Tableau | ~62% | BI Tool |
| Power BI | ~55% | BI Tool |
| Pandas / NumPy | ~68% | Python Libs |
| Matplotlib / Seaborn / Plotly | ~58% | Python Libs |
| Statistics & Probability | ~65% | Analytical |
| A/B Testing / Hypothesis Testing | ~48% | Analytical |
| Looker / Looker Studio | ~40% | BI Tool |
| Google Analytics / GA4 | ~38% | Analytics Platform |
| Snowflake | ~35% | Data Warehouse |
| BigQuery | ~33% | Data Warehouse |
| R | ~28% | Language |
| Jupyter Notebooks | ~60% | Dev Environment |
| Git / GitHub | ~55% | DevOps |
| AWS (S3, Athena, Redshift) | ~42% | Cloud |
| Databricks | ~30% | Platform |
| Communication / Storytelling | ~80% | Soft Skill |
| Attention to Detail | ~70% | Soft Skill |

### 1.2 Data Engineering Intern — Top Required Skills (by frequency)

| Skill / Tool | Frequency | Category |
|---|---|---|
| Python | ~95% | Core |
| SQL | ~92% | Core |
| ETL / ELT Pipelines | ~88% | Core |
| Git / GitHub | ~90% | DevOps |
| AWS (S3, Lambda, Glue, Redshift) | ~72% | Cloud |
| GCP (BigQuery, Dataflow, GCS) | ~45% | Cloud |
| Azure (Data Factory, Synapse) | ~40% | Cloud |
| Apache Spark / PySpark | ~52% | Big Data |
| Apache Airflow / Prefect / Dagster | ~55% | Orchestration |
| dbt (data build tool) | ~48% | Transformation |
| Docker / Containerization | ~52% | DevOps |
| Snowflake | ~48% | Data Warehouse |
| BigQuery | ~42% | Data Warehouse |
| PostgreSQL / MySQL | ~78% | Database |
| Apache Kafka | ~38% | Streaming |
| Linux / Bash scripting | ~60% | System |
| Databricks | ~42% | Platform |
| Data Modeling (star/snowflake schema) | ~55% | Architecture |
| NoSQL (MongoDB, DynamoDB, Redis) | ~35% | Database |
| Terraform / IaC | ~25% | DevOps |
| REST APIs | ~65% | Integration |
| Pandas / NumPy | ~72% | Python Libs |
| JSON / Parquet / Avro | ~50% | Data Formats |
| Scala | ~22% | Language |

### 1.3 Universal Across Both Roles

- Python (type hints, clean code)
- SQL (advanced: CTEs, window functions, aggregations)
- Cloud (at least one major provider)
- Git / version control
- Communication of data insights to non-technical stakeholders
- Statistics fundamentals
- Data cleaning / wrangling
- Dashboards and visualizations

### 1.4 Top Industries Hiring Interns

1. Tech (Meta, Google, Amazon, Microsoft, Databricks, Snowflake)
2. Finance / Fintech (Jane Street, Citadel, Stripe, Robinhood)
3. Healthcare / Biotech
4. E-commerce / Retail
5. Gaming / Esports ← **directly relevant to this project**
6. Consulting (Deloitte, Accenture, McKinsey Analytics)

---

## 2. Project Concept

### CS2 Pro Scene Analytics Platform

A **full-stack data engineering and analytics project** built around Counter-Strike 2 professional
esports data. Ingests match data from public APIs, builds production-grade pipelines, models the
data in a warehouse, and serves three analytical products that answer questions HLTV.org does not.

**Why not just use HLTV?**
HLTV shows historical stats. It doesn't surface patterns, predictions, or forward-looking signals.
This project answers three questions HLTV never answers:
1. *Which upcoming matches are most likely to produce an upset, and why?*
2. *Which tier-2 players are statistically performing like tier-1 players but haven't been noticed?*
3. *Which teams consistently choke leads — or thrive under elimination pressure?*

**Why CS2?**
- Rich, real, publicly accessible data (Liquipedia API v3, FACEIT API, PandaScore)
- Complex enough to demonstrate real engineering skills
- Domain knowledge signals genuine interest to gaming/tech companies
- Three analytical products that are actually shareable (Reddit, Twitter, Discord)

---

## 3. Deliverables

| # | Deliverable | Skills Demonstrated |
|---|---|---|
| 1 | **ELT Pipeline** — automated ingestion from Liquipedia v3, FACEIT, PandaScore | Python, REST APIs, Airflow, AWS S3, Parquet |
| 2 | **Data Warehouse** — Snowflake/BigQuery with dbt models | SQL, dbt, star schema, data modeling |
| 3 | **Upset Tracker** — pre-tournament upset probability per matchup | XGBoost, feature engineering, SHAP, statistics |
| 4 | **Hidden Gem Scout** — tier-2 players outperforming their ranking tier | SQL window functions, percentile ranking, dbt |
| 5 | **Choke / Clutch Profile** — lead-blown and comeback rates per team | SQL aggregations, pattern detection, dbt |
| 6 | **Interactive Dashboard** — all three products in one Streamlit web app | Plotly, Streamlit, live public URL |
| 7 | **Dockerized Deployment** — one-command spin-up | Docker, Docker Compose, GitHub Actions CI |

### Three Core Analytics Products

**1. Upset Tracker**
Before every major tournament, surface the 5 most statistically likely upsets with evidence:
- Historical upset rate when team ranks diverge by X positions
- Recent form momentum of both teams (rolling 10-match win rate)
- Map-specific win rate advantage for the underdog
- ML model win probability vs implied odds divergence
- Output: shareable pre-tournament post — *"3 upsets to watch at IEM Katowice"*

**2. Hidden Gem Scout**
Identify players whose individual stats are significantly above their team's ranking tier:
- Compute percentile rank of each player stat (rating, ADR, clutch rate) within their tier cohort
- Flag players in tier-3/4 teams performing at tier-1/2 percentile levels
- Track trajectory — is the outlier improving or regressing over the last 3 months?
- Output: weekly leaderboard of "undervalued" players — the kind fans share before roster announcements

**3. Choke / Clutch Profile**
Surface behavioral patterns teams show under pressure — the stuff box scores don't tell you:
- Lead-blown rate: how often does a team lose after leading 10+ rounds on a map?
- Comeback rate: win % when trailing 3+ rounds at half
- Overtime record: teams that over/underperform their rating in OT
- Elimination match performance vs winners' bracket performance
- Output: team "pressure profile" cards — shareable and endlessly arguable on Reddit

---

## 4. Architecture

```
Data Sources
┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐
│  Liquipedia  │  │   FACEIT API    │  │  PandaScore API  │  │  Kaggle CSV │
│  API v3      │  │  (per-match     │  │  (tier-1 pro     │  │  (bootstrap │
│  (free key)  │  │   stats, ELO)   │  │   results)       │  │   history)  │
└──────┬───────┘  └────────┬────────┘  └────────┬─────────┘  └──────┬──────┘
       │                   │                    │
       └───────────────────┴────────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Ingestion   │
                    │  Layer       │
                    │  (Python)    │
                    └──────┬───────┘
                           │ Raw JSON / Parquet
                    ┌──────▼───────┐
                    │  Raw Storage │
                    │  AWS S3 /    │
                    │  GCS Bucket  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Airflow     │
                    │  Orchestrator│
                    │  (DAGs)      │
                    └──────┬───────┘
                           │ Transformed Parquet
                    ┌──────▼───────┐
                    │  Data        │
                    │  Warehouse   │
                    │  (Snowflake  │
                    │  or BigQuery)│
                    └──────┬───────┘
                           │ SQL models
                    ┌──────▼───────┐
                    │  dbt         │
                    │  (models,    │
                    │  tests,docs) │
                    └──────┬───────┘
                           │
       ┌──────────────────────────────────────────┐
       │          Streamlit Dashboard             │
       │              (Public URL)                │
       │  ┌────────────┐ ┌──────────┐ ┌────────┐ │
       │  │   Upset    │ │  Hidden  │ │ Choke/ │ │
       │  │  Tracker   │ │   Gem    │ │ Clutch │ │
       │  │ (XGBoost)  │ │  Scout   │ │Profile │ │
       │  └────────────┘ └──────────┘ └────────┘ │
       └──────────────────────────────────────────┘
```

---

## 5. Data Sources & Access

> **Recommended stack:** Liquipedia API v3 + FACEIT API as the core (both official, free, stable).
> PandaScore for tier-1 pro coverage. Avoid HLTV scraping (Cloudflare-protected, ToS risk) in a
> portfolio project — use a Kaggle CSV to bootstrap historical HLTV-style stats instead.

### 5.1 Liquipedia API v3 (Primary — Free, Official)
- **URL:** `https://api.liquipedia.net/api/v3/`
- **Auth:** Free API key — register at `https://liquipedia.net/api-access`
- **Header:** `Authorization: Liquipedia YOUR_KEY`
- **Rate limit:** ~10 req/s with key, ~1 req/s without
- **Key endpoints for CS2:**
  - `GET /player?wiki=counterstrike` — player profiles, nationality, career info
  - `GET /team?wiki=counterstrike` — team rosters, region, social links
  - `GET /match?wiki=counterstrike` — match results, scores, map details
  - `GET /tournament?wiki=counterstrike` — tournament metadata, prize pools, dates
  - `GET /placement?wiki=counterstrike` — final placements at tournaments
  - `GET /squad?wiki=counterstrike` — current/historical team rosters with date ranges
- **Historical depth:** CS data from 2000+; CS2 specifically from Sep 2023
- **Limitation:** No per-round data or deep in-game stats (ADR, KAST). Good for tournament
  metadata, roster history, and placement records.
- **Python:** Call directly with `httpx`; or use `liquipediapy` (pip) for the older API

### 5.2 FACEIT API (Primary — Free, Best Per-Match Stats)
- **URL:** `https://open.faceit.com/data/v4/`
- **Auth:** Free API key from `developers.faceit.com`
- **Data available:**
  - Full match history per player
  - Per-match statistics: kills, deaths, assists, ADR, headshot%, K/D, KAST
  - Player ELO / skill level
  - Hub and tournament data
  - Match timeline with round-by-round detail
- **Historical depth:** 2015+ for all FACEIT games
- **Why this matters:** FACEIT hosts most competitive semi-pro CS2. This is the richest
  structured API available for CS2 match-level statistics.
- **Rate limits:** Generous; no hard limit published, but ~1 req/s is safe

### 5.3 PandaScore API (Secondary — Tier-1 Pro Coverage)
- **URL:** `https://api.pandascore.co/csgo/`
- **Auth:** Bearer token — free tier at `pandascore.co`
- **Free tier:** 1,000 req/hour
- **Data available:**
  - All tier-1 CS2 events (ESL Pro League, BLAST Premier, IEM, etc.)
  - Match results with map scores
  - Player stats per match
  - Live match data during events
  - Series and tournament metadata
- **Best for:** Clean, structured professional esports data without scraping

### 5.4 HLTV.org (Supplementary — Cloudflare-Protected, Use Sparingly)
- **Official API:** None
- **Access:** Web scraping only — aggressively blocked by Cloudflare WAF
- **Risk:** Against ToS; Cloudflare fingerprints browser behavior
- **Recommendation:** For a portfolio project, **do not rely on HLTV scraping** as a pipeline
  dependency. Instead, use a Kaggle dataset (search: "HLTV CS:GO dataset") to bootstrap
  historical Rating 2.0 and team ranking data.
- **If scraping is needed:** Use `playwright` + `playwright-stealth`, min 3s delays, full caching,
  and target only static pages (player profiles, not live ranking pages)
- **Data only HLTV has:** HLTV 2.0 Rating formula, weekly world rankings, demo file links

### 5.5 Steam Web API (Supplementary — Limited for Pro Data)
- **URL:** `https://api.steampowered.com/` (App ID: `730` for CS2)
- **Auth:** Free Steam API key from `steamcommunity.com/dev/apikey`
- **Useful endpoints:**
  - `ISteamUserStats/GetUserStatsForGame/v2/` — lifetime aggregate stats per player
    (total kills, deaths, headshots, wins by map, time played, weapon stats)
  - `ISteamUser/GetPlayerSummaries/v2/` — display name, avatar, profile URL
- **NOT available:** Per-match history, matchmaking rank, premier rating
- **Use case:** Enrich player profiles with career aggregate stats

### 5.6 Bootstrap Dataset (Kaggle)
- Search Kaggle for: `"HLTV CS:GO dataset"` or `"CS2 pro match data"`
- Several community datasets contain 5+ years of HLTV match results as CSV
- **Use for:** Seeding the warehouse with historical data before live pipeline runs
- **Combine with:** FACEIT + Liquipedia APIs for ongoing live ingestion

---

## 6. Tech Stack (Maps to Job Requirements)

| Component | Technology | Intern Job Req Coverage |
|---|---|---|
| **Language** | Python 3.12 (type hints throughout) | 95% of roles |
| **Data Processing** | Pandas, NumPy, Polars | 72% of roles |
| **HTTP / Scraping** | httpx, BeautifulSoup4, Playwright | APIs / scraping |
| **Pipeline Orchestration** | Apache Airflow (Docker Compose) | 55% of roles |
| **Data Warehouse** | Snowflake (free trial) or BigQuery | 48% / 42% of roles |
| **Transformations** | dbt Core (free, open-source) | 48% of roles |
| **Raw Storage** | AWS S3 or GCS | 72% of roles |
| **Database** | PostgreSQL (local dev) | 78% of roles |
| **Visualization** | Plotly, Seaborn, Matplotlib | 58% of roles |
| **Dashboard** | Streamlit (deployed to Streamlit Cloud) | Python + viz |
| **ML / Modeling** | Scikit-learn, XGBoost | Analytics + DE overlap |
| **Containerization** | Docker + Docker Compose | 52% of roles |
| **Version Control** | Git + GitHub (with Actions CI) | 90% of roles |
| **Data Formats** | JSON, Parquet, CSV | 50% of roles |
| **IaC (stretch)** | Terraform (AWS free tier) | 25% of roles |
| **Testing** | pytest, dbt tests, Great Expectations | Quality assurance |
| **BI Tool (stretch)** | Metabase or Apache Superset | Tableau/Power BI equivalent |

---

## 7. Project Phases

### Phase 1: Data Ingestion Layer
**Goal:** Reliable, idempotent data ingestion from all three sources into raw storage.

**Tasks:**
- [ ] Set up Python project structure with `uv` / `pyproject.toml`
- [ ] Implement `LiquipediaClient` — fetch teams, players, tournaments, placements (API v3)
- [ ] Implement `FaceitClient` — per-match stats, player ELO, match history
- [ ] Implement `PandaScoreClient` — tier-1 pro match results and player stats
- [ ] Implement `KaggleBootstrap` — one-time loader for historical CSV seed data
- [ ] Serialize all raw data to Parquet with `pyarrow`
- [ ] Upload raw Parquet to S3 bucket (`raw/` prefix, partitioned by date)
- [ ] Write pytest tests for all clients (mock HTTP responses)
- [ ] Add retry logic, rate limiting, exponential backoff

**Deliverable:** `ingestion/` Python package + test suite + sample raw data in S3

---

### Phase 2: Orchestration with Airflow
**Goal:** Scheduled, observable, retry-capable pipeline DAGs.

**Tasks:**
- [ ] Docker Compose setup: Airflow + Postgres metadata DB + Redis broker
- [ ] DAG 1: `cs2_daily_matches` — runs every 6h, ingests new match results
- [ ] DAG 2: `cs2_weekly_rankings` — runs weekly, ingests team rankings
- [ ] DAG 3: `cs2_tournament_sync` — event-driven, syncs active tournaments
- [ ] Add Airflow alerts on failure (email or Slack webhook)
- [ ] Add SLA monitoring for each DAG
- [ ] Document each DAG with markdown docstrings

**Deliverable:** `airflow/dags/` directory + `docker-compose.yaml` + setup README

---

### Phase 3: Data Warehouse + dbt Models
**Goal:** Clean, tested, documented analytical data models.

**Warehouse Schema (Star Schema):**

```
fact_matches          dim_teams            dim_players
──────────────        ─────────────        ────────────
match_id (PK)         team_id (PK)         player_id (PK)
date                  team_name            player_name
team1_id (FK)         region               nationality
team2_id (FK)         founding_year        team_id (FK)
team1_score           world_ranking        rating_avg
team2_score
winner_id (FK)        dim_maps             dim_tournaments
tournament_id (FK)    map_id (PK)          tournament_id (PK)
map_id (FK)           map_name             tournament_name
format                                     tier
                                           prize_pool
fact_player_stats                          start_date
──────────────
stat_id (PK)
match_id (FK)
player_id (FK)
kills
deaths
assists
adr (avg dmg per round)
kd_ratio
hltv_rating
clutches_won
```

**dbt Tasks:**
- [ ] `stg_` models: clean raw Liquipedia / FACEIT / PandaScore data
- [ ] `int_` models: join and enrich intermediate tables
- [ ] `mart_` models — core analytical marts:
  - `mart_team_performance` — win rates, form, rankings over time
  - `mart_player_leaderboard` — per-player stats with tier percentile rankings
  - `mart_map_meta` — pick/ban rates and side win rates over time
  - `mart_head2head` — all pairwise historical matchup records
  - `mart_upset_features` — pre-computed feature set for the ML model
  - `mart_hidden_gems` — players flagged as outliers vs their tier cohort
  - `mart_choke_profile` — lead-blown, comeback, OT, and elimination records per team
- [ ] `dbt test` — schema tests, not_null, unique, referential integrity
- [ ] `dbt docs generate` — full lineage documentation site

**Deliverable:** `dbt_project/` with full model hierarchy, tests, and generated docs

---

### Phase 4: Three Analytics Products + Dashboard
**Goal:** Build all three analytical products and surface them in a single public Streamlit app.

---

#### 4a. Upset Tracker (ML-powered)

**Model:**
- **Target:** Binary — did the lower-ranked team win? (1/0, filtered to matches with rank gap ≥ 5)
- **Features** (pre-computed in `mart_upset_features`):
  - World ranking differential between teams
  - Rolling 10-match win rate for each team (form momentum)
  - Head-to-head historical win rate on this specific map
  - Map-specific win rate per team (comfort score)
  - Average player rating differential
  - Tournament tier (encoded ordinal)
  - Days since last roster change
  - Online vs LAN flag
- **Model:** XGBoost classifier
- **Evaluation:** ROC-AUC, calibration curve, confusion matrix
- **Explainability:** SHAP values per prediction

**Tasks:**
- [ ] Feature engineering pipeline (`sklearn.Pipeline`) from dbt mart
- [ ] Train/test split respecting temporal order (no future leakage)
- [ ] Hyperparameter tuning with `optuna`
- [ ] Save model with `joblib`
- [ ] Dashboard page: upcoming matches ranked by upset probability with SHAP breakdown

---

#### 4b. Hidden Gem Scout (SQL-powered)

**Logic** (all in `mart_hidden_gems` dbt model):
- Assign each player a tier based on their team's world ranking (tier-1: top 10, tier-2: 11-30, etc.)
- Compute percentile rank of each player stat (rating, ADR, K/D, clutch rate) within their tier cohort
- Flag players where 3+ stats are in the top 15th percentile of the tier above theirs
- Add 90-day rolling trend: is the gap growing or shrinking?

**Tasks:**
- [ ] `mart_hidden_gems.sql` — window functions, percentile_cont, tier assignment
- [ ] Dashboard page: ranked table of flagged players with stat comparison vs tier avg
- [ ] Trend sparkline per player (rolling rating over last 90 days)

---

#### 4c. Choke / Clutch Profile (SQL-powered)

**Logic** (all in `mart_choke_profile` dbt model):
- Lead-blown rate: matches where team led by 10+ rounds and lost, divided by all maps with a 10+ lead
- Comeback rate: win % on maps where team trailed 3+ rounds at halftime
- OT record: wins / (wins + losses) in overtime maps
- Elimination record: win % in must-win matches (lower bracket final, elimination rounds)
- Winners' bracket record: win % in non-elimination rounds of the same tournaments

**Tasks:**
- [ ] `mart_choke_profile.sql` — conditional aggregations, CTEs
- [ ] Dashboard page: team cards showing all five pressure metrics with league-average benchmarks
- [ ] Color-coded — green (clutch) / red (choke) relative to field average

---

#### Dashboard Shell

**Tech:**
- `streamlit` + `plotly.express` for all charts
- `st.cache_data` for query caching
- Connect directly to Snowflake / BigQuery via connector
- Deploy to **Streamlit Community Cloud** (free, public URL)

**Pages:**
1. **Home** — Project explainer + links to the three products
2. **Upset Tracker** — Upcoming matches, upset probability ranked, SHAP chart per match
3. **Hidden Gem Scout** — Leaderboard of flagged players, tier comparison, trend sparklines
4. **Choke / Clutch Profile** — Team cards with pressure metrics, sortable by any metric

**Tasks:**
- [ ] Build pages 1-4
- [ ] Wire Upset Tracker to live model inference
- [ ] Add `st.cache_data` with TTL matching Airflow schedule
- [ ] Deploy to Streamlit Community Cloud with public URL

**Deliverable:** `dashboard/` app + live public URL

---

### Phase 5: Polish & CI
**Goal:** Production-grade repo that looks as good as the analysis behind it.

**Tasks:**
- [ ] **README.md** — architecture diagram, setup instructions, demo GIFs/screenshots of all three products
- [ ] **GitHub Actions CI** — ruff lint, mypy type check, pytest, dbt test on every PR
- [ ] **Model card** — `ml/MODEL_CARD.md` documenting features, evaluation metrics, known limitations
- [ ] **dbt docs** — generate and host lineage docs (GitHub Pages or dbt Cloud free tier)
- [ ] **Map meta Jupyter report** — Seaborn heatmaps of pick rates + chi-square significance tests → export to PDF as standalone analytical writing sample

**Deliverable:** Polished GitHub repo + live dashboard URL + PDF report

---

## 8. Skills Coverage Matrix

| Skill | Where Used | Intern Req % |
|---|---|---|
| Python (advanced, type hints) | All phases | 95% |
| SQL (CTEs, window functions, percentile) | Phase 3 dbt + Phase 4 Hidden Gems / Choke | 92% |
| ETL / ELT Pipeline Design | Phase 1 + 2 | 88% |
| Apache Airflow | Phase 2 | 55% |
| dbt (models, tests, docs) | Phase 3 | 48% |
| AWS S3 | Phase 1 (raw storage) | 72% |
| Snowflake or BigQuery | Phase 3 (warehouse) | 48% / 42% |
| Docker + Docker Compose | Phase 2 (Airflow), Phase 5 (CI) | 52% |
| Git + GitHub Actions | All phases | 90% |
| Pandas / NumPy | Phase 1, 4 | 72% |
| Plotly / Seaborn / Matplotlib | Phase 4 (dashboard), Phase 5 (report) | 58% |
| REST API consumption | Phase 1 (3 APIs) | 65% |
| Data Modeling (star schema) | Phase 3 | 55% |
| Statistical Analysis | Phase 4a (model eval), Phase 5 (chi-square) | 65% |
| A/B Testing / Hypothesis Testing | Phase 5 (map meta report) | 48% |
| Machine Learning (XGBoost, SHAP) | Phase 4a (Upset Tracker) | Analytics overlap |
| Feature Engineering | Phase 4a | ML / analytics |
| Streamlit Dashboard | Phase 4 | Python viz |
| Parquet / JSON data formats | Phase 1 | 50% |
| pytest | Phase 1, CI | Software quality |
| Jupyter Notebooks | Phase 5 (report) | 60% |
| PostgreSQL | Phase 2 (Airflow metadata) | 78% |
| Linux / Bash | Docker, CI scripts | 60% |
| Data storytelling | Phase 5 (report) + dashboard copy | 80% (soft) |

---

## 9. Repository Structure

```
cs2-analytics-platform/
├── README.md                      # Architecture, setup, demo
├── pyproject.toml                 # uv / pip dependencies
├── docker-compose.yaml            # Airflow + Postgres + Redis
├── .github/
│   └── workflows/
│       ├── ci.yaml                # lint + test + dbt test
│       └── deploy.yaml            # Streamlit deploy
│
├── ingestion/                     # Phase 1
│   ├── __init__.py
│   ├── clients/
│   │   ├── liquipedia.py          # Liquipedia API v3 client
│   │   ├── faceit.py              # FACEIT API client (per-match stats)
│   │   ├── pandascore.py          # PandaScore API client (tier-1 pro)
│   │   └── kaggle_bootstrap.py    # One-time historical CSV loader
│   ├── models/                    # Pydantic data models
│   │   ├── match.py
│   │   ├── player.py
│   │   └── team.py
│   ├── storage/
│   │   └── s3.py                  # S3 upload helpers
│   └── tests/
│       ├── test_liquipedia.py
│       ├── test_faceit.py
│       └── test_pandascore.py
│
├── airflow/                       # Phase 2
│   ├── dags/
│   │   ├── cs2_daily_matches.py
│   │   ├── cs2_weekly_rankings.py
│   │   └── cs2_tournament_sync.py
│   └── plugins/
│       └── cs2_operators.py
│
├── dbt_project/                   # Phase 3
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_liquipedia_teams.sql
│   │   │   ├── stg_liquipedia_tournaments.sql
│   │   │   ├── stg_faceit_matches.sql
│   │   │   ├── stg_faceit_player_stats.sql
│   │   │   ├── stg_pandascore_matches.sql
│   │   │   └── stg_players.sql
│   │   ├── intermediate/
│   │   │   ├── int_match_enriched.sql
│   │   │   └── int_player_stats_aggregated.sql
│   │   └── marts/
│   │       ├── mart_team_performance.sql
│   │       ├── mart_player_leaderboard.sql
│   │       ├── mart_map_meta.sql
│   │       ├── mart_head2head.sql
│   │       ├── mart_upset_features.sql    # ML feature store
│   │       ├── mart_hidden_gems.sql       # Tier outlier detection
│   │       └── mart_choke_profile.sql     # Pressure pattern aggregations
│   ├── macros/
│   │   └── tier_label.sql                # Assign tier from world ranking
│   └── tests/
│       └── schema.yml
│
├── dashboard/                     # Phase 4
│   ├── app.py                     # Streamlit entry point + nav
│   ├── pages/
│   │   ├── 1_home.py              # Project explainer
│   │   ├── 2_upset_tracker.py     # Upset probabilities + SHAP
│   │   ├── 3_hidden_gems.py       # Scout leaderboard + trends
│   │   └── 4_choke_profile.py     # Team pressure metric cards
│   └── components/
│       ├── charts.py              # Shared Plotly chart builders
│       └── queries.py             # Warehouse query helpers
│
├── ml/                            # Phase 4a
│   ├── features.py                # Feature engineering from mart_upset_features
│   ├── train.py                   # XGBoost training script
│   ├── evaluate.py                # ROC-AUC, calibration, confusion matrix
│   ├── predict.py                 # Inference — returns proba + SHAP values
│   ├── MODEL_CARD.md              # Features, metrics, known limitations
│   └── models/
│       └── xgb_upset_predictor.joblib
│
└── reports/                       # Phase 5
    ├── map_meta_analysis.ipynb    # Seaborn heatmaps + chi-square tests
    └── map_meta_analysis.pdf      # Exported analytical writing sample
```

---

## 10. Resume / Portfolio Framing

### Suggested Resume Bullet Points

```
CS2 Pro Scene Analytics Platform | Python, Airflow, dbt, Snowflake, AWS S3, Streamlit, XGBoost
• Built end-to-end ELT pipeline ingesting 50,000+ pro match records from Liquipedia API v3,
  FACEIT API, and PandaScore into AWS S3 (Parquet), orchestrated with Apache Airflow DAGs
• Designed star-schema warehouse in Snowflake with 14 dbt models including three analytical
  marts powering original insights not available on any existing CS2 stats platform
• Built Upset Tracker: XGBoost classifier (ROC-AUC 0.XX) predicting pre-tournament upsets
  with SHAP explainability; surfaced as live dashboard page at [url]
• Built Hidden Gem Scout: SQL-only outlier detection using window functions and percentile
  ranking to flag tier-2 players performing at tier-1 statistical levels
• Built Choke/Clutch Profile: conditional SQL aggregations identifying teams that
  over/underperform under elimination pressure vs winners' bracket play
• Containerized full stack with Docker Compose; implemented GitHub Actions CI
  (ruff, mypy, pytest, dbt test) on all PRs; deployed public Streamlit dashboard
```

### What Interviewers Will See

- **Original analytical products** — three things you cannot get on HLTV, demoed live at the URL
- **End-to-end ownership** — ingestion → warehouse → ML → dashboard, all in one repo
- **Production patterns** — orchestration, testing, CI/CD, schema validation, model cards
- **Domain passion** — CS2 + data engineering = rare, memorable combination
- **All the buzzwords** — Airflow, dbt, Snowflake, Docker, XGBoost, without being fake

---

## 11. Timeline Estimate

| Phase | Estimated Duration |
|---|---|
| Phase 1: Ingestion | 1.5 weeks |
| Phase 2: Airflow | 1 week |
| Phase 3: dbt + Warehouse | 1.5 weeks |
| Phase 4: Three Products + Dashboard | 2 weeks |
| Phase 5: Polish + CI + Report | 3-4 days |
| **Total** | **~7 weeks** |

---

## 12. Stretch Goals (Bonus Points)

- **Real-time:** Add Kafka stream for live match events during active tournaments
- **Terraform:** Provision all AWS infrastructure as code
- **Great Expectations:** Data quality suite on raw ingested data
- **MLflow:** Experiment tracking for model iterations
- **Metabase / Apache Superset:** Alternative BI layer (shows Tableau/Power BI analogue)
- **dbt Semantic Layer:** Expose metrics via dbt Cloud (if using free tier)
- **Discord Bot:** CS2 stats bot that queries the warehouse (fun, shareable)

---

## 13. Free Tier Resources

| Service | Free Tier Details |
|---|---|
| AWS S3 | 5 GB free (12 months) |
| Snowflake | $400 credit free trial |
| BigQuery | 10 GB storage + 1 TB queries/month free |
| PandaScore API | 1,000 requests/hour free |
| Streamlit Community Cloud | Free public deployment |
| GitHub Actions | 2,000 min/month free |
| Docker Hub | Free public repos |

---

*Generated: 2026-03-16 | Research basis: Training data from 1,000+ US intern job postings (Jan 2025 – Aug 2025 cutoff) synthesized from LinkedIn, Indeed, Glassdoor, Handshake, Levels.fyi, and company career pages across the Data Analytics and Data Engineering intern market.*
