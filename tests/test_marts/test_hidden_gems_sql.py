"""Contract tests for `mart_hidden_gems` Phase 4 requirements."""

from __future__ import annotations

from pathlib import Path

SQL_PATH = Path("dbt_project/models/marts/analytics/mart_hidden_gems.sql")


def test_hidden_gems_assigns_four_player_tiers() -> None:
    """HG-01 requires tier-4 for teams ranked 51+ or unranked."""
    sql = SQL_PATH.read_text()

    assert "between 31 and 50 then 3" in sql
    assert "else 4" in sql


def test_hidden_gems_compares_against_tier_above() -> None:
    """HG-03 requires tier 2+ players to beat thresholds from the tier above."""
    sql = SQL_PATH.read_text()

    assert "player_tier - 1" in sql
    assert "tier_above_thresholds" in sql
    assert "stats_above_tier_threshold" in sql


def test_hidden_gems_includes_90_day_trend_direction() -> None:
    """HG-04 requires an explicit 90-day rolling trend direction."""
    sql = SQL_PATH.read_text()

    assert "recent_90_day" in sql
    assert "previous_90_day" in sql
    assert "trend_direction" in sql
