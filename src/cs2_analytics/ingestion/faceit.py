"""FACEIT Data API v4 ingestion client for CS2 per-match statistics.

Fetches match metadata and per-player stats (kills/deaths/ADR/KAST/ELO)
from the FACEIT Data API v4. Results are serialized as canonical Match and
Player records and written to S3 in snappy-compressed Parquet format.

Rate limit: ~1 req/s on a free FACEIT API key. asyncio.sleep(1.0) is called
after each API request to stay within this limit. Never remove these sleeps
without checking the current FACEIT API quota for your key tier.
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import structlog

from cs2_analytics.ingestion.base import BaseAPIClient
from cs2_analytics.models.canonical import Match, Player
from cs2_analytics.models.faceit import FACEITMatch, FACEITPlayer
from cs2_analytics.utils.parquet import MATCH_SCHEMA, PLAYER_SCHEMA, models_to_records
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

# Module-level structured logger — emits JSON-compatible log events
logger = structlog.get_logger()


class FACEITClient(BaseAPIClient):
    """FACEIT Data API v4 client for CS2 per-match statistics.

    Rate limit: ~1 req/s on free API key.
    Auth: Bearer token in Authorization header.

    Class-level semaphore (Semaphore(1)) ensures only 1 concurrent request
    across all FACEITClient instances — important for shared event loops.
    """

    BASE_URL: str = "https://open.faceit.com/data/v4"
    # 1 concurrent request enforces FACEIT's ~1 req/s free-tier rate limit
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(1)

    def _auth_headers(self) -> dict[str, str]:
        """Return FACEIT Bearer token auth header."""
        return {"Authorization": f"Bearer {self._api_key}"}

    async def get_match(self, match_id: str) -> FACEITMatch:
        """Fetch match metadata by ID.

        Endpoint: GET /matches/{match_id}
        Returns a validated FACEITMatch with team and result data.
        """
        data: dict[str, Any] = await self.get(f"/matches/{match_id}")
        return FACEITMatch.model_validate(data)

    async def get_match_stats(self, match_id: str) -> list[FACEITPlayer]:
        """Fetch per-player stats for a completed match.

        Endpoint: GET /matches/{match_id}/stats
        Response structure: {"rounds": [{"teams": [{"players": [...]}]}]}
        Player stats are nested under player_stats dict — merged into top-level
        before model validation so kills/deaths/adr/kd_ratio/kast are accessible.
        """
        data: dict[str, Any] = await self.get(f"/matches/{match_id}/stats")
        players: list[FACEITPlayer] = []
        for round_data in data.get("rounds", []):
            for team_data in round_data.get("teams", []):
                for player_data in team_data.get("players", []):
                    # Flatten player_stats into top-level so FACEITPlayer can validate stat fields
                    stats = player_data.get("player_stats", {})
                    merged = {**player_data, **stats}
                    players.append(FACEITPlayer.model_validate(merged))
        return players

    async def ingest_matches(
        self,
        match_ids: list[str],
        bucket: str,
        ingest_date: date,
        *,
        region: str = "us-east-1",
    ) -> tuple[int, int]:
        """Fetch match metadata and player stats, then write both to S3.

        Processes each match ID sequentially with 1.0s sleep between requests
        to stay within FACEIT's rate limit. Failed matches are logged and skipped
        so one bad match does not abort the entire batch (resilient ingestion).

        Returns (match_count, player_count) written to S3.
        """
        canonical_matches: list[Match] = []
        canonical_players: list[Player] = []
        recorded_at = ingest_date.isoformat()

        for match_id in match_ids:
            try:
                # Fetch match metadata and sleep to respect rate limit
                match = await self.get_match(match_id)
                canonical_matches.append(match.to_canonical())
                await asyncio.sleep(1.0)  # FACEIT rate limit: ~1 req/s

                # Fetch per-player stats and sleep before next match
                stats = await self.get_match_stats(match_id)
                for player in stats:
                    # Stats are passed as None here — they are already embedded in
                    # the FACEITPlayer model via the merged dict in get_match_stats()
                    canonical_players.append(
                        player.to_canonical(
                            match_id=match_id,
                            kills=None,
                            deaths=None,
                            adr=None,
                            kd_ratio=None,
                            kast=None,
                            recorded_at=recorded_at,
                        )
                    )
                await asyncio.sleep(1.0)  # rate limit: sleep between matches

            except Exception:
                # Log and continue — a failed match should not abort the full batch
                logger.warning("match_ingest_failed", match_id=match_id)
                continue

        y, m, d = ingest_date.year, ingest_date.month, ingest_date.day

        if canonical_matches:
            write_parquet_to_s3(
                records=models_to_records(canonical_matches),
                schema=MATCH_SCHEMA,
                bucket=bucket,
                key=build_s3_key("faceit", "matches", y, m, d),
                region=region,
            )

        if canonical_players:
            write_parquet_to_s3(
                records=models_to_records(canonical_players),
                schema=PLAYER_SCHEMA,
                bucket=bucket,
                key=build_s3_key("faceit", "players", y, m, d),
                region=region,
            )

        logger.info(
            "faceit_ingest_complete",
            date=recorded_at,
            match_count=len(canonical_matches),
            player_count=len(canonical_players),
        )
        return len(canonical_matches), len(canonical_players)
