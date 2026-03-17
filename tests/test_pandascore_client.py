"""Tests for PandaScoreClient ingestion client.

Tests cover:
- Class attributes: BASE_URL, _semaphore
- Auth header generation
- get_recent_matches(): deserializes bare JSON array response
- get_players(): deserializes bare JSON array response
- asyncio.sleep(3.6) called after each API request
- ingest_matches(): writes canonical Match records to S3
- ingest_players(): writes canonical Player records to S3 (stats None on free tier)

All HTTP calls are mocked via respx — no live network access.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from cs2_analytics.ingestion.pandascore import PandaScoreClient
from cs2_analytics.models.pandascore import PandaScoreMatch, PandaScorePlayer

# --- Fixture paths ---
FIXTURES = Path(__file__).parent / "fixtures" / "pandascore"


@pytest.fixture
def matches_fixture() -> list[dict[str, Any]]:
    """Realistic PandaScore /csgo/matches/past response (bare JSON array)."""
    return json.loads((FIXTURES / "matches_response.json").read_text())


@pytest.fixture
def players_fixture() -> list[dict[str, Any]]:
    """Realistic PandaScore /csgo/players response (bare JSON array)."""
    return json.loads((FIXTURES / "players_response.json").read_text())


# --- Class attribute tests ---


class TestPandaScoreClientAttributes:
    def test_base_url(self) -> None:
        """PandaScoreClient.BASE_URL must point to PandaScore API."""
        assert PandaScoreClient.BASE_URL == "https://api.pandascore.co"

    def test_semaphore_is_asyncio_semaphore(self) -> None:
        """_semaphore must be an asyncio.Semaphore (class-level)."""
        assert isinstance(PandaScoreClient._semaphore, asyncio.Semaphore)

    def test_auth_headers(self) -> None:
        """_auth_headers() must return Bearer token header."""
        client = PandaScoreClient(api_key="test-token-123")
        headers = client._auth_headers()
        assert headers == {"Authorization": "Bearer test-token-123"}

    def test_instantiation(self) -> None:
        """PandaScoreClient instantiates with api_key parameter."""
        client = PandaScoreClient(api_key="key")
        assert client._api_key == "key"


# --- get_recent_matches tests ---


class TestGetRecentMatches:
    @pytest.mark.asyncio
    async def test_returns_list_of_pandascore_matches(
        self, matches_fixture: list[dict[str, Any]]
    ) -> None:
        """get_recent_matches() returns a list of PandaScoreMatch objects."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=matches_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                async with PandaScoreClient(api_key="test") as client:
                    result = await client.get_recent_matches()

        assert len(result) == 2
        assert all(isinstance(m, PandaScoreMatch) for m in result)
        assert result[0].id == 101
        assert result[1].id == 102

    @pytest.mark.asyncio
    async def test_passes_page_and_per_page_params(
        self, matches_fixture: list[dict[str, Any]]
    ) -> None:
        """get_recent_matches() passes page and per_page as query params."""
        with respx.mock:
            route = respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=matches_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                async with PandaScoreClient(api_key="test") as client:
                    await client.get_recent_matches(page=2, per_page=25)

        # Verify query params were sent
        request = route.calls.last.request
        assert "page=2" in str(request.url)
        assert "per_page=25" in str(request.url)

    @pytest.mark.asyncio
    async def test_sleeps_after_request(self, matches_fixture: list[dict[str, Any]]) -> None:
        """get_recent_matches() calls asyncio.sleep(3.6) after API call."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=matches_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                async with PandaScoreClient(api_key="test") as client:
                    await client.get_recent_matches()

        mock_sleep.assert_called_once_with(3.6)

    @pytest.mark.asyncio
    async def test_handles_empty_list_response(self) -> None:
        """get_recent_matches() handles empty list API response."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=[])
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                async with PandaScoreClient(api_key="test") as client:
                    result = await client.get_recent_matches()

        assert result == []


# --- get_players tests ---


