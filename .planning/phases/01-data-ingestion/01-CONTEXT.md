# Phase 1: Data Ingestion - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers a working Python ingestion layer that pulls raw CS2 match data from Liquipedia API v3, FACEIT API, PandaScore API, and Kaggle CSV bootstrap — serializes all output to Parquet via pyarrow — and lands it in AWS S3 under Hive-partitioned paths. Pydantic models validate all entities. A pytest suite with mocked HTTP responses covers all four clients. No Airflow orchestration yet — clients are standalone callables ready to be wrapped in DAGs in Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Project Layout & Config Management
- Package layout: `src/cs2_analytics/` with `ingestion/`, `models/`, `utils/` subdirs — standard src layout compatible with uv + pyproject.toml
- Config: `pydantic-settings` with `.env` file and a `Settings` class — type-safe, validated at startup, all API keys and AWS creds loaded here
- HTTP client: `httpx` with `AsyncClient` — modern, async-capable, consistent API across all four source clients
- Retry/backoff: `tenacity` library — `@retry` decorator with exponential backoff, configurable per-client via constants

### Ingestion Client Design
- Abstract base: `BaseAPIClient` ABC with `get()`, `paginate()`, and rate-limit hook — each source (Liquipedia, FACEIT, PandaScore) subclasses it
- Rate limiting: `asyncio.Semaphore` + per-client sleep tuned to each API's limit (FACEIT ~1 req/s, PandaScore ~0.27 req/s, Liquipedia ~10 req/s)
- Kaggle bootstrap: Dedicated `KaggleBootstrapIngester` class that reads local CSV and writes to same Parquet/S3 format as live clients — keeps pipeline uniform
- Logging: `structlog` for JSON-structured logs — pairs well with Airflow log capture in Phase 2

### S3 & Parquet Output Strategy
- S3 path partitioning: `raw/{source}/{entity_type}/year={y}/month={m}/day={d}/` — Hive-compatible, works with Athena and dbt external table scanning
- Parquet writer: `pyarrow` directly — lightweight, no pandas dependency for pure ingestion layer
- Write mode: Overwrite same S3 key on re-ingestion runs — idempotent daily runs, safe for Airflow retries
- S3 client: `boto3` directly — explicit, minimal extra dependencies

### Pydantic Models & Test Strategy
- Model scope: Shared `Match`, `Player`, `Team` canonical models + per-source raw models (e.g., `FACEITMatch`, `PandaScoreMatch`) that map to shared — clean source/domain separation
- Validation strictness: `model_config = ConfigDict(extra="ignore")` — tolerate undocumented API fields, strictly validate known fields
- pytest mocking: `respx` library — httpx-native request mocker, cleaner than `responses` for async clients
- Fixtures: `tests/fixtures/{source}/` directories with `.json` sample API response files — kept separate from test logic

### Claude's Discretion
- Internal utilities (S3 path builder, Parquet schema helpers) — implementation details at Claude's discretion
- Exact Pydantic field names for each source model — follow API response field naming with snake_case conversion
- pyproject.toml dependency grouping (dev vs runtime)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — fresh project, no existing code

### Established Patterns
- Python 3.12 with full type hints throughout (per PROJECT.md constraint)
- `uv` + `pyproject.toml` for dependency management (per PROJECT.md constraint)
- Stack locked: Python, Airflow, dbt Core, Snowflake, AWS S3, XGBoost, Streamlit, Docker, GitHub Actions

### Integration Points
- Phase 2 (Orchestration) will wrap these ingestion clients as Airflow operators/tasks — clients must be callable with no side effects beyond S3 writes
- Phase 3 (Warehouse & dbt) will read from the `raw/` S3 prefix — Hive partitioning must be consistent
- Snowflake external stage will point at `raw/` prefix for COPY INTO staging tables

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond what's captured in decisions — open to standard approaches for file naming, schema field ordering, and internal utility design.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
