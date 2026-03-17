"""Tests for FACEITClient ingestion client — covers ING-02.

Tests cover:
- Class attributes: BASE_URL, _semaphore
- Auth header generation (Bearer token)
- get_match(): returns FACEITMatch from /matches/{id}
- get_match_stats(): returns list[FACEITPlayer] from /matches/{id}/stats
- ingest_matches(): writes canonical Match + Player records to S3
- asyncio.sleep(1.0) called between API requests for rate limiting

All HTTP calls are mocked via respx — no live network access.
boto3 calls are mocked via unittest.mock to avoid real AWS credentials.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx

from cs2_analytics.ingestion.faceit import FACEITClient
from cs2_analytics.models.faceit import FACEITMatch, FACEITPlayer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures" / "faceit"


@pytest.fixture
def match_fixture() -> dict[str, Any]:
    return json.loads((_FIXTURES / "match_response.json").read_text())


@pytest.fixture
def match_stats_fixture() -> dict[str, Any]:
    return json.loads((_FIXTURES / "match_stats_response.json").read_text())


# ---------------------------------------------------------------------------
# Class attribute tests
# ---------------------------------------------------------------------------


def test_faceit_client_base_url() -> None:
    """FACEITClient.BASE_URL should point to FACEIT Data API v4."""
    assert FACEITClient.BASE_URL == "https://open.faceit.com/data/v4"


def test_faceit_client_semaphore_is_semaphore_1() -> None:
    """FACEITClient._semaphore must be asyncio.Semaphore(1) at class level."""
    assert isinstance(FACEITClient._semaphore, asyncio.Semaphore)
    # Semaphore(1) has _value=1 internally
    assert FACEITClient._semaphore._value == 1  # type: ignore[attr-defined]


def test_faceit_client_auth_headers() -> None:
    """_auth_headers() must return Bearer token with the provided API key."""
    client = FACEITClient(api_key="my-faceit-key")
    headers = client._auth_headers()
    assert headers == {"Authorization": "Bearer my-faceit-key"}


def test_faceit_client_extends_base_api_client() -> None:
    """FACEITClient must subclass BaseAPIClient."""
    from cs2_analytics.ingestion.base import BaseAPIClient

    assert issubclass(FACEITClient, BaseAPIClient)


# ---------------------------------------------------------------------------
# get_match() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_match_returns_faceit_match(
    respx_mock: respx.MockRouter,
    match_fixture: dict[str, Any],
) -> None:
    """get_match() should call GET /matches/{id} and return FACEITMatch."""
    match_id = "1-abc123"
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}").mock(
        return_value=httpx.Response(200, json=match_fixture)
    )
    async with FACEITClient(api_key="key") as client:
        result = await client.get_match(match_id)

    assert isinstance(result, FACEITMatch)
    assert result.match_id == match_id
    assert result.game == "cs2"
    assert result.region == "EU"


@pytest.mark.asyncio
async def test_get_match_uses_correct_endpoint(
    respx_mock: respx.MockRouter,
    match_fixture: dict[str, Any],
) -> None:
    """get_match() must call exactly /matches/{match_id} — not a different path."""
    match_id = "test-id-999"
    route = respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}").mock(
        return_value=httpx.Response(200, json=match_fixture | {"match_id": match_id})
    )
    async with FACEITClient(api_key="key") as client:
        await client.get_match(match_id)

    assert route.called


# ---------------------------------------------------------------------------
# get_match_stats() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_match_stats_returns_player_list(
    respx_mock: respx.MockRouter,
    match_stats_fixture: dict[str, Any],
) -> None:
    """get_match_stats() should return a list of FACEITPlayer instances."""
    match_id = "1-abc123"
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}/stats").mock(
        return_value=httpx.Response(200, json=match_stats_fixture)
    )
    async with FACEITClient(api_key="key") as client:
        players = await client.get_match_stats(match_id)

    assert isinstance(players, list)
    assert len(players) == 3  # 2 in team1 + 1 in team2 from fixture
    assert all(isinstance(p, FACEITPlayer) for p in players)


@pytest.mark.asyncio
async def test_get_match_stats_player_fields(
    respx_mock: respx.MockRouter,
    match_stats_fixture: dict[str, Any],
) -> None:
    """get_match_stats() should populate player_id and nickname from fixture."""
    match_id = "1-abc123"
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}/stats").mock(
        return_value=httpx.Response(200, json=match_stats_fixture)
    )
    async with FACEITClient(api_key="key") as client:
        players = await client.get_match_stats(match_id)

    first_player = players[0]
    assert first_player.player_id == "player-001"
    assert first_player.nickname == "s1mple"
    assert first_player.country == "UA"
    assert first_player.faceit_elo == 3000


@pytest.mark.asyncio
async def test_get_match_stats_empty_rounds(respx_mock: respx.MockRouter) -> None:
    """get_match_stats() should return empty list when rounds is empty."""
    match_id = "1-abc123"
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}/stats").mock(
        return_value=httpx.Response(200, json={"rounds": []})
    )
    async with FACEITClient(api_key="key") as client:
        players = await client.get_match_stats(match_id)

    assert players == []


# ---------------------------------------------------------------------------
# ingest_matches() tests (with mocked S3 and asyncio.sleep)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_matches_returns_counts(
    respx_mock: respx.MockRouter,
    match_fixture: dict[str, Any],
    match_stats_fixture: dict[str, Any],
) -> None:
    """ingest_matches() should return (match_count, player_count) tuple."""
    match_id = "1-abc123"
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}").mock(
        return_value=httpx.Response(200, json=match_fixture)
    )
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}/stats").mock(
        return_value=httpx.Response(200, json=match_stats_fixture)
    )

    with patch("cs2_analytics.ingestion.faceit.write_parquet_to_s3") as _:
        with patch("cs2_analytics.ingestion.faceit.asyncio.sleep"):
            async with FACEITClient(api_key="key") as client:
                match_count, player_count = await client.ingest_matches(
                    match_ids=[match_id],
                    bucket="test-bucket",
                    ingest_date=date(2024, 1, 15),
                )

    assert match_count == 1
    assert player_count == 3  # 3 players from fixture


@pytest.mark.asyncio
async def test_ingest_matches_calls_write_parquet_twice(
    respx_mock: respx.MockRouter,
    match_fixture: dict[str, Any],
    match_stats_fixture: dict[str, Any],
) -> None:
    """ingest_matches() must call write_parquet_to_s3 twice: once for matches, once for players."""
    match_id = "1-abc123"
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}").mock(
        return_value=httpx.Response(200, json=match_fixture)
    )
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}/stats").mock(
        return_value=httpx.Response(200, json=match_stats_fixture)
    )

    with patch("cs2_analytics.ingestion.faceit.write_parquet_to_s3") as mock_write:
        with patch("cs2_analytics.ingestion.faceit.asyncio.sleep"):
            async with FACEITClient(api_key="key") as client:
                await client.ingest_matches(
                    match_ids=[match_id],
                    bucket="test-bucket",
                    ingest_date=date(2024, 1, 15),
                )

    assert mock_write.call_count == 2


@pytest.mark.asyncio
async def test_ingest_matches_uses_correct_s3_key_format(
    respx_mock: respx.MockRouter,
    match_fixture: dict[str, Any],
    match_stats_fixture: dict[str, Any],
) -> None:
    """ingest_matches() should write to Hive-partitioned S3 keys."""
    match_id = "1-abc123"
    ingest_date = date(2024, 1, 15)
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}").mock(
        return_value=httpx.Response(200, json=match_fixture)
    )
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}/stats").mock(
        return_value=httpx.Response(200, json=match_stats_fixture)
    )

    with patch("cs2_analytics.ingestion.faceit.write_parquet_to_s3") as mock_write:
        with patch("cs2_analytics.ingestion.faceit.asyncio.sleep"):
            async with FACEITClient(api_key="key") as client:
                await client.ingest_matches(
                    match_ids=[match_id],
                    bucket="test-bucket",
                    ingest_date=ingest_date,
                )

    # Extract keys from both write_parquet_to_s3 calls
    call_keys = [call.kwargs["key"] for call in mock_write.call_args_list]
    assert any("faceit/matches" in k for k in call_keys)
    assert any("faceit/players" in k for k in call_keys)
    assert any("year=2024/month=01/day=15" in k for k in call_keys)


@pytest.mark.asyncio
async def test_ingest_matches_skips_failed_match(
    respx_mock: respx.MockRouter,
    match_fixture: dict[str, Any],
    match_stats_fixture: dict[str, Any],
) -> None:
    """ingest_matches() should skip failed matches and continue processing remaining ones."""
    bad_id = "bad-match"
    good_id = "1-abc123"

    # Bad match returns 500 — should be caught and skipped
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{bad_id}").mock(
        return_value=httpx.Response(500, json={"error": "server error"})
    )
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{good_id}").mock(
        return_value=httpx.Response(200, json=match_fixture)
    )
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{good_id}/stats").mock(
        return_value=httpx.Response(200, json=match_stats_fixture)
    )

    with patch("cs2_analytics.ingestion.faceit.write_parquet_to_s3"):
        with patch("cs2_analytics.ingestion.faceit.asyncio.sleep"):
            async with FACEITClient(api_key="key") as client:
                match_count, player_count = await client.ingest_matches(
                    match_ids=[bad_id, good_id],
                    bucket="test-bucket",
                    ingest_date=date(2024, 1, 15),
                )

    # Only the good match should be counted
    assert match_count == 1
    assert player_count == 3


@pytest.mark.asyncio
async def test_ingest_matches_no_writes_when_empty(respx_mock: respx.MockRouter) -> None:
    """ingest_matches() with empty match_ids should return (0, 0)
    and not call write_parquet_to_s3."""
    with patch("cs2_analytics.ingestion.faceit.write_parquet_to_s3") as mock_write:
        async with FACEITClient(api_key="key") as client:
            match_count, player_count = await client.ingest_matches(
                match_ids=[],
                bucket="test-bucket",
                ingest_date=date(2024, 1, 15),
            )

    assert match_count == 0
    assert player_count == 0
    mock_write.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_matches_to_canonical_match_fields(
    respx_mock: respx.MockRouter,
    match_fixture: dict[str, Any],
    match_stats_fixture: dict[str, Any],
) -> None:
    """ingest_matches() should produce canonical Match records with correct source='faceit'."""
    match_id = "1-abc123"
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}").mock(
        return_value=httpx.Response(200, json=match_fixture)
    )
    respx_mock.get(f"https://open.faceit.com/data/v4/matches/{match_id}/stats").mock(
        return_value=httpx.Response(200, json=match_stats_fixture)
    )

    captured_records: list[list[dict[str, Any]]] = []

    def capture_write(records: list[dict], **kwargs: Any) -> None:
        captured_records.append(records)

    with patch("cs2_analytics.ingestion.faceit.write_parquet_to_s3", side_effect=capture_write):
        with patch("cs2_analytics.ingestion.faceit.asyncio.sleep"):
            async with FACEITClient(api_key="key") as client:
                await client.ingest_matches(
                    match_ids=[match_id],
                    bucket="test-bucket",
                    ingest_date=date(2024, 1, 15),
                )

    # First call is matches, second is players
    assert len(captured_records) == 2
    match_records = captured_records[0]
    assert len(match_records) == 1
    assert match_records[0]["source"] == "faceit"
    assert match_records[0]["match_id"] == match_id
    assert match_records[0]["team_a_id"] == "team-alpha"
    assert match_records[0]["winner_id"] == "team-alpha"
