---
phase: 2
slug: orchestration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.23.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_dags/ -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_dags/ -x -q`
- **After every plan wave:** Run `uv run pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | ORC-01..05 | unit (stub) | `uv run pytest tests/test_dags/ -x -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | ORC-05 | manual (smoke) | `docker compose up -d && docker compose ps` | manual-only | ⬜ pending |
| 02-03-01 | 03 | 1 | ORC-01 | unit (structural) | `uv run pytest tests/test_dags/test_dag_structure.py::test_daily_matches_schedule -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 1 | ORC-01 | unit (logic) | `uv run pytest tests/test_dags/test_daily_matches.py -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 1 | ORC-02 | unit (structural) | `uv run pytest tests/test_dags/test_dag_structure.py -x` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 1 | ORC-03 | unit (structural) | `uv run pytest tests/test_dags/test_dag_structure.py -x` | ❌ W0 | ⬜ pending |
| 02-06-01 | 06 | 1 | ORC-04 | unit (logic) | `uv run pytest tests/test_dags/test_slack_alerts.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dags/__init__.py` — makes test_dags a package
- [ ] `tests/test_dags/conftest.py` — extends root conftest with `CS2_SLACK_WEBHOOK_URL` dummy and DagBag fixture
- [ ] `tests/test_dags/test_dag_structure.py` — stubs for ORC-01, ORC-02, ORC-03 structural requirements
- [ ] `tests/test_dags/test_daily_matches.py` — stubs for ORC-01 task logic with mocked clients
- [ ] `tests/test_dags/test_slack_alerts.py` — stubs for ORC-04 callback with mocked SlackWebhookHook
- [ ] `airflow/dags/utils/__init__.py` — package init for DAG utilities
- [ ] `apache-airflow` and `apache-airflow-providers-slack==8.7.1` added to `pyproject.toml` dev deps

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker compose up` starts full stack | ORC-05 | Requires Docker daemon, Postgres + Redis + Airflow startup in < 30s impractical in pytest | `docker compose up -d && docker compose ps` — all services should be healthy |
| `cs2_daily_matches` DAG appears green in Airflow UI | ORC-01 | Requires live Airflow instance | Trigger dag manually, verify green in UI |
| Slack webhook fires on DAG failure | ORC-04 | Requires live Slack workspace | Trigger `fail_intentionally` DAG, verify Slack message received |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
