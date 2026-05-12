# v2 Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the project from a batch analytics portfolio app into a production-style analytics platform with infrastructure as code, stronger data quality, experiment tracking, BI access, Discord queries, and model iteration.

**Architecture:** Keep v1's warehouse-first contract, then add platform layers around it. Batch dbt marts remain the trusted source for analytics; MLflow tracks model experiments; BI and Discord read curated metrics, not raw tables.

**Tech Stack:** Snowflake, dbt, Terraform, AWS, Great Expectations, MLflow, Streamlit, Superset or Metabase, dbt Cloud Semantic Layer, Discord.py.

---

## v2 Workstreams

### 1. Infrastructure as Code

**Requirements:** INF-01

- [ ] Add Terraform project structure under `infra/terraform/`.
- [ ] Provision least-privilege AWS resources:
  - S3 raw and processed buckets,
  - IAM roles and policies,
  - secrets storage,
  - optional ECS or lightweight compute for scheduled ingestion.
- [ ] Keep Snowflake trial cost in mind; default modules should be low-cost and easy to destroy.
- [ ] Add `terraform fmt`, `terraform validate`, and README commands.
- [ ] Acceptance: a fresh AWS account can provision the required v2 infrastructure from code.

### 2. Data Quality Suite

**Requirements:** INF-02

- [ ] Add Great Expectations project under `great_expectations/`.
- [ ] Build suites for raw CS API ranking, match, and player-stat data.
- [ ] Validate schema, non-null identifiers, accepted ranges, freshness, duplicate keys, and row-count expectations.
- [ ] Run expectations after ingestion and before dbt.
- [ ] Store data docs as static artifacts.
- [ ] Acceptance: bad raw payload fixtures fail the suite before they reach marts.

### 3. MLflow Experiment Tracking

**Requirements:** INF-03

- [ ] Add MLflow dependency and local tracking configuration.
- [ ] Log Upset Tracker runs with feature set, split dates, threshold policy, metrics, artifacts, plots, and model file.
- [ ] Log Hidden Gem model experiments if the feature becomes supervised.
- [ ] Add model registry naming convention:
  - `upset_tracker`,
  - `hidden_gem_promoter`.
- [ ] Acceptance: retraining creates a reproducible MLflow run with all evaluation artifacts attached.

### 4. BI Layer

**Requirements:** BI-01, BI-02

- [ ] Pick Metabase or Superset after checking Snowflake connector friction and deployment cost.
- [ ] Build read-only Snowflake role for BI access.
- [ ] Publish dashboard templates for team performance, player leaderboard, hidden gems, upset history, and choke profile.
- [ ] Add dbt metrics/semantic definitions for win rate, upset rate, prospect score, pressure rating, and map win rate.
- [ ] Evaluate dbt Cloud Semantic Layer for metric serving.
- [ ] Acceptance: non-technical users can explore curated Snowflake marts without writing SQL.

### 5. Discord Bot

**Requirements:** INT-01

- [ ] Create a Discord bot service with slash commands:
  - `/team <name>`,
  - `/player <name>`,
  - `/upset <team_a> <team_b>`,
  - `/hidden-gems`,
  - `/choke-profile <team>`.
- [ ] Read only from marts or semantic-layer metrics.
- [ ] Add Snowflake query caching and command rate limits.
- [ ] Add deployment notes for local, Docker, and cloud deployment.
- [ ] Acceptance: the bot can answer common CS2 stats questions from the warehouse in under a few seconds.

### 6. Model Updates

**Requirements:** v2 model improvement

- [ ] Upset Tracker:
  - add historical ranking snapshots at match time,
  - add team recent form windows,
  - add map-pool strength when map data is available,
  - add roster stability features,
  - recalibrate probabilities after each retrain.
- [ ] Hidden Gem Scout:
  - start storing player/team snapshots daily,
  - create promotion labels when a player moves into a higher-tier team or sustained higher-tier performance window,
  - compare ranker models such as XGBoost ranker, LightGBM ranker, and calibrated classifier,
  - keep the current SQL scout as the explainable fallback.
- [ ] Add time-aware evaluation for both models.
- [ ] Acceptance: model updates beat v1 baselines on holdout metrics without data leakage.

## v2 Release Gate

- [ ] Terraform can provision and destroy infrastructure cleanly.
- [ ] Great Expectations blocks malformed raw data.
- [ ] MLflow tracks at least one retraining run with artifacts.
- [ ] BI dashboard connects to Snowflake with read-only access.
- [ ] Discord bot answers at least five warehouse-backed commands.
- [ ] Updated models document metrics, feature sets, limitations, and leakage checks.
