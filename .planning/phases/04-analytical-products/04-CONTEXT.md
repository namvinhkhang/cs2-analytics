# Phase 4: Analytical Products - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers all three analytical products as runnable, testable code: an XGBoost Upset Tracker ML model trained on warehouse mart data with SHAP explainability, a validated Hidden Gem Scout SQL mart with tier-percentile logic and 90-day trends, and a verified Choke/Clutch Profile mart covering all four pressure-situation metrics. Output is computable Python (`ml/`) plus patched dbt SQL — the dashboard (Phase 5) consumes these outputs directly.

</domain>

<decisions>
## Implementation Decisions

### ML Training Pipeline
- Training script lives at `ml/train.py` — pure Python, importable and testable (not a notebook)
- Read training data from Snowflake directly via `snowflake-connector-python` using `mart_upset_features`
- Use mart columns as-is (ranking_delta, score_diff, is_overtime, etc.) — all features pre-computed in Phase 3
- Temporal split: last 20% of rows by `played_at` date as holdout set (no future leakage)

### SHAP & Model Artifacts
- SHAP explainer: `TreeExplainer` — purpose-built for XGBoost, fastest and exact
- SHAP value storage: Parquet files under `ml/shap/` alongside the model artifacts
- SHAP timing: **computed at prediction time per-query** — load model + compute on-demand (not batch at training)
- Model versioning: semantic version suffix — `upset_tracker_v1.0.joblib` — explicit and human-readable

### Hidden Gem & Choke/Clutch SQL Completeness
- Patch `mart_hidden_gems` SQL to fully implement HG-01 through HG-04: tier assignment (top 10 = tier-1, 11-30 = tier-2, 31-50 = tier-3, 51+ = tier-4), 15th-percentile cross-tier flag, 90-day rolling trend via SQL window function
- Patch `mart_choke_profile` SQL to fully implement CC-01 through CC-04: lead-blown rate (lost after leading 10+ rounds), comeback rate (won when trailing 3+ at halftime), OT record, elimination vs winners' bracket win %
- Testing approach: pytest with DuckDB in-memory fixtures for SQL logic; `snowflake-connector-python` for ML integration tests against live Snowflake (skippable in CI without creds)

### Claude's Discretion
- Evaluation outputs (ROC-AUC score, calibration curve, confusion matrix) saved as `ml/evaluation/` artifacts
- Model card structure: plain Markdown with sections for features, evaluation metrics, known limitations, and version history

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dbt_project/models/marts/analytics/mart_upset_features.sql` — feature set with ranking_delta, score_diff, is_overtime, is_upset label already defined
- `dbt_project/models/marts/analytics/mart_hidden_gems.sql` — scaffold exists, needs tier + percentile + trend logic patched in
- `dbt_project/models/marts/analytics/mart_choke_profile.sql` — scaffold exists, needs all 4 CC metrics verified/patched
- `src/cs2_analytics/utils/config.py` — `Settings(BaseSettings)` with `CS2_*` env vars including Snowflake connection vars
- `airflow/dags/cs2_dbt_run.py` — BashOperator DAG pattern for running dbt, usable as reference for Snowflake connection pattern

### Established Patterns
- All Python: type hints throughout, `uv` + `pyproject.toml` dependency management
- Tests use `respx` for HTTP mocking; ML tests will use DuckDB fixtures for SQL and pytest parametrize
- `asyncio_mode = "auto"` in pytest; training script is sync (scikit-learn/XGBoost are sync)
- No bare except clauses; comprehensive error handling at system boundaries
- Settings validation: pass `_env_file=None` in tests to prevent `.env` leakage

### Integration Points
- `ml/train.py` reads from Snowflake (`CS2_SNOWFLAKE_*` env vars) → writes to `ml/models/` and `ml/evaluation/`
- Dashboard (Phase 5) will import `ml/` utilities for SHAP-at-prediction-time queries
- dbt mart patches stay in `dbt_project/models/marts/analytics/` — no schema changes needed

</code_context>

<specifics>
## Specific Ideas

- SHAP values computed at prediction time (not batch) — the dashboard will load the model and compute per-query
- Model file: `ml/models/upset_tracker_v1.0.joblib`
- Model card: `ml/MODEL_CARD.md`

</specifics>

<deferred>
## Deferred Ideas

- MLflow experiment tracking (v2 requirement INF-03) — deferred, not in v1
- Real-time SHAP for live matches — deferred until Phase 5 dashboard architecture is clear
- Momentum / win-streak derived features — phase 3 mart columns are sufficient for v1

</deferred>
