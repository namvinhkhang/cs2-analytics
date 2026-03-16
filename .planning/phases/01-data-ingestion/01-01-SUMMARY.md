---
phase: 01-data-ingestion
plan: 01
subsystem: models
tags: [pydantic-v2, pydantic-settings, uv, python-packaging, canonical-models, faceit, liquipedia, pandascore]

# Dependency graph
requires: []
provides:
  - src-layout Python package cs2_analytics installable via uv
  - Settings(BaseSettings) with CS2_ env prefix for all API keys and AWS config
  - Canonical Match, Player, Team models with extra="forbid"
  - Per-source raw models for FACEIT, Liquipedia, and PandaScore with extra="ignore" and to_canonical() methods
  - pyproject.toml with hatchling build backend, strict mypy/ruff config, asyncio_mode=auto pytest
affects: [02-ingestion-clients, 03-s3-utils, 04-tests]

# Tech tracking
tech-stack:
  added:
    - "httpx>=0.27 — async HTTP client"
    - "tenacity>=9.0 — retry decorator with exponential backoff"
    - "pydantic>=2.7 (resolved: 2.12.5) — v2 data validation"
    - "pydantic-settings>=2.3 (resolved: 2.13.1) — Settings from env vars"
    - "pyarrow>=16.0 (resolved: 23.0.1) — Parquet serialization"
    - "boto3>=1.35 (resolved: 1.42.68) — AWS S3 client"
    - "structlog>=24.0 (resolved: 25.5.0) — JSON-structured logging"
    - "kaggle>=1.6 (resolved: 2.0.0) — Kaggle dataset download"
    - "pytest>=8.0, pytest-asyncio>=0.23, respx>=0.21 — test stack"
    - "ruff>=0.4, mypy>=1.10, boto3-stubs[s3] — dev tools"
  patterns:
    - "Pydantic v2 ConfigDict pattern — model_config = ConfigDict(extra=...) not inner class Config"
    - "Source/canonical model split — per-source raw models (extra=ignore) map to canonical models (extra=forbid) via to_canonical()"
    - "Module-level settings singleton — Settings() instantiated at import time, fails fast on missing keys"
    - "TDD RED-GREEN pattern — failing tests committed before implementation"
    - "conftest.py env setup — dummy CS2_* vars set before test imports to prevent ValidationError"

key-files:
  created:
    - pyproject.toml
    - .env.example
    - src/cs2_analytics/__init__.py
    - src/cs2_analytics/utils/__init__.py
    - src/cs2_analytics/utils/config.py
    - src/cs2_analytics/ingestion/__init__.py
    - src/cs2_analytics/models/__init__.py
    - src/cs2_analytics/models/canonical.py
    - src/cs2_analytics/models/faceit.py
    - src/cs2_analytics/models/liquipedia.py
    - src/cs2_analytics/models/pandascore.py
    - tests/conftest.py
    - tests/test_config.py
    - tests/test_models.py
  modified:
    - pyproject.toml (added pydantic.mypy plugin after mypy strict errors)

key-decisions:
  - "Added pydantic.mypy plugin to resolve mypy strict-mode false positives on Settings() singleton"
  - "conftest.py sets dummy env vars at collection time so all test modules can import cs2_analytics.utils.config without crashing"
  - "Module-level settings singleton re-raises ValidationError — production code still crashes on missing keys"

patterns-established:
  - "Pattern: to_canonical() inside method body import — avoids circular imports if canonical module ever imports source models"
  - "Pattern: canonical models use extra=forbid, source models use extra=ignore — one strict schema, many forgiving inputs"
  - "Pattern: all optional stat fields default to None — profile records and per-match records share the same Player model"

requirements-completed: [ING-08]

# Metrics
duration: 8min
completed: 2026-03-16
---

# Phase 1 Plan 01: Project Scaffold and Data Models Summary

**Pydantic v2 src-layout package with canonical Match/Player/Team models and per-source FACEIT/Liquipedia/PandaScore raw models, all connected by to_canonical() mapping methods.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-16T14:23:55Z
- **Completed:** 2026-03-16T14:31:30Z
- **Tasks:** 2/2
- **Files modified:** 14

## Accomplishments

- Installed all runtime and dev dependencies via uv sync (51 packages total)
- Settings(BaseSettings) with CS2_ env prefix validates all 7 required keys at startup; raises pydantic_core.ValidationError on missing keys
- Canonical Match, Player, Team models with extra="forbid" enforce schema stability for downstream dbt models
- Per-source models (FACEITMatch, FACEITPlayer, LiquipediaTeam, LiquipediaPlayer, LiquipediaMatch, LiquipediaTournament, LiquipediaPlacement, PandaScoreMatch, PandaScorePlayer) with extra="ignore" tolerate undocumented API fields
- 29 tests passing (5 config + 24 model); mypy strict passes on models/ and utils/

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold project, install dependencies, create Settings class** - `b746f1b` (feat)
2. **Task 2: Implement canonical and per-source Pydantic v2 models** - `33d6e19` (feat)

