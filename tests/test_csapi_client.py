"""Tests for CS API modern CS2 source parsing and ingestion helpers."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from cs2_analytics.ingestion.csapi import CSAPIClient
from cs2_analytics.models.csapi import CSAPIPlayerStat, CSAPITeamRanking


@pytest.mark.asyncio
@respx.mock
async def test_get_rankings_injects_snapshot_date() -> None:
    """CS API /rankings returns date once, so each ranking row should carry it."""
    respx.get("https://api.csapi.de/rankings/").mock(
        return_value=Response(
            200,
            json={
                "date": "2026-05-10",
                "rankings": [
                    {
                        "id": 9565,
                        "name": "Vitality",
                        "rank": 1,
                        "rank_diff": 0,
                        "points": 2086,
                        "points_diff": 5,
                    }
                ],
            },
        )
    )

    async with CSAPIClient() as client:
        rankings = await client.get_rankings()

    assert rankings == [
        CSAPITeamRanking(
            id=9565,
            name="Vitality",
            rank=1,
            rank_diff=0,
            points=2086,
            points_diff=5,
            ranking_date="2026-05-10",
        )
    ]


def test_team_ranking_maps_to_canonical_team() -> None:
    """VRS team ranking rows should be usable by dim_teams."""
    ranking = CSAPITeamRanking(
        id=9565,
        name="Vitality",
        rank=1,
        rank_diff=0,
        points=2086,
        points_diff=5,
        ranking_date="2026-05-10",
    )

    team = ranking.to_canonical_team()

    assert team.team_id == "9565"
    assert team.source == "csapi"
    assert team.name == "Vitality"
    assert team.region == "global"
    assert team.world_ranking == 1
    assert team.ingested_at == "2026-05-10"


def test_player_stat_maps_to_modern_player_record() -> None:
    """CS API raw player stats include team context needed for hidden-gem tiers."""
    stat = CSAPIPlayerStat(
        id=11893,
        name="zywoo",
        team_id=9565,
        team_name="Vitality",
        k=18.962,
        d=11.788,
        swing=4.616,
        adr=89.123,
        kast=79.34,
        rating=1.472,
        matches_played=52,
    )

    record = stat.to_player_stat_record(recorded_at="2026-05-10")

    assert record["player_id"] == "11893"
    assert record["team_id"] == "9565"
    assert record["team_name"] == "Vitality"
    assert record["match_id"] == "csapi:2026-05-10:11893"
    assert record["kills"] == pytest.approx(18.962)
    assert record["deaths"] == pytest.approx(11.788)
    assert record["kd_ratio"] == pytest.approx(18.962 / 11.788)
    assert record["rating"] == pytest.approx(1.472)
    assert record["matches_played"] == 52


@pytest.mark.asyncio
@respx.mock
async def test_ingest_player_stats_writes_csapi_prefix() -> None:
    """Modern player stats should use match IDs and match dates from /matches."""
    respx.get(
        "https://api.csapi.de/matches/",
        params={"limit": 1, "offset": 0},
    ).mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 2394120,
                    "team1": {"id": 11283, "name": "Falcons", "score": 2, "rank": 3},
                    "team2": {"id": 12895, "name": "K27", "score": 0, "rank": 37},
                    "maps": [],
                    "best_of": 3,
                    "date": "2026-05-09",
                    "event": "PGL Astana 2026",
                    "winner": {"id": 11283, "name": "Falcons"},
                }
            ],
        )
    )
    respx.get("https://api.csapi.de/matches/2394120/stats").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 0,
                    "name": "All",
                    "team1": {
                        "id": 11283,
                        "name": "Falcons",
                        "players": [
                            {
                                "id": 19230,
                                "name": "m0nesy",
                                "k": 36,
                                "d": 19,
                                "swing": 8.22,
                                "adr": 89.3,
                                "kast": 85.7,
                                "rating": 1.56,
                            }
                        ],
                    },
                    "team2": {
                        "id": 12895,
                        "name": "K27",
                        "players": [
                            {
                                "id": 24725,
                                "name": "qw1nk1",
                                "k": 37,
                                "d": 29,
                                "swing": 5.75,
                                "adr": 95.5,
                                "kast": 76.2,
                                "rating": 1.58,
                            }
                        ],
                    },
                }
            ],
        )
    )

    with patch("cs2_analytics.ingestion.csapi.write_parquet_to_s3") as mock_write:
        async with CSAPIClient() as client:
            count = await client.ingest_player_stats(
                bucket="bucket",
                ingest_date=date(2026, 5, 10),
                limit=1,
                pages=1,
                request_delay_seconds=0.0,
            )

    assert count == 2
    call = mock_write.call_args.kwargs
    assert call["bucket"] == "bucket"
    assert call["key"] == "raw/csapi/player_stats/year=2026/month=05/day=10/data.parquet"
    assert call["records"][0]["source"] == "csapi"
    assert call["records"][0]["player_id"] == "19230"
    assert call["records"][0]["team_id"] == "11283"
    assert call["records"][0]["team_name"] == "Falcons"
    assert call["records"][0]["match_id"] == "2394120"
    assert call["records"][0]["recorded_at"] == "2026-05-09"
    assert call["records"][0]["matches_played"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_ingest_player_stats_paginates_matches() -> None:
    """CS API match ingestion should paginate matches and stop on short pages."""
    first_page = respx.get(
        "https://api.csapi.de/matches/",
        params={"limit": 1, "offset": 0},
    ).mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 1,
                    "team1": {"id": 10, "name": "A"},
                    "team2": {"id": 20, "name": "B"},
                    "date": "2026-05-09",
                    "event": "Event",
                }
            ],
        )
    )
    second_page = respx.get(
        "https://api.csapi.de/matches/",
        params={"limit": 1, "offset": 1},
    ).mock(
        return_value=Response(200, json=[])
    )
    stats_route = respx.get("https://api.csapi.de/matches/1/stats").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 0,
                    "name": "All",
                    "team1": {
                        "id": 10,
                        "name": "A",
                        "players": [
                            {
                                "id": 1,
                                "name": "p1",
                                "k": 10,
                                "d": 5,
                                "swing": 1.0,
                                "adr": 90.0,
                                "kast": 80.0,
                                "rating": 1.4,
                            }
                        ],
                    },
                    "team2": {"id": 20, "name": "B", "players": []},
                }
            ],
        )
    )

    with patch("cs2_analytics.ingestion.csapi.write_parquet_to_s3") as mock_write:
        async with CSAPIClient() as client:
            count = await client.ingest_player_stats(
                bucket="bucket",
                ingest_date=date(2026, 5, 10),
                limit=1,
                pages=2,
                request_delay_seconds=0.0,
            )

    assert count == 1
    assert first_page.call_count == 1
    assert second_page.call_count == 1
    assert stats_route.call_count == 1
    records = mock_write.call_args.kwargs["records"]
    assert records[0]["match_id"] == "1"
    assert records[0]["recorded_at"] == "2026-05-09"


@pytest.mark.asyncio
@respx.mock
async def test_ingest_player_stats_can_limit_matches_and_use_chunk_filename() -> None:
    """Chunked bootstraps should process a bounded match slice and avoid overwriting files."""
    matches_route = respx.get(
        "https://api.csapi.de/matches/",
        params={"limit": 1, "offset": 100},
    ).mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 2,
                    "team1": {"id": 10, "name": "A"},
                    "team2": {"id": 20, "name": "B"},
                    "date": "2026-05-09",
                    "event": "Event",
                }
            ],
        )
    )
    stats_route = respx.get("https://api.csapi.de/matches/2/stats").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 0,
                    "name": "All",
                    "team1": {
                        "id": 10,
                        "name": "A",
                        "players": [
                            {
                                "id": 1,
                                "name": "p1",
                                "k": 10,
                                "d": 5,
                                "swing": 1.0,
                                "adr": 90.0,
                                "kast": 80.0,
                                "rating": 1.4,
                            }
                        ],
                    },
                    "team2": {"id": 20, "name": "B", "players": []},
                }
            ],
        )
    )

    with patch("cs2_analytics.ingestion.csapi.write_parquet_to_s3") as mock_write:
        async with CSAPIClient() as client:
            count = await client.ingest_player_stats(
                bucket="bucket",
                ingest_date=date(2026, 5, 10),
                limit=100,
                offset=100,
                pages=30,
                max_matches=1,
                request_delay_seconds=0.0,
                output_filename="matches_offset_100.parquet",
            )

    assert count == 1
    assert matches_route.call_count == 1
    assert stats_route.call_count == 1
    assert (
        mock_write.call_args.kwargs["key"]
        == "raw/csapi/player_stats/year=2026/month=05/day=10/matches_offset_100.parquet"
    )
