from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DASHBOARD_RAW_LOADS = (
    ("raw_csapi_matches", "cs2_raw_stage/csapi/matches/"),
    ("raw_csapi_team_rankings", "cs2_raw_stage/csapi/team_rankings/"),
    ("raw_csapi_player_stats", "cs2_raw_stage/csapi/player_stats/"),
    ("raw_valve_team_regions", "cs2_raw_stage/valve/team_regions/"),
)
UNUSED_DASHBOARD_RAW_LOADS = (
    ("raw_faceit_matches", "cs2_raw_stage/faceit/matches/"),
    ("raw_pandascore_matches", "cs2_raw_stage/pandascore/matches/"),
    ("raw_faceit_players", "cs2_raw_stage/faceit/players/"),
    ("raw_pandascore_players", "cs2_raw_stage/pandascore/players/"),
    ("raw_liquipedia_teams", "cs2_raw_stage/liquipedia/teams/"),
)
WEEKLY_DASHBOARD_RAW_LOADS = (
    ("raw_hltv_round_history", "cs2_raw_stage/hltv_unofficial/round_history/"),
)


def test_dashboard_refresh_workflow_has_required_schedule_and_steps() -> None:
    workflow = REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml"

    text = workflow.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "17 10 * * 0,2-6" in text
    assert "43 11 * * 1" in text
    assert "contents: write" in text
    assert "uv run python scripts/bootstrap_csapi.py --profile" in text
    assert "uv run dbt deps --project-dir dbt_project" in text
    assert "uv run dbt run --select" in text
    assert "uv run dbt test --select" in text
    assert "uv run python -m ml.train" in text
    assert "uv run python -m dashboard.export_snapshots" in text
    assert "dashboard/snapshots" in text
    assert "SNOWFLAKE_PRIVATE_KEY" in text
    assert "CS2_AWS_S3_BUCKET" in text
    assert "AWS_ACCESS_KEY_ID" in text


def test_dashboard_refresh_workflow_keeps_daily_and_weekly_schedules_disjoint() -> None:
    """Weekly owns Monday so the hosted action does not ingest duplicate daily rows."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert 'cron: "17 10 * * 0,2-6"' in workflow
    assert 'cron: "17 10 * * 1"' not in workflow
    assert 'cron: "17 10 * * *"' not in workflow
    assert 'cron: "43 11 * * 1"' in workflow


def test_weekly_dashboard_refresh_uses_bounded_csapi_ingest_profile() -> None:
    """Weekly dashboard refresh should not run the deep CS API weekly profile."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert 'echo "csapi_profile=daily" >> "$GITHUB_OUTPUT"' in workflow
    assert '--profile "${{ steps.refresh.outputs.csapi_profile }}"' in workflow
    assert '--profile "${{ steps.refresh.outputs.profile }}"' not in workflow


def test_dashboard_refresh_workflow_loads_valve_regions_before_dbt() -> None:
    """The hosted snapshots need Valve region rows loaded before mart exports."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert "Ingest Valve team regions" in workflow
    assert "ingest_latest_team_regions_sync" in workflow
    assert "raw_valve_team_regions" in workflow
    assert "cs2_raw_stage/valve/team_regions/" in workflow


def test_dashboard_refresh_workflow_loads_active_raw_tables_before_dbt() -> None:
    """No-Airflow refreshes only load active dashboard sources before dbt."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert "Load raw Parquet data into Snowflake" in workflow
    for table, stage_prefix in EXPECTED_DASHBOARD_RAW_LOADS:
        assert table in workflow
        assert stage_prefix in workflow
    for table, stage_prefix in UNUSED_DASHBOARD_RAW_LOADS:
        assert table not in workflow
        assert stage_prefix not in workflow
    assert workflow.index("Load raw Parquet data into Snowflake") < workflow.index(
        "Run targeted dbt models",
    )


def test_dashboard_refresh_workflow_loads_only_current_raw_partition() -> None:
    """COPY should not scan every historical raw file on each scheduled run."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert "from datetime import date" in workflow
    assert (
        'current_partition = f"year={today.year}/month={today.month:02d}/day={today.day:02d}/"'
        in workflow
    )
    assert "stage_prefix = f\"{base_stage_prefix}{current_partition}\"" in workflow
    assert "FROM @{database}.RAW.{stage_prefix}" in workflow


def test_dashboard_refresh_workflow_only_loads_hltv_for_weekly_profile() -> None:
    """Daily refreshes should not require the optional manual HLTV raw table."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert 'REFRESH_PROFILE: ${{ steps.refresh.outputs.profile }}' in workflow
    assert 'refresh_profile = os.environ["REFRESH_PROFILE"]' in workflow
    assert 'WEEKLY_RAW_LOADS if refresh_profile == "weekly" else RAW_LOADS' in workflow
    for table, stage_prefix in WEEKLY_DASHBOARD_RAW_LOADS:
        assert table in workflow
        assert stage_prefix in workflow


def test_dashboard_refresh_workflow_exports_choke_snapshot_only_weekly() -> None:
    """Daily snapshot refresh should not query Choke until weekly HLTV/dbt runs."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert "Export dashboard snapshots" in workflow
    weekly_marts = "--mart mart_upset_features --mart mart_hidden_gems --mart mart_choke_profile"
    assert weekly_marts in workflow
    assert "--mart mart_upset_features --mart mart_hidden_gems" in workflow
    assert 'steps.refresh.outputs.profile }}" == "weekly"' in workflow


def test_dashboard_refresh_workflow_does_not_create_raw_tables() -> None:
    """Raw DDL is a setup/admin concern; CI should not need schema CREATE privileges."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert "CREATE TABLE IF NOT EXISTS" not in workflow
    assert "is missing or inaccessible" in workflow
    assert "dbt_project/setup/snowflake_setup.sql" in workflow


def test_dashboard_refresh_workflow_rebuilds_upstream_region_models() -> None:
    """Running only final marts can leave dim_teams stale after raw Valve ingestion."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert '+mart_upset_features +mart_hidden_gems' in workflow


def test_dashboard_refresh_workflow_rebases_artifact_commit_before_push() -> None:
    """Snapshot commits must handle remote main moving while the workflow runs."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert "git pull --rebase" in workflow
    assert "git push origin" in workflow
    assert "HEAD:${branch}" in workflow


def test_dbt_profile_exists_for_dashboard_refresh_workflow() -> None:
    """GitHub Actions dbt run needs to create the gitignored profiles-dir file."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml").read_text(
        encoding="utf-8",
    )

    assert "--profiles-dir dbt_project" in workflow
    assert "Generate dbt profile" in workflow
    assert "cat > dbt_project/profiles.yml" in workflow
    assert "cs2_analytics:" in workflow
    assert "SNOWFLAKE_PRIVATE_KEY_PATH" in workflow


def test_dashboard_refresh_workflow_is_not_gitignored() -> None:
    workflow = ".github/workflows/dashboard-refresh.yml"

    result = subprocess.run(
        ["git", "check-ignore", workflow],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr
