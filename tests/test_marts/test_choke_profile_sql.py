"""Contract tests for `mart_choke_profile` Phase 4 pressure metrics."""

from __future__ import annotations

from pathlib import Path

SQL_PATH = Path("dbt_project/models/marts/analytics/mart_choke_profile.sql")


def test_choke_profile_exposes_pressure_metric_availability_flags() -> None:
    """Unavailable halftime/bracket data should be explicit, not hidden in comments."""
    sql = SQL_PATH.read_text()

    assert "halftime_data_available" in sql
    assert "bracket_data_available" in sql
    assert "comeback_metric_type" in sql


def test_choke_profile_returns_winners_bracket_and_elimination_columns() -> None:
    """CC-04 output columns should exist even when source bracket data is unavailable."""
    sql = SQL_PATH.read_text()

    assert "elimination_win_pct" in sql
    assert "winners_bracket_win_pct" in sql
