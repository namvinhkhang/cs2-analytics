"""Contract tests for Snowflake setup grants used by automation."""

from __future__ import annotations

from pathlib import Path


def test_transformer_can_load_valve_regions_from_raw_stage() -> None:
    """Dashboard refresh COPY needs table INSERT plus external stage usage."""
    sql = Path("dbt_project/setup/snowflake_setup.sql").read_text()

    assert "GRANT USAGE ON STAGE CS2_ANALYTICS.RAW.cs2_raw_stage TO ROLE TRANSFORMER" in sql
    assert "GRANT INSERT ON TABLE CS2_ANALYTICS.RAW.raw_valve_team_regions" in sql
