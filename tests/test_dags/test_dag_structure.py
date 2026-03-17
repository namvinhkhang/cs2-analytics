"""Structural DAG tests — verify all DAGs load and have correct properties.

These tests use DagBag to import DAG files, catching any import errors.
They validate schedule, catchup, and task_ids without executing tasks.
"""
from __future__ import annotations

import pytest
from airflow.models import DagBag


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder="airflow/dags", include_examples=False)


def test_no_import_errors(dagbag: DagBag) -> None:
    assert not dagbag.import_errors, f"DAG import errors: {dagbag.import_errors}"


def test_daily_matches_dag_exists(dagbag: DagBag) -> None:
    # Use dagbag.dags dict — avoids dagbag.get_dag() which queries the SQLite DB
    dag = dagbag.dags.get("cs2_daily_matches")
    assert dag is not None, "cs2_daily_matches DAG not found"


def test_daily_matches_schedule(dagbag: DagBag) -> None:
    dag = dagbag.dags.get("cs2_daily_matches")
    assert dag is not None
    assert str(dag.schedule_interval) == "0 */6 * * *"


def test_daily_matches_catchup_false(dagbag: DagBag) -> None:
    dag = dagbag.dags.get("cs2_daily_matches")
    assert dag is not None
    assert dag.catchup is False


def test_weekly_rankings_dag_exists(dagbag: DagBag) -> None:
    # This DAG is not yet implemented — expected to be None (RED stub)
    dag = dagbag.dags.get("cs2_weekly_rankings")
    assert dag is not None, "cs2_weekly_rankings DAG not found"


def test_weekly_rankings_schedule(dagbag: DagBag) -> None:
    dag = dagbag.dags.get("cs2_weekly_rankings")
    assert dag is not None
    assert str(dag.schedule_interval) == "@weekly"


def test_tournament_sync_dag_exists(dagbag: DagBag) -> None:
    # This DAG is not yet implemented — expected to be None (RED stub)
    dag = dagbag.dags.get("cs2_tournament_sync")
    assert dag is not None, "cs2_tournament_sync DAG not found"


def test_tournament_sync_schedule(dagbag: DagBag) -> None:
    dag = dagbag.dags.get("cs2_tournament_sync")
    assert dag is not None
    assert str(dag.schedule_interval) == "@daily"