class TestGetPlayers:
    @pytest.mark.asyncio
    async def test_returns_list_of_pandascore_players(
        self, players_fixture: list[dict[str, Any]]
    ) -> None:
        """get_players() returns a list of PandaScorePlayer objects."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/players").mock(
                return_value=httpx.Response(200, json=players_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                async with PandaScoreClient(api_key="test") as client:
                    result = await client.get_players()

        assert len(result) == 2
        assert all(isinstance(p, PandaScorePlayer) for p in result)
        assert result[0].id == 201
        assert result[0].name == "s1mple"
        assert result[0].nationality == "UA"

    @pytest.mark.asyncio
    async def test_sleeps_after_request(self, players_fixture: list[dict[str, Any]]) -> None:
        """get_players() calls asyncio.sleep(3.6) after API call."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/players").mock(
                return_value=httpx.Response(200, json=players_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                async with PandaScoreClient(api_key="test") as client:
                    await client.get_players()

        mock_sleep.assert_called_once_with(3.6)

    @pytest.mark.asyncio
    async def test_handles_player_with_no_team(self, players_fixture: list[dict[str, Any]]) -> None:
        """get_players() handles player without current_team (None)."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/players").mock(
                return_value=httpx.Response(200, json=players_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                async with PandaScoreClient(api_key="test") as client:
                    result = await client.get_players()

        # ZywOo has no team
        assert result[1].current_team is None


# --- ingest_matches tests ---


class TestIngestMatches:
    @pytest.mark.asyncio
    async def test_returns_match_count(self, matches_fixture: list[dict[str, Any]]) -> None:
        """ingest_matches() returns count of matches written."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=matches_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("cs2_analytics.ingestion.pandascore.write_parquet_to_s3") as mock_write:
                    async with PandaScoreClient(api_key="test") as client:
                        count = await client.ingest_matches(
                            bucket="test-bucket",
                            ingest_date=date(2024, 1, 15),
                        )

        assert count == 2
        mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_writes_to_correct_s3_key(self, matches_fixture: list[dict[str, Any]]) -> None:
        """ingest_matches() writes to correct Hive-partitioned S3 key."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=matches_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("cs2_analytics.ingestion.pandascore.write_parquet_to_s3") as mock_write:
                    async with PandaScoreClient(api_key="test") as client:
                        await client.ingest_matches(
                            bucket="test-bucket",
                            ingest_date=date(2024, 1, 15),
                        )

        call_kwargs = mock_write.call_args
        assert call_kwargs.kwargs["bucket"] == "test-bucket"
        assert "pandascore/matches" in call_kwargs.kwargs["key"]
        assert "year=2024" in call_kwargs.kwargs["key"]
        assert "month=01" in call_kwargs.kwargs["key"]
        assert "day=15" in call_kwargs.kwargs["key"]

    @pytest.mark.asyncio
    async def test_skips_s3_write_on_empty_results(self) -> None:
        """ingest_matches() does not call write_parquet_to_s3 if no matches."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=[])
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("cs2_analytics.ingestion.pandascore.write_parquet_to_s3") as mock_write:
                    async with PandaScoreClient(api_key="test") as client:
                        count = await client.ingest_matches(
                            bucket="test-bucket",
                            ingest_date=date(2024, 1, 15),
                        )

        assert count == 0
        mock_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_multiple_pages(self, matches_fixture: list[dict[str, Any]]) -> None:
        """ingest_matches() fetches each page sequentially (no asyncio.gather)."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/matches/past").mock(
                return_value=httpx.Response(200, json=matches_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with patch("cs2_analytics.ingestion.pandascore.write_parquet_to_s3"):
                    async with PandaScoreClient(api_key="test") as client:
                        count = await client.ingest_matches(
                            bucket="test-bucket",
                            ingest_date=date(2024, 1, 15),
                            pages=2,
                        )

        # 2 pages = 2 API calls = 2 sleeps
        assert mock_sleep.call_count == 2
        assert count == 4  # 2 matches per page * 2 pages


# --- ingest_players tests ---


class TestIngestPlayers:
    @pytest.mark.asyncio
    async def test_returns_player_count(self, players_fixture: list[dict[str, Any]]) -> None:
        """ingest_players() returns count of players written."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/players").mock(
                return_value=httpx.Response(200, json=players_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("cs2_analytics.ingestion.pandascore.write_parquet_to_s3") as mock_write:
                    async with PandaScoreClient(api_key="test") as client:
                        count = await client.ingest_players(
                            bucket="test-bucket",
                            ingest_date=date(2024, 1, 15),
                        )

        assert count == 2
        mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_stats_none_on_free_tier(self, players_fixture: list[dict[str, Any]]) -> None:
        """ingest_players() passes all stat fields as None (free tier limitation)."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/players").mock(
                return_value=httpx.Response(200, json=players_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("cs2_analytics.ingestion.pandascore.write_parquet_to_s3") as mock_write:
                    async with PandaScoreClient(api_key="test") as client:
                        await client.ingest_players(
                            bucket="test-bucket",
                            ingest_date=date(2024, 1, 15),
                        )

        # Verify the records written have None stats
        call_kwargs = mock_write.call_args
        records: list[dict] = call_kwargs.kwargs["records"]
        for record in records:
            assert record["kills"] is None
            assert record["deaths"] is None
            assert record["adr"] is None
            assert record["kd_ratio"] is None

    @pytest.mark.asyncio
    async def test_writes_to_correct_s3_key(self, players_fixture: list[dict[str, Any]]) -> None:
        """ingest_players() writes to correct Hive-partitioned S3 key."""
        with respx.mock:
            respx.get("https://api.pandascore.co/csgo/players").mock(
                return_value=httpx.Response(200, json=players_fixture)
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("cs2_analytics.ingestion.pandascore.write_parquet_to_s3") as mock_write:
                    async with PandaScoreClient(api_key="test") as client:
                        await client.ingest_players(
                            bucket="test-bucket",
                            ingest_date=date(2024, 1, 15),
                        )

        call_kwargs = mock_write.call_args
        assert "pandascore/players" in call_kwargs.kwargs["key"]
