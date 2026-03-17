---
phase: 01-data-ingestion
plan: 08
subsystem: testing
tags: [ruff, mypy, lint, type-annotations, pydantic, pyarrow, collections-abc]

# Dependency graph
requires:
  - phase: 01-data-ingestion
    provides: complete ingestion client test suite (plans 01-07)
provides:
  - zero ruff lint errors across src/ and tests/
  - mypy strict-mode clean across all 16 source files
  - ruff format applied to 24 files
affects: [02-airflow, 03-dbt, 04-analytics, 05-ci-cd]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sequence[BaseModel] over list[BaseModel] for covariant function parameters"
    - "type: ignore[import-untyped] inline comment for third-party libs without stubs (pyarrow, kaggle)"
    - "Unused context-manager variables renamed to _ to satisfy F841"

key-files:
  created: []
  modified:
    - src/cs2_analytics/ingestion/base.py
    - src/cs2_analytics/ingestion/kaggle.py
    - src/cs2_analytics/ingestion/liquipedia.py
    - src/cs2_analytics/models/faceit.py
    - src/cs2_analytics/models/liquipedia.py
    - src/cs2_analytics/models/pandascore.py
    - src/cs2_analytics/utils/parquet.py
    - src/cs2_analytics/utils/s3.py
    - tests/conftest.py
    - tests/test_base_client.py
    - tests/test_config.py
    - tests/test_faceit_client.py
    - tests/test_kaggle_ingester.py
    - tests/test_liquipedia_client.py
    - tests/test_parquet.py
    - tests/test_s3.py
    - tests/test_s3_utils.py

key-decisions:
  - "Use Sequence[BaseModel] instead of list[BaseModel] in models_to_records — list is invariant in mypy strict mode, Sequence is covariant"
  - "Add type: ignore[import-untyped] inline to pyarrow imports and deferred kaggle import — preferred over global ignore_missing_imports setting for precision"
  - "Rename unused context-manager aliases to _ (not suppress with noqa) — semantically clearer intent"

patterns-established:
  - "Covariance pattern: accept Sequence[T] for read-only container parameters, return list[T]"
  - "Untyped third-party lib pattern: # type: ignore[import-untyped] on the specific import line"

requirements-completed: [ING-01, ING-02, ING-03, ING-04, ING-05, ING-06, ING-07, ING-08]

# Metrics
duration: 5min
completed: 2026-03-17
---

# Phase 1 Plan 8: Lint Gap Closure Summary

**Eliminated all 48 ruff lint errors and 13 mypy strict-mode type issues, leaving the Phase 1 codebase fully clean for CI gate (0 ruff errors, 0 mypy errors, 158 tests green)**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-17T01:28:11Z
- **Completed:** 2026-03-17T01:32:37Z
- **Tasks:** 2
- **Files modified:** 24

## Accomplishments

- All 48 ruff errors resolved (45 via `--fix`, 3 F841 + 4 E501 manually)
- `uv run ruff check src/ tests/` exits 0 — All checks passed
- `uv run ruff format --check src/ tests/` exits 0 — 28 files already formatted
- `uv run mypy src/cs2_analytics/` exits 0 — Success: no issues found in 16 source files
- 158 tests pass (no regressions from any cleanup change)

## Error Code Breakdown

| Code | Count | Category | Resolution |
|------|-------|----------|-----------|
| I001 | 12 | Import sort | `ruff --fix` |
| F401 | 14 | Unused import | `ruff --fix` |
| UP037 | 8 | Quoted type annotation | `ruff --fix` |
| UP035 | 1 | AsyncIterator from typing | `ruff --fix` |
| UP017 | 1 | timezone.utc → datetime.UTC | `ruff --fix` |
| F841 | 3 | Unused local variable | Manual rename to `_` |
| E501 | 4 | Line too long | Manual line split |
| import-untyped | 3 | pyarrow/kaggle no stubs | `# type: ignore[import-untyped]` |
| arg-type | 5 | list[Match] vs list[BaseModel] | `Sequence[BaseModel]` param |
| type-arg | 1 | `list[dict]` missing params | `list[dict[str, Any]]` |

## Task Commits

1. **Task 1 + Task 2: ruff auto-fix, manual E501/F841, mypy fixes** - `763dd19` (fix)

## Files Created/Modified

- `src/cs2_analytics/ingestion/base.py` - UP035: AsyncIterator from collections.abc
- `src/cs2_analytics/ingestion/kaggle.py` - F401 unused imports; type: ignore[import-untyped] on deferred kaggle import
- `src/cs2_analytics/ingestion/liquipedia.py` - F401 unused import
- `src/cs2_analytics/models/faceit.py` - UP037 unquote return types; UP017 datetime.UTC
- `src/cs2_analytics/models/liquipedia.py` - F401 unused import; UP037 unquote return types
- `src/cs2_analytics/models/pandascore.py` - UP037 unquote return types; E501 comment split
- `src/cs2_analytics/utils/parquet.py` - I001 import sort; Sequence[BaseModel] param; type: ignore pyarrow
- `src/cs2_analytics/utils/s3.py` - list[dict[str, Any]] type param; type: ignore pyarrow imports
- `tests/conftest.py` - I001 import sort
- `tests/test_base_client.py` - I001 import sort; F401 unused patch
- `tests/test_config.py` - I001 import sort
- `tests/test_faceit_client.py` - F401 unused imports; F841 mock_write→_; I001; E501 docstring split
- `tests/test_kaggle_ingester.py` - F401 unused imports; F841 count→_; I001
- `tests/test_liquipedia_client.py` - F401 unused import; F841 mock_s3→_; E501 docstring split
- `tests/test_parquet.py` - F401 unused import; I001; E501 list literal split
- `tests/test_s3.py` - F401 unused imports; I001
- `tests/test_s3_utils.py` - F401 unused import; I001 (additional file beyond plan scope)

