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
    assert "recent_90_day_gap_to_tier_above" in sql
    assert "previous_90_day_gap_to_tier_above" in sql
    assert "gap_delta_to_tier_above" in sql
    assert "gap_growing" in sql
    assert "gap_shrinking" in sql
    assert "trend_direction" in sql


def test_hidden_gems_documents_clutch_rate_unavailable() -> None:
    """HG-02/HG-03 skip clutch rate until a player-level source exists."""
    sql = SQL_PATH.read_text()

    assert "clutch rate is not available" in sql.lower()
    assert "clutch_rate" not in sql


def test_hidden_gems_exposes_recent_sample_size_without_hard_filter() -> None:
    """Hidden Gem Scout should let the dashboard slider control the recent-map floor."""
    sql = SQL_PATH.read_text()

    assert "minimum_recent_90_day_maps" in sql
    assert "recent_90_day_maps_played" in sql
    assert "20 as minimum_recent_90_day_maps" in sql
    assert "meets_recent_sample_size" in sql
    assert "and recent_90_day_maps_played >= minimum_recent_90_day_maps" not in sql.lower()
