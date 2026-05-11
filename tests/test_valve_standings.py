"""Tests for Valve regional standings parsing and ingestion helpers."""

from __future__ import annotations

from datetime import date

from cs2_analytics.ingestion.valve import (
    ValveSnapshotFileSet,
    build_valve_team_regions_s3_key,
    parse_valve_standings_snapshot,
    select_latest_snapshot,
)

VITALITY_ROW = (
    "| 1 | 2081 | Vitality | apEX, flameZ, mezii, ropz, ZywOo | "
    "[details](details/2026_05_04/0001--vitality--apex-flamez-mezii-ropz-zywoo.md) |"
)
NAVI_ROW = (
    "| 2 | 1885 | Natus Vincere | Aleksib, b1t, iM, makazze, w0nderful | "
    "[details](details/2026_05_04/0002--natus_vincere--aleksib-b1t-im-makazze-w0nderful.md) |"
)
STANDINGS_TABLE_HEADER = """| Standing | Points | Team Name | Roster | |
| :- | -: | :- | :- | :- |"""
REGIONAL_MARKDOWN = "\n".join(
    [
        "### Regional Standings for Europe as of 2026_05_04<br />",
        "<br />",
        STANDINGS_TABLE_HEADER,
        VITALITY_ROW,
        NAVI_ROW,
    ]
)
GLOBAL_MARKDOWN = "\n".join(
    [
        "### Standings as of 2026_05_04<br />",
        "<br />",
        STANDINGS_TABLE_HEADER,
        VITALITY_ROW,
        NAVI_ROW,
    ]
)


def test_parse_valve_standings_snapshot_extracts_region_without_replacing_rankings() -> None:
    records = parse_valve_standings_snapshot(
        snapshot_date=date(2026, 5, 4),
        regional_markdown_by_region={"Europe": REGIONAL_MARKDOWN},
        global_markdown=GLOBAL_MARKDOWN,
    )

    assert [record.team_name for record in records] == ["Vitality", "Natus Vincere"]
    assert records[0].normalized_team_name == "vitality"
    assert records[0].region == "Europe"
    assert records[0].regional_rank == 1
    assert records[0].global_rank == 1
    assert records[0].points == 2081
    assert records[0].detail_path == (
        "details/2026_05_04/0001--vitality--apex-flamez-mezii-ropz-zywoo.md"
    )
    assert "world_ranking" not in records[0].to_raw_record()


def test_select_latest_snapshot_requires_complete_regional_and_global_files() -> None:
    snapshot = select_latest_snapshot(
        years=["2025", "2026", "notes"],
        filenames=[
            "standings_americas_2026_04_06.md",
            "standings_asia_2026_04_06.md",
            "standings_europe_2026_04_06.md",
            "standings_global_2026_04_06.md",
            "standings_americas_2026_05_04.md",
            "standings_asia_2026_05_04.md",
            "standings_global_2026_05_04.md",
        ],
    )

    assert snapshot == ValveSnapshotFileSet(
        year=2026,
        snapshot_date=date(2026, 4, 6),
        regional_filenames={
            "Americas": "standings_americas_2026_04_06.md",
            "Asia": "standings_asia_2026_04_06.md",
            "Europe": "standings_europe_2026_04_06.md",
        },
        global_filename="standings_global_2026_04_06.md",
    )


def test_build_valve_team_regions_s3_key_uses_raw_valve_partition() -> None:
    key = build_valve_team_regions_s3_key(date(2026, 5, 4))

    assert key == "raw/valve/team_regions/year=2026/month=05/day=04/data.parquet"