## Decisions Made

- `Sequence[BaseModel]` over `list[BaseModel]` in `models_to_records` — mypy strict mode treats `list` as invariant; `Sequence` is covariant and allows `list[Match]` to satisfy the parameter without casting
- Inline `# type: ignore[import-untyped]` per-import rather than global `ignore_missing_imports = true` — precise suppression, makes future stub additions easier to detect
- Renamed unused context-manager variables to `_` rather than deleting the `as` clause — preserves the patch object for tests that may need it in future but satisfies ruff's F841

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy arg-type variance errors (5 occurrences across 4 files)**
- **Found during:** Task 2 (post-ruff-fix mypy verification)
- **Issue:** `models_to_records(models: list[BaseModel])` — callers pass `list[Match]`, `list[Player]`, `list[Team]`. Mypy strict mode rejects this because `list` is invariant (even though `Match` is a subclass of `BaseModel`).
- **Fix:** Changed parameter type to `Sequence[BaseModel]` from `collections.abc`, which is covariant
- **Files modified:** `src/cs2_analytics/utils/parquet.py`
- **Verification:** `uv run mypy src/cs2_analytics/` exits 0; all 158 tests still pass
- **Committed in:** 763dd19

**2. [Rule 2 - Missing Critical] Added type: ignore[import-untyped] for pyarrow and kaggle**
- **Found during:** Task 2 (mypy verification)
- **Issue:** pyarrow and kaggle packages have no PEP 561 stubs and no `py.typed` marker. With `strict = true`, mypy reports `import-untyped` errors and skips analysis of calls into those libraries.
- **Fix:** Added `# type: ignore[import-untyped]` inline on pyarrow imports in parquet.py and s3.py, and on the deferred `import kaggle` in kaggle.py
- **Files modified:** `src/cs2_analytics/utils/parquet.py`, `src/cs2_analytics/utils/s3.py`, `src/cs2_analytics/ingestion/kaggle.py`
- **Verification:** `uv run mypy src/cs2_analytics/` exits 0
- **Committed in:** 763dd19

**3. [Rule 1 - Bug] Fixed missing type parameter in write_parquet_to_s3 signature**
- **Found during:** Task 2 (mypy verification)
- **Issue:** `records: list[dict]` — mypy strict mode requires explicit type params: `list[dict[str, Any]]`
- **Fix:** Updated to `list[dict[str, Any]]`
- **Files modified:** `src/cs2_analytics/utils/s3.py`
- **Verification:** mypy clean; tests pass
- **Committed in:** 763dd19

**4. [Note] test_s3_utils.py beyond plan scope — already had lint errors**
- The plan listed 15 files but `tests/test_s3_utils.py` also had I001 and F401 errors (added in a prior plan). Fixed by `ruff --fix` automatically alongside the listed files. Test count is 158 (not 147) because this file's tests were already there.

---

**Total deviations:** 3 auto-fixed (2 bug, 1 missing critical) + 1 scope note
**Impact on plan:** All auto-fixes required to meet the plan's mypy exit-0 success criterion. No scope creep beyond fixing pre-existing type issues exposed by the lint cleanup.

## Issues Encountered

- Plan anticipated exactly 45 ruff errors and 147 tests — actual was 48 errors and 158 tests due to `tests/test_s3_utils.py` (added in plan 07) being in scope but not listed in the error inventory. All errors were auto-fixed by `ruff --fix`.
- Plan anticipated mypy would be clean after UP037 removal — actual mypy had 13 pre-existing strict-mode failures (variance + untyped imports) that required 3 targeted fixes.

## Next Phase Readiness

- Phase 1 (Data Ingestion) is fully complete: 0 ruff errors, 0 mypy errors, 158 tests green, ruff format applied
- Ready for Phase 2 (Airflow DAGs) — all ingestion clients are tested, typed, and lint-clean

---
*Phase: 01-data-ingestion*
*Completed: 2026-03-17*

## Self-Check: PASSED

- [x] SUMMARY.md created at `.planning/phases/01-data-ingestion/01-08-SUMMARY.md`
- [x] Task commit `763dd19` exists in git log
- [x] `src/cs2_analytics/utils/parquet.py` exists with Sequence[BaseModel] fix
- [x] `uv run ruff check src/ tests/` exits 0
- [x] `uv run mypy src/cs2_analytics/` exits 0
- [x] 158 tests pass
