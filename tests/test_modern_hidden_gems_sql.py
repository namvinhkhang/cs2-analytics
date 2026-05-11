"""Contract tests for CS2-era Hidden Gem Scout data sources."""

from __future__ import annotations

from pathlib import Path


def test_dim_teams_uses_only_current_ranking_sources() -> None:
    """Team IDs must come from sources with stable team IDs, not Kaggle names."""
    sql = Path("dbt_project/models/marts/core/dim_teams.sql").read_text()

    assert "stg_csapi_team_rankings" in sql
    assert "stg_liquipedia_teams" in sql
    assert "stg_valve_team_regions" in sql
    assert "stg_kaggle_matches" not in sql
    assert "kaggle_rankings" not in sql
    assert "ranking_source = 'kaggle'" not in sql
    assert "ranking_source_priority" in sql
    assert "when 'liquipedia' then 1" in sql
    assert "when 'csapi' then 2" in sql
    assert "coalesce(" in sql
    assert "vr.region" in sql


def test_valve_regions_do_not_replace_world_rankings() -> None:
    """Valve enrichment should fill missing geography without changing rank lineage."""
    dim_sql = Path("dbt_project/models/marts/core/dim_teams.sql").read_text()
    staging_sql = Path("dbt_project/models/staging/stg_valve_team_regions.sql").read_text()

    assert "stg_valve_team_regions" in dim_sql
    assert "world_ranking" not in staging_sql
    assert "global_rank" in staging_sql
    assert "c.world_ranking" in dim_sql


def test_dim_teams_lowercases_names_before_region_normalization() -> None:
    """Uppercase team names like FURIA and MOUZ must still match Valve regions."""
    sql = Path("dbt_project/models/marts/core/dim_teams.sql").read_text()
    compact_sql = "".join(sql.split())

    assert "regexp_replace(lower(" in compact_sql
    assert "normalized_team_name" in sql


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


def test_hidden_gems_uses_current_player_team_for_rankings() -> None:
    """Historical match teams should not decide a player's current hidden-gem tier."""
    sql = Path("dbt_project/models/marts/analytics/mart_hidden_gems.sql").read_text()

    assert "current_players as" in sql
    assert "coalesce(cp.current_team_id, s.team_id)" in sql
    assert "left join current_players cp" in sql


def test_player_leaderboard_uses_current_player_team_for_rankings() -> None:
    """Leaderboard tiers should follow dim_players' latest profile team."""
    sql = Path("dbt_project/models/marts/analytics/mart_player_leaderboard.sql").read_text()

    assert "current_players as" in sql
    assert "coalesce(cp.current_team_id, s.team_id)" in sql
    assert "left join current_players cp" in sql


def test_player_union_prefers_csapi_current_profiles() -> None:
    """Current CS API profile rows should survive profile-level deduplication."""
    sql = Path("dbt_project/models/intermediate/int_players_unioned.sql").read_text()

    assert "when match_id is null and source = 'csapi' then 1" in sql


def test_modern_intermediate_models_exclude_kaggle_sources() -> None:
    """Historical Kaggle rows should stay out of modern CS2 mart lineage."""
    matches_sql = Path("dbt_project/models/intermediate/int_matches_unioned.sql").read_text()
    players_sql = Path("dbt_project/models/intermediate/int_players_unioned.sql").read_text()
    schema_yml = Path("dbt_project/models/intermediate/intermediate.yml").read_text()

    assert "stg_kaggle_matches" not in matches_sql
    assert "stg_kaggle_players" not in players_sql
    assert "'kaggle'" not in schema_yml


def test_modern_match_union_includes_csapi_matches() -> None:
    """CS API matches should feed modern match facts for ranking-compatible analytics."""
    matches_sql = Path("dbt_project/models/intermediate/int_matches_unioned.sql").read_text()
    sources_yml = Path("dbt_project/models/sources.yml").read_text()
    staging_yml = Path("dbt_project/models/staging/staging.yml").read_text()
    intermediate_yml = Path("dbt_project/models/intermediate/intermediate.yml").read_text()

    assert "stg_csapi_matches" in matches_sql
    assert "raw_csapi_matches" in sources_yml
    assert "stg_csapi_matches" in staging_yml
    assert "values: ['faceit', 'pandascore', 'csapi']" in intermediate_yml


def test_upset_features_use_csapi_match_source() -> None:
    """Upset Predictor should avoid provider-ID joins by training on CS API matches."""
    sql = Path("dbt_project/models/marts/analytics/mart_upset_features.sql").read_text()

    assert "source = 'csapi'" in sql


def test_upset_features_expose_readable_team_names() -> None:
    """Dashboard watchlists should not force users to decode raw team IDs."""
    sql = Path("dbt_project/models/marts/analytics/mart_upset_features.sql").read_text()

    assert "team_a_name" in sql
    assert "team_b_name" in sql


def test_hidden_gems_expose_readable_team_names() -> None:
    """Hidden Gem Scout should filter and display prospects by team name."""
    sql = Path("dbt_project/models/marts/analytics/mart_hidden_gems.sql").read_text()

    assert "team_name" in sql
