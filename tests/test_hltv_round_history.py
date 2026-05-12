"""Tests for HLTV unofficial round-history normalization."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from cs2_analytics.ingestion.hltv import parse_hltv_map_stats_files, write_round_history_parquet
from cs2_analytics.models.hltv import HLTVMatchMapStats


def _sample_map_stats() -> dict[str, object]:
    return {
        "id": 228493,
        "matchId": 2394126,
        "map": "Ancient",
        "date": 1778402400000,
        "team1": {"id": 6248, "name": "The MongolZ"},
        "team2": {"id": 7020, "name": "Spirit"},
        "event": {"id": 8049, "name": "PGL Astana 2026"},
        "startSides": {"team1": "T", "team2": "CT"},
        "overtimeStartSides": [
            {"team1": "CT", "team2": "T"},
            {"team1": "T", "team2": "CT"},
        ],
        "result": {
            "team1TotalRounds": 16,
            "team2TotalRounds": 19,
            "halfResults": [
                {"team1Rounds": 4, "team2Rounds": 8},
                {"team1Rounds": 8, "team2Rounds": 4},
                {"team1Rounds": 4, "team2Rounds": 7},
            ],
        },
        "roundHistory": [
            {
                "round": 1,
                "winner": 2,
                "outcome": "bomb_defused",
                "score": "0-1",
                "isOvertime": False,
            },
            {"round": 12, "winner": 1, "outcome": "t_win", "score": "4-8", "isOvertime": False},
            {
                "round": 13,
                "winner": 1,
                "outcome": "bomb_defused",
                "score": "5-8",
                "isOvertime": False,
            },
            {"round": 25, "winner": 2, "outcome": "ct_win", "score": "12-13", "isOvertime": True},
        ],
    }


def test_hltv_map_stats_round_history_maps_side_winners_to_team_winners() -> None:
    """Round history should preserve side context and team winner identity."""
    stats = HLTVMatchMapStats.model_validate(_sample_map_stats())

    records = stats.to_round_records(ingested_at="2026-05-11")

    assert records == [
        {
            "source": "hltv_unofficial",
            "map_stats_id": "228493",
            "match_id": "2394126",
            "event_id": "8049",
            "event_name": "PGL Astana 2026",
            "map_name": "Ancient",
            "played_at": "2026-05-10",
            "round_number": 1,
            "t_team_id": "6248",
            "t_team_name": "The MongolZ",
            "ct_team_id": "7020",
            "ct_team_name": "Spirit",
            "winner_side": "ct",
            "winner_team_id": "7020",
            "winner_team_name": "Spirit",
            "team1_id": "6248",
            "team1_name": "The MongolZ",
            "team2_id": "7020",
            "team2_name": "Spirit",
            "score_team1_after": 0,
            "score_team2_after": 1,
            "reported_score": "0-1",
            "round_outcome": "bomb_defused",
            "is_overtime": False,
            "ingested_at": "2026-05-11",
        },
        {
            "source": "hltv_unofficial",
            "map_stats_id": "228493",
            "match_id": "2394126",
            "event_id": "8049",
            "event_name": "PGL Astana 2026",
            "map_name": "Ancient",
            "played_at": "2026-05-10",
            "round_number": 12,
            "t_team_id": "6248",
            "t_team_name": "The MongolZ",
            "ct_team_id": "7020",
            "ct_team_name": "Spirit",
            "winner_side": "t",
            "winner_team_id": "6248",
            "winner_team_name": "The MongolZ",
            "team1_id": "6248",
            "team1_name": "The MongolZ",
            "team2_id": "7020",
            "team2_name": "Spirit",
            "score_team1_after": 4,
            "score_team2_after": 8,
            "reported_score": "4-8",
            "round_outcome": "t_win",
            "is_overtime": False,
            "ingested_at": "2026-05-11",
        },
        {
            "source": "hltv_unofficial",
            "map_stats_id": "228493",
            "match_id": "2394126",
            "event_id": "8049",
            "event_name": "PGL Astana 2026",
            "map_name": "Ancient",
            "played_at": "2026-05-10",
            "round_number": 13,
            "t_team_id": "7020",
            "t_team_name": "Spirit",
            "ct_team_id": "6248",
            "ct_team_name": "The MongolZ",
            "winner_side": "ct",
            "winner_team_id": "6248",
            "winner_team_name": "The MongolZ",
            "team1_id": "6248",
            "team1_name": "The MongolZ",
            "team2_id": "7020",
            "team2_name": "Spirit",
            "score_team1_after": 5,
            "score_team2_after": 8,
            "reported_score": "5-8",
            "round_outcome": "bomb_defused",
            "is_overtime": False,
            "ingested_at": "2026-05-11",
        },
        {
            "source": "hltv_unofficial",
            "map_stats_id": "228493",
            "match_id": "2394126",
            "event_id": "8049",
            "event_name": "PGL Astana 2026",
            "map_name": "Ancient",
            "played_at": "2026-05-10",
            "round_number": 25,
            "t_team_id": "7020",
            "t_team_name": "Spirit",
            "ct_team_id": "6248",
            "ct_team_name": "The MongolZ",
            "winner_side": "t",
            "winner_team_id": "7020",
            "winner_team_name": "Spirit",
            "team1_id": "6248",
            "team1_name": "The MongolZ",
            "team2_id": "7020",
            "team2_name": "Spirit",
            "score_team1_after": 12,
            "score_team2_after": 13,
            "reported_score": "12-13",
            "round_outcome": "ct_win",
            "is_overtime": True,
            "ingested_at": "2026-05-11",
        },
    ]


def test_parse_hltv_map_stats_files_reads_cached_json_exports(tmp_path: Path) -> None:
    """The ingestion layer should consume cached JSON without live scraping."""
    input_path = tmp_path / "228493.json"
    input_path.write_text(HLTVMatchMapStats.model_validate(_sample_map_stats()).model_dump_json())

    records = parse_hltv_map_stats_files([input_path], ingested_at=date(2026, 5, 11))

    assert len(records) == 4
    assert records[0]["map_stats_id"] == "228493"
    assert records[-1]["round_number"] == 25


def test_parse_hltv_map_stats_files_skips_invalid_null_placeholder_exports(
    tmp_path: Path,
) -> None:
    """Null placeholder exports should not stop the rest of the cache batch."""
    valid_path = tmp_path / "228493.json"
    invalid_path = tmp_path / "228406.json"
    valid_path.write_text(HLTVMatchMapStats.model_validate(_sample_map_stats()).model_dump_json())
    invalid_path.write_text(
        """
        {
          "id": 228406,
          "matchId": null,
          "map": null,
          "date": null,
          "event": null,
          "team1": {"id": null, "name": null},
          "team2": {"id": null, "name": null},
          "startSides": {"team1": null, "team2": null},
          "overtimeStartSides": [],
          "result": {"team1TotalRounds": 0, "team2TotalRounds": 0, "halfResults": []},
          "roundHistory": []
        }
        """,
        encoding="utf-8",
    )

    records = parse_hltv_map_stats_files([invalid_path, valid_path], ingested_at=date(2026, 5, 11))

    assert len(records) == 4
    assert {record["map_stats_id"] for record in records} == {"228493"}


def test_write_round_history_parquet_uses_compact_typed_schema(tmp_path: Path) -> None:
    """Parsed round rows should persist as compact Parquet, not raw HTML or demos."""
    records = HLTVMatchMapStats.model_validate(_sample_map_stats()).to_round_records(
        ingested_at="2026-05-11"
    )
    output_path = tmp_path / "round_history.parquet"

    write_round_history_parquet(records, output_path)

    table = pq.read_table(output_path)
    assert table.num_rows == 4
    assert table.schema.field("map_stats_id").nullable is False
    assert table.schema.field("winner_side").nullable is False


def test_real_hltv_payload_shape_contains_enough_choke_profile_data() -> None:
    """Current cached HLTV JSON should parse with team IDs and round winners."""
    path = Path("data/hltv_cache/map_stats/228493.json")
    if not path.exists():
        return

    records = parse_hltv_map_stats_files([path], ingested_at=date(2026, 5, 11))

    assert len(records) == 35
    assert {records[0]["team1_id"], records[0]["team2_id"]} == {"6248", "7020"}
    assert records[11]["reported_score"] == "4-8"
    assert records[-1]["reported_score"] == "16-19"
    assert sum(1 for record in records if record["is_overtime"]) == 11
