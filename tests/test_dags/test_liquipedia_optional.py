"""Tests for optional Liquipedia DAG behavior.

Liquipedia enriches team, player, and tournament context, but the rest of the
project should still run when that API key is unavailable locally.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class MissingLiquipediaSettings:
    """Minimal settings object for exercising Liquipedia-only ingestion helpers."""

    liquipedia_api_key: str | None = None
    aws_s3_bucket: str = "test-bucket"
    aws_region: str = "us-east-1"


@pytest.mark.asyncio
async def test_weekly_team_rankings_skip_without_liquipedia_key() -> None:
    """Weekly team rankings should no-op when Liquipedia is not configured."""
    from cs2_weekly_rankings import _ingest_rankings

    count = await _ingest_rankings(MissingLiquipediaSettings())

    assert count == 0


@pytest.mark.asyncio
async def test_weekly_player_rankings_skip_without_liquipedia_key() -> None:
    """Weekly player rankings should no-op when Liquipedia is not configured."""
    from cs2_weekly_rankings import _ingest_player_rankings

    count = await _ingest_player_rankings(MissingLiquipediaSettings())

    assert count == 0


@pytest.mark.asyncio
async def test_tournament_sync_skips_without_liquipedia_key() -> None:
    """Tournament sync should no-op when Liquipedia is not configured."""
    from cs2_tournament_sync import _ingest_tournament_matches

    count = await _ingest_tournament_matches(MissingLiquipediaSettings())

    assert count == 0
