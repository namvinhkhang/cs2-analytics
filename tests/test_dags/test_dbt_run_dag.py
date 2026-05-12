"""Structural tests for cs2_dbt_run Airflow DAG.

Validates DAG structure, task count, schedule, and dependency chain
without requiring Snowflake or dbt connections.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_RAW_LOADS = (
    ("raw_faceit_matches", "cs2_raw_stage/faceit/matches/"),
    ("raw_pandascore_matches", "cs2_raw_stage/pandascore/matches/"),
    ("raw_csapi_matches", "cs2_raw_stage/csapi/matches/"),
    ("raw_csapi_team_rankings", "cs2_raw_stage/csapi/team_rankings/"),
    ("raw_csapi_player_stats", "cs2_raw_stage/csapi/player_stats/"),
    ("raw_valve_team_regions", "cs2_raw_stage/valve/team_regions/"),
    ("raw_hltv_round_history", "cs2_raw_stage/hltv_unofficial/round_history/"),
    ("raw_faceit_players", "cs2_raw_stage/faceit/players/"),
    ("raw_pandascore_players", "cs2_raw_stage/pandascore/players/"),
    ("raw_liquipedia_teams", "cs2_raw_stage/liquipedia/teams/"),
)


class TestDbtRunDagStructure:
    """cs2_dbt_run DAG structural validation."""

    def test_dag_loads(self, dagbag) -> None:
        """cs2_dbt_run DAG loads without import errors."""
        dag = dagbag.dags.get("cs2_dbt_run")
        assert dag is not None, "cs2_dbt_run DAG not found in DagBag"

    def test_dag_has_three_tasks(self, dagbag) -> None:
        """cs2_dbt_run has exactly 3 tasks."""
        dag = dagbag.dags.get("cs2_dbt_run")
        assert dag is not None
        assert len(dag.tasks) == 3

    def test_dag_task_ids(self, dagbag) -> None:
        """cs2_dbt_run task IDs match expected pipeline."""
        dag = dagbag.dags.get("cs2_dbt_run")
        assert dag is not None
        task_ids = {t.task_id for t in dag.tasks}
        assert task_ids == {"copy_into_raw", "dbt_run", "dbt_test"}

    def test_dag_schedule(self, dagbag) -> None:
        """cs2_dbt_run runs daily at 08:00 UTC."""
        dag = dagbag.dags.get("cs2_dbt_run")
        assert dag is not None
        # schedule_interval is set on the dag object from the @dag decorator
        assert dag.schedule_interval == "0 8 * * *" or str(dag.timetable) == "0 8 * * *"

    def test_dag_tags(self, dagbag) -> None:
        """cs2_dbt_run has cs2 and warehouse tags."""
        dag = dagbag.dags.get("cs2_dbt_run")
        assert dag is not None
        assert "cs2" in dag.tags
        assert "warehouse" in dag.tags

    def test_task_dependencies(self, dagbag) -> None:
        """Pipeline order: copy_into_raw >> dbt_run >> dbt_test."""
        dag = dagbag.dags.get("cs2_dbt_run")
        assert dag is not None
        task_dict = {t.task_id: t for t in dag.tasks}

        # copy_into_raw has no upstream deps — it is the first task in the pipeline
        assert len(task_dict["copy_into_raw"].upstream_task_ids) == 0
        # dbt_run depends on copy_into_raw completing successfully
        assert "copy_into_raw" in task_dict["dbt_run"].upstream_task_ids
        # dbt_test depends on dbt_run completing successfully
        assert "dbt_run" in task_dict["dbt_test"].upstream_task_ids

    def test_copy_into_raw_loads_all_staged_raw_parquet_sources(self) -> None:
        """Airflow must load every staged raw Parquet prefix before dbt runs."""
        dag_source = (REPO_ROOT / "airflow" / "dags" / "cs2_dbt_run.py").read_text(
            encoding="utf-8",
        )

        for table, stage_prefix in EXPECTED_RAW_LOADS:
            assert table in dag_source
            assert stage_prefix in dag_source
