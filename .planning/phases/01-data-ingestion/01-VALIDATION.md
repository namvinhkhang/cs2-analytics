---
phase: 1
slug: data-ingestion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` section — Wave 0 creates |
| **Quick run command** | `uv run pytest tests/ingestion/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ingestion/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | ING-07 | unit | `uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | ING-08 | unit | `uv run pytest tests/models/ -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | ING-01 | unit | `uv run pytest tests/ingestion/test_liquipedia.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | ING-02 | unit | `uv run pytest tests/ingestion/test_faceit.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | ING-03 | unit | `uv run pytest tests/ingestion/test_pandascore.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | ING-04 | unit | `uv run pytest tests/ingestion/test_kaggle.py -x -q` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 2 | ING-05 | unit | `uv run pytest tests/ingestion/ -k "s3" -x -q` | ❌ W0 | ⬜ pending |
| 1-05-01 | 05 | 2 | ING-06 | unit | `uv run pytest tests/ingestion/ -k "retry or rate" -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — empty init
- [ ] `tests/ingestion/__init__.py` — empty init
- [ ] `tests/models/__init__.py` — empty init
- [ ] `tests/conftest.py` — shared fixtures (Settings, mock S3 client)
- [ ] `tests/fixtures/liquipedia/` — sample API response JSON files
- [ ] `tests/fixtures/faceit/` — sample API response JSON files
- [ ] `tests/fixtures/pandascore/` — sample API response JSON files
- [ ] `tests/fixtures/kaggle/` — sample CSV file
- [ ] `tests/ingestion/test_liquipedia.py` — stubs for ING-01
- [ ] `tests/ingestion/test_faceit.py` — stubs for ING-02
- [ ] `tests/ingestion/test_pandascore.py` — stubs for ING-03
- [ ] `tests/ingestion/test_kaggle.py` — stubs for ING-04
- [ ] `tests/models/test_models.py` — stubs for ING-08
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Parquet files appear in real AWS S3 bucket | ING-05 | Requires live AWS credentials and S3 bucket | Run `uv run python -m cs2_analytics.ingestion.faceit --dry-run=false` with real FACEIT API key + S3 bucket; check S3 console for `raw/faceit/` prefix |
| API rate limits not exceeded during live run | ING-06 | Requires real API calls to observe throttling behavior | Monitor API console rate counters during a short live run (~10 matches) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
