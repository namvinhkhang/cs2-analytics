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


def test_choke_profile_uses_hltv_round_history_for_exact_choke_metrics() -> None:
    """Choke profile should be round-history backed, not only final-score backed."""
    sql = SQL_PATH.read_text().lower()

    assert "stg_hltv_round_history" in sql
    assert "largest_lead" in sql
    assert "halftime_leads_lost" in sql
    assert "clutch_data_available" in sql
    assert "hltv_unofficial" in sql


def test_choke_profile_joins_dim_teams_by_hltv_team_id() -> None:
    """HLTV round-history team IDs should map directly to dim_teams team IDs."""
    sql = SQL_PATH.read_text().lower()

    assert "on ta.team_id = t.team_id" in sql
    assert "regexp_replace(ta.team_name" not in sql