## Files Created/Modified

- `pyproject.toml` — package config, hatchling build backend, uv deps, asyncio_mode=auto, strict mypy (pydantic plugin), ruff
- `.env.example` — all 7 CS2_* env vars documented with placeholder values
- `src/cs2_analytics/__init__.py` — package root with docstring
- `src/cs2_analytics/utils/config.py` — Settings(BaseSettings) with CS2_ prefix; module-level singleton
- `src/cs2_analytics/models/canonical.py` — Match, Player, Team with extra="forbid"
- `src/cs2_analytics/models/faceit.py` — FACEITMatch (to_canonical → Match), FACEITPlayer (to_canonical → Player)
- `src/cs2_analytics/models/liquipedia.py` — 5 models: LiquipediaTeam, LiquipediaPlayer, LiquipediaMatch (all with to_canonical), LiquipediaTournament, LiquipediaPlacement
- `src/cs2_analytics/models/pandascore.py` — PandaScoreMatch (to_canonical → Match), PandaScorePlayer (to_canonical → Player)
- `tests/conftest.py` — dummy CS2_* env vars set at collection time; dummy_env fixture for isolated tests
- `tests/test_config.py` — 5 Settings tests (TDD)
- `tests/test_models.py` — 24 model tests covering extra=forbid/ignore, to_canonical(), optional stats (TDD)

## Canonical Model Signatures

Wave 2 plans should copy these field contracts exactly:

```python
class Match(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    source: str           # "faceit" | "liquipedia" | "pandascore" | "kaggle"
    team_a_id: str
    team_b_id: str
    winner_id: str | None
    played_at: str        # ISO-8601 date string
    map_name: str | None = None

class Player(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: str
    source: str
    display_name: str
    team_id: str | None = None
    nationality: str | None = None
    kills: int | None = None
    deaths: int | None = None
    adr: float | None = None
    kd_ratio: float | None = None
    kast: float | None = None
    elo: int | None = None
    match_id: str | None = None
    recorded_at: str      # ISO-8601 date string

class Team(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: str
    source: str
    name: str
    region: str | None = None
    world_ranking: int | None = None
    ingested_at: str      # ISO-8601 date string
```

## Resolved Dependency Versions (from uv.lock)

| Library | Resolved Version |
|---------|-----------------|
| pydantic | 2.12.5 |
| pydantic-settings | 2.13.1 |
| pyarrow | 23.0.1 |
| boto3 | 1.42.68 |
| structlog | 25.5.0 |
| kaggle | 2.0.0 |
| httpx | 0.28.1 |
| tenacity | 9.1.4 |
| pytest | 9.0.2 |
| pytest-asyncio | 1.3.0 |
| respx | 0.22.0 |
| mypy | 1.19.1 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy strict-mode false positives on Settings() singleton**
- **Found during:** Task 2 (overall verification)
- **Issue:** mypy strict mode reported 6 "Missing named argument" errors for `settings = Settings()` — it couldn't infer that pydantic-settings populates fields from environment variables
- **Fix:** Added `plugins = ["pydantic.mypy"]` to `[tool.mypy]` in pyproject.toml; this plugin teaches mypy about BaseSettings field injection
- **Files modified:** pyproject.toml
- **Commit:** 33d6e19

**2. [Rule 2 - Missing functionality] Added conftest.py with dummy env vars**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** The module-level `settings = Settings()` singleton crashes at test collection time because no .env is present; tests importing the config module would fail before any test ran
- **Fix:** Created `tests/conftest.py` that sets dummy CS2_* env vars via `os.environ.setdefault()` before any test module imports the config module
- **Files modified:** tests/conftest.py (new file)
- **Commit:** b746f1b

**3. [Rule 1 - Bug] Fixed incorrect UNIX epoch in test fixture**
- **Found during:** Task 2 (TDD GREEN phase — first run)
- **Issue:** Test used epoch `1705363200` expecting `"2024-01-15"` but UTC conversion gives `"2024-01-16 00:00:00"` (that epoch is midnight UTC on Jan 16)
- **Fix:** Changed test epoch to `1705276800` which is `2024-01-15T00:00:00Z`
- **Files modified:** tests/test_models.py
- **Commit:** 33d6e19

## Self-Check: PASSED
