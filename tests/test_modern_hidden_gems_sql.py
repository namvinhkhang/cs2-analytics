"""Contract tests for CS2-era Hidden Gem Scout data sources."""

from __future__ import annotations

from pathlib import Path


def test_dim_teams_uses_modern_rankings_before_kaggle_fallback() -> None:
    """Modern VRS rankings should outrank legacy Kaggle fallback rankings."""
    sql = Path("dbt_project/models/marts/core/dim_teams.sql").read_text()

    assert "stg_csapi_team_rankings" in sql
    assert "stg_kaggle_matches" in sql
    assert "ranking_source_priority" in sql
    assert "when 'liquipedia' then 1" in sql
    assert "when 'csapi' then 2" in sql
    assert "when 'kaggle' then 3" in sql


def test_player_leaderboard_uses_four_tiers() -> None:
    """HG-01 requires tier-4 instead of folding every rank 31+ player into tier 3."""
    sql = Path("dbt_project/models/marts/analytics/mart_player_leaderboard.sql").read_text()

    assert "between 31 and 50 then 3" in sql
    assert "else 4" in sql


def test_hidden_gems_exposes_prospect_score_without_tier4_fallback() -> None:
    """Hidden Gem Scout should rank real flags instead of accepting all tier-4 rows."""
    sql = Path("dbt_project/models/marts/analytics/mart_hidden_gems.sql").read_text()

    assert "prospect_score" in sql
    assert "where stats_above_tier_threshold >= 3" in sql
    assert "or player_tier = 4" not in sql
