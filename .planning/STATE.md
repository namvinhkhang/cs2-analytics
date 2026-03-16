# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-16)

**Core value:** Three analytical products that answer questions HLTV.org never answers — surfaced from a production-grade pipeline that any interviewer can inspect end-to-end.
**Current focus:** Phase 1 — Data Ingestion

## Current Position

Phase: 1 of 6 (Data Ingestion)
Plan: 1 of TBD in current phase
Status: In progress
Last activity: 2026-03-16 — Completed plan 01-01 (project scaffold + data models)

Progress: [█░░░░░░░░░] 5%

## Performance Metrics

**Velocity:**
- Total plans completed: 1
- Average duration: 8 min
- Total execution time: 0.13 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-data-ingestion | 1 | 8 min | 8 min |

**Recent Trend:**
- Last 5 plans: 01-01 (8 min)
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Snowflake over BigQuery — better Airflow/dbt ecosystem docs
- [Init]: AWS S3 over GCS — higher intern posting frequency (72% vs 45%)
- [Init]: FACEIT as primary stats source — only official API with per-match ADR/KAST at semi-pro level
- [Init]: Kaggle CSV bootstrap for HLTV data — avoids ToS risk and Cloudflare blocking
- [Init]: Streamlit over Tableau/PowerBI — public URL + shows Python proficiency simultaneously
- [01-01]: Added pydantic.mypy plugin — resolves mypy strict-mode false positives on Settings() singleton
- [01-01]: conftest.py sets dummy env vars at collection time — allows test imports without .env present

### Pending Todos

None yet.

### Blockers/Concerns

- API rate limits: FACEIT ~1 req/s, PandaScore 1,000 req/hour — ingestion clients must implement backoff
- Snowflake $400 free trial credit is finite — avoid wasteful queries during development

## Session Continuity

Last session: 2026-03-16
Stopped at: Completed 01-01-PLAN.md (project scaffold, Settings class, canonical + per-source models)
Resume file: None
