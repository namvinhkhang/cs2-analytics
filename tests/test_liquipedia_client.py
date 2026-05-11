"""Tests for LiquipediaClient ingestion client.

Tests cover:
- Class attributes: BASE_URL, _semaphore
- Auth header generation (Apikey format, not Bearer)
- get_teams(): deserializes {"result": [...]} envelope
- get_players(): deserializes {"result": [...]} envelope
- get_matches(): deserializes {"result": [...]} envelope
- get_tournaments(): deserializes {"result": [...]} envelope
- get_placements(): deserializes {"result": [...]} envelope
- asyncio.sleep(2.0) called after each API request (rate limit policy)
- ingest_all(): writes canonical Team, Player, Match records to S3
- ingest_all(): empty result returns zero counts without S3 write
- ingest_all() returns dict with 5 entity type counts

All HTTP calls are mocked via respx — no live network access.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from cs2_analytics.ingestion.liquipedia import LiquipediaClient
from cs2_analytics.models.liquipedia import (
    LiquipediaMatch,
    LiquipediaPlacement,
    LiquipediaPlayer,
    LiquipediaTeam,
    LiquipediaTournament,
)

# --- Fixture paths ---
FIXTURES = Path(__file__).parent / "fixtures" / "liquipedia"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


# --- Class attribute tests ---


def test_base_url() -> None:
    """LiquipediaClient.BASE_URL must point to API v3."""
    assert LiquipediaClient.BASE_URL == "https://api.liquipedia.net/api/v3"


def test_semaphore_is_asyncio_semaphore() -> None:
    """_semaphore must be a class-level asyncio.Semaphore."""
    assert isinstance(LiquipediaClient._semaphore, asyncio.Semaphore)


def test_auth_headers_apikey_format() -> None:
    """_auth_headers() must use 'Apikey' prefix (not 'Bearer')."""
    client = LiquipediaClient(api_key="test-key-123")
    headers = client._auth_headers()
    assert headers["Authorization"] == "Apikey test-key-123"
    assert headers.get("Accept") == "application/json"


# --- Method existence tests ---


def test_has_get_teams() -> None:
    assert hasattr(LiquipediaClient, "get_teams")


def test_has_get_players() -> None:
    assert hasattr(LiquipediaClient, "get_players")


def test_has_get_matches() -> None:
    assert hasattr(LiquipediaClient, "get_matches")


def test_has_get_tournaments() -> None:
    assert hasattr(LiquipediaClient, "get_tournaments")


def test_has_get_placements() -> None:
    assert hasattr(LiquipediaClient, "get_placements")


def test_has_ingest_all() -> None:
    assert hasattr(LiquipediaClient, "ingest_all")


def test_has_ingest_teams() -> None:
    assert hasattr(LiquipediaClient, "ingest_teams")


def test_has_ingest_players() -> None:
    assert hasattr(LiquipediaClient, "ingest_players")


def test_has_ingest_matches() -> None:
    assert hasattr(LiquipediaClient, "ingest_matches")


# --- Network-mocked functional tests ---


@pytest.mark.asyncio
@respx.mock
async def test_get_teams_returns_liquipedia_team_list() -> None:
    """get_teams() deserializes the {result: [...]} envelope into LiquipediaTeam list."""
    fixture = load_fixture("teams_response.json")
    respx.get("https://api.liquipedia.net/api/v3/team").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with LiquipediaClient(api_key="key") as client:
            teams = await client.get_teams(limit=50)

    assert len(teams) == 2
    assert all(isinstance(t, LiquipediaTeam) for t in teams)
    assert teams[0].pagename == "Natus_Vincere"
    assert teams[0].name == "Natus Vincere"


@pytest.mark.asyncio
@respx.mock
async def test_get_players_returns_liquipedia_player_list() -> None:
    """get_players() deserializes the {result: [...]} envelope into LiquipediaPlayer list."""
    fixture = load_fixture("players_response.json")
    respx.get("https://api.liquipedia.net/api/v3/player").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with LiquipediaClient(api_key="key") as client:
            players = await client.get_players(limit=50)

    assert len(players) == 2
    assert all(isinstance(p, LiquipediaPlayer) for p in players)
    assert players[0].id == "s1mple"


@pytest.mark.asyncio
@respx.mock
async def test_get_matches_returns_liquipedia_match_list() -> None:
    """get_matches() deserializes the {result: [...]} envelope into LiquipediaMatch list."""
    fixture = load_fixture("matches_response.json")
    respx.get("https://api.liquipedia.net/api/v3/match2").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with LiquipediaClient(api_key="key") as client:
            matches = await client.get_matches(limit=50)

    assert len(matches) == 1
    assert isinstance(matches[0], LiquipediaMatch)
    assert matches[0].match2id == "match-001"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments_returns_liquipedia_tournament_list() -> None:
    """get_tournaments() deserializes the {result: [...]} envelope
    into LiquipediaTournament list."""
    fixture = load_fixture("tournaments_response.json")
    respx.get("https://api.liquipedia.net/api/v3/tournament").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with LiquipediaClient(api_key="key") as client:
            tournaments = await client.get_tournaments(limit=50)

    assert len(tournaments) == 1
    assert isinstance(tournaments[0], LiquipediaTournament)
    assert tournaments[0].pagename == "IEM_Katowice_2024"


@pytest.mark.asyncio
@respx.mock
async def test_get_placements_returns_liquipedia_placement_list() -> None:
    """get_placements() deserializes the {result: [...]} envelope into LiquipediaPlacement list."""
    fixture = load_fixture("placements_response.json")
    respx.get("https://api.liquipedia.net/api/v3/placement").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with LiquipediaClient(api_key="key") as client:
            placements = await client.get_placements(limit=50)

    assert len(placements) == 2
    assert all(isinstance(p, LiquipediaPlacement) for p in placements)
    assert placements[0].place == "1"


@pytest.mark.asyncio
@respx.mock
async def test_get_teams_sleep_called_after_request() -> None:
    """asyncio.sleep(2.0) must be called after each get_teams() request (rate limit policy)."""
    fixture = load_fixture("teams_response.json")
    respx.get("https://api.liquipedia.net/api/v3/team").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        async with LiquipediaClient(api_key="key") as client:
            await client.get_teams(limit=50)

    mock_sleep.assert_called_once_with(2.0)


@pytest.mark.asyncio
@respx.mock
async def test_get_matches_uses_match2_endpoint() -> None:
    """get_matches() must call /match2 (not /match) per Liquipedia API v3 spec."""
    fixture = load_fixture("matches_response.json")
    # Only mock the correct /match2 endpoint
    respx.get("https://api.liquipedia.net/api/v3/match2").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with LiquipediaClient(api_key="key") as client:
            matches = await client.get_matches(limit=50)

    assert len(matches) == 1


@pytest.mark.asyncio
@respx.mock
async def test_ingest_all_returns_dict_of_counts() -> None:
    """ingest_all() returns a dict with keys for all 5 entity types."""
    respx.get("https://api.liquipedia.net/api/v3/team").mock(
        return_value=httpx.Response(200, json=load_fixture("teams_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/player").mock(
        return_value=httpx.Response(200, json=load_fixture("players_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/match2").mock(
        return_value=httpx.Response(200, json=load_fixture("matches_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/tournament").mock(
        return_value=httpx.Response(200, json=load_fixture("tournaments_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/placement").mock(
        return_value=httpx.Response(200, json=load_fixture("placements_response.json"))
    )

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "cs2_analytics.ingestion.liquipedia.write_parquet_to_s3",
            new_callable=MagicMock,
        ) as _,
    ):
        async with LiquipediaClient(api_key="key") as client:
            counts = await client.ingest_all(
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    assert "teams" in counts
    assert "players" in counts
    assert "matches" in counts
    assert "tournaments" in counts
    assert "placements" in counts
    assert counts["teams"] == 2
    assert counts["players"] == 2
    assert counts["matches"] == 1
    assert counts["tournaments"] == 1
    assert counts["placements"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_ingest_teams_writes_only_team_records() -> None:
    """ingest_teams() writes canonical teams and returns their count."""
    respx.get("https://api.liquipedia.net/api/v3/team").mock(
        return_value=httpx.Response(200, json=load_fixture("teams_response.json"))
    )

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "cs2_analytics.ingestion.liquipedia.write_parquet_to_s3",
            new_callable=MagicMock,
        ) as mock_s3,
    ):
        async with LiquipediaClient(api_key="key") as client:
            count = await client.ingest_teams(
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    assert count == 2
    assert mock_s3.call_count == 1
    assert "liquipedia" in mock_s3.call_args.kwargs["key"]
    assert "teams" in mock_s3.call_args.kwargs["key"]


@pytest.mark.asyncio
@respx.mock
async def test_ingest_players_writes_only_player_records() -> None:
    """ingest_players() writes canonical players and returns their count."""
    respx.get("https://api.liquipedia.net/api/v3/player").mock(
        return_value=httpx.Response(200, json=load_fixture("players_response.json"))
    )

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "cs2_analytics.ingestion.liquipedia.write_parquet_to_s3",
            new_callable=MagicMock,
        ) as mock_s3,
    ):
        async with LiquipediaClient(api_key="key") as client:
            count = await client.ingest_players(
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    assert count == 2
    assert mock_s3.call_count == 1
    assert "liquipedia" in mock_s3.call_args.kwargs["key"]
    assert "players" in mock_s3.call_args.kwargs["key"]


@pytest.mark.asyncio
@respx.mock
async def test_ingest_matches_writes_only_match_records() -> None:
    """ingest_matches() writes canonical matches and returns their count."""
    respx.get("https://api.liquipedia.net/api/v3/match2").mock(
        return_value=httpx.Response(200, json=load_fixture("matches_response.json"))
    )

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "cs2_analytics.ingestion.liquipedia.write_parquet_to_s3",
            new_callable=MagicMock,
        ) as mock_s3,
    ):
        async with LiquipediaClient(api_key="key") as client:
            count = await client.ingest_matches(
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    assert count == 1
    assert mock_s3.call_count == 1
    assert "liquipedia" in mock_s3.call_args.kwargs["key"]
    assert "matches" in mock_s3.call_args.kwargs["key"]


@pytest.mark.asyncio
@respx.mock
async def test_ingest_all_calls_write_parquet_for_teams_players_matches() -> None:
    """ingest_all() calls write_parquet_to_s3 for teams, players, and matches."""
    respx.get("https://api.liquipedia.net/api/v3/team").mock(
        return_value=httpx.Response(200, json=load_fixture("teams_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/player").mock(
        return_value=httpx.Response(200, json=load_fixture("players_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/match2").mock(
        return_value=httpx.Response(200, json=load_fixture("matches_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/tournament").mock(
        return_value=httpx.Response(200, json=load_fixture("tournaments_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/placement").mock(
        return_value=httpx.Response(200, json=load_fixture("placements_response.json"))
    )

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "cs2_analytics.ingestion.liquipedia.write_parquet_to_s3",
            new_callable=MagicMock,
        ) as mock_s3,
    ):
        async with LiquipediaClient(api_key="key") as client:
            await client.ingest_all(
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    # Should be called 3 times: teams, players, matches (tournaments/placements not yet canonical)
    assert mock_s3.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_ingest_all_empty_results_no_s3_write() -> None:
    """ingest_all() skips write_parquet_to_s3 when entity list is empty."""
    empty = {"result": []}
    respx.get("https://api.liquipedia.net/api/v3/team").mock(
        return_value=httpx.Response(200, json=empty)
    )
    respx.get("https://api.liquipedia.net/api/v3/player").mock(
        return_value=httpx.Response(200, json=empty)
    )
    respx.get("https://api.liquipedia.net/api/v3/match2").mock(
        return_value=httpx.Response(200, json=empty)
    )
    respx.get("https://api.liquipedia.net/api/v3/tournament").mock(
        return_value=httpx.Response(200, json=empty)
    )
    respx.get("https://api.liquipedia.net/api/v3/placement").mock(
        return_value=httpx.Response(200, json=empty)
    )

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "cs2_analytics.ingestion.liquipedia.write_parquet_to_s3",
            new_callable=MagicMock,
        ) as mock_s3,
    ):
        async with LiquipediaClient(api_key="key") as client:
            counts = await client.ingest_all(
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    mock_s3.assert_not_called()
    assert all(v == 0 for v in counts.values())


@pytest.mark.asyncio
@respx.mock
async def test_ingest_all_s3_key_includes_liquipedia_prefix() -> None:
    """ingest_all() builds S3 keys with 'liquipedia' as source prefix."""
    respx.get("https://api.liquipedia.net/api/v3/team").mock(
        return_value=httpx.Response(200, json=load_fixture("teams_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/player").mock(
        return_value=httpx.Response(200, json=load_fixture("players_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/match2").mock(
        return_value=httpx.Response(200, json=load_fixture("matches_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/tournament").mock(
        return_value=httpx.Response(200, json=load_fixture("tournaments_response.json"))
    )
    respx.get("https://api.liquipedia.net/api/v3/placement").mock(
        return_value=httpx.Response(200, json=load_fixture("placements_response.json"))
    )

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "cs2_analytics.ingestion.liquipedia.write_parquet_to_s3",
            new_callable=MagicMock,
        ) as mock_s3,
    ):
        async with LiquipediaClient(api_key="key") as client:
            await client.ingest_all(
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    # All S3 keys passed to write_parquet_to_s3 should contain 'liquipedia'
    for call in mock_s3.call_args_list:
        key = call.kwargs.get("key") or call.args[2]
        assert "liquipedia" in key, f"Expected 'liquipedia' in S3 key, got: {key}"
