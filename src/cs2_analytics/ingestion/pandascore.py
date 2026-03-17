"""PandaScore REST API ingestion client for CS2 (counterstrike) match results and player stats.

Fetches pro-league match results and player profiles from the PandaScore API.
Results are serialized as canonical Match and Player records and written to S3
in snappy-compressed Parquet format.

Rate limit: 1,000 req/hour on free tier = ~0.27 req/s.
A mandatory asyncio.sleep(3.6) after EVERY API call enforces this limit.
NEVER remove these sleeps or use asyncio.gather() — it exhausts the hourly
budget in seconds (see RESEARCH.md Pitfall 1).

CS2 game slug: /csgo/ (PandaScore uses the legacy CS:GO slug for match endpoints).
Auth: Bearer token in Authorization header.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import structlog

from cs2_analytics.ingestion.base import BaseAPIClient
from cs2_analytics.models.canonical import Match, Player
from cs2_analytics.models.pandascore import PandaScoreMatch, PandaScorePlayer
from cs2_analytics.utils.parquet import MATCH_SCHEMA, PLAYER_SCHEMA, models_to_records
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

# Module-level structured logger — emits JSON-compatible log events
logger = structlog.get_logger()


class PandaScoreClient(BaseAPIClient):
    """PandaScore REST API client for CS2 (counterstrike) match results and player stats.

    Free tier rate limit: 1,000 req/hour = ~0.27 req/s.
    A 3.6-second sleep after EVERY request is mandatory to prevent 429 exhaustion.
    (Pitfall 1 from RESEARCH.md: asyncio.gather() without rate limiting fires all
    coroutines at once and exhausts the hourly budget in seconds.)

    Auth: Bearer token in Authorization header.
    CS2 game prefix: /csgo/ (PandaScore uses the legacy game slug — do NOT use /cs2/).
    """

    BASE_URL: str = "https://api.pandascore.co"
    # 1 concurrent request — combined with sleep(3.6) enforces 1,000 req/hour limit
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(1)

    def _auth_headers(self) -> dict[str, str]:
        """Return PandaScore Bearer token auth header."""
        return {"Authorization": f"Bearer {self._api_key}"}

    async def get_recent_matches(self, page: int = 1, per_page: int = 50) -> list[PandaScoreMatch]:
        """Fetch recent CS2 past match results.

        Endpoint: GET /csgo/matches/past
        PandaScore list endpoints return a bare JSON array (not wrapped in a dict).
        The isinstance(data, list) check handles this — base get() type-annotates
        dict[str, Any] but the actual runtime value may be a list for list endpoints.

        Sleeps 3.6s after request — MANDATORY for free tier rate limit compliance.
        """
        data = await self.get(
            "/csgo/matches/past",
            page=page,
            per_page=per_page,
        )
        await asyncio.sleep(3.6)  # MANDATORY: 1,000 req/hour free tier limit

        # PandaScore list endpoints return a bare JSON array, not {"results": [...]}
        if isinstance(data, list):
            records: list[dict[str, Any]] = data
        else:
            records = data.get("results", [])
        return [PandaScoreMatch.model_validate(r) for r in records]

    async def get_players(self, page: int = 1, per_page: int = 50) -> list[PandaScorePlayer]:
        """Fetch CS2 player profiles.

        Endpoint: GET /csgo/players
        Sleeps 3.6s after request — MANDATORY for free tier rate limit compliance.
        Advanced stats (adr, kast) are not available from the profile endpoint;
        they require match-specific endpoints and may be premium-only (Pitfall 3).
        """
        data = await self.get(
            "/csgo/players",
            page=page,
            per_page=per_page,
        )
        await asyncio.sleep(3.6)  # MANDATORY: 1,000 req/hour free tier limit

        if isinstance(data, list):
            records = data
        else:
            records = data.get("results", [])
        return [PandaScorePlayer.model_validate(r) for r in records]

    async def ingest_matches(
        self,
        bucket: str,
        ingest_date: date,
        *,
        pages: int = 1,
        per_page: int = 50,
        region: str = "us-east-1",
    ) -> int:
        """Fetch match pages and write canonical Match records to S3.

        Fetches pages sequentially (NOT with asyncio.gather) to avoid burst
        exhaustion on the 1,000 req/hour free tier. Each page fetch includes
        a 3.6s sleep via get_recent_matches().

        Returns count of matches written to S3.
        """
        canonical_matches: list[Match] = []
        for page in range(1, pages + 1):
            raw_matches = await self.get_recent_matches(page=page, per_page=per_page)
            canonical_matches.extend([m.to_canonical() for m in raw_matches])

        y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
        if canonical_matches:
            write_parquet_to_s3(
                records=models_to_records(canonical_matches),
                schema=MATCH_SCHEMA,
                bucket=bucket,
                key=build_s3_key("pandascore", "matches", y, m, d),
                region=region,
            )

        logger.info("pandascore_matches_ingested", count=len(canonical_matches))
        return len(canonical_matches)

    async def ingest_players(
        self,
        bucket: str,
        ingest_date: date,
        *,
        pages: int = 1,
        per_page: int = 50,
        region: str = "us-east-1",
    ) -> int:
        """Fetch player pages and write canonical Player records to S3.

        Advanced stats (kills, deaths, adr, kast, kd_ratio) are passed as None
        because /csgo/players returns profile data only — per-match stats require
        match-specific endpoints and may be premium-only on the free tier.

        Returns count of players written to S3.
        """
        canonical_players: list[Player] = []
        recorded_at = ingest_date.isoformat()

        for page in range(1, pages + 1):
            raw_players = await self.get_players(page=page, per_page=per_page)
            for p in raw_players:
                canonical_players.append(
                    p.to_canonical(
                        kills=None,  # per-match stats not in /csgo/players endpoint
                        deaths=None,  # require match-specific endpoints
                        adr=None,  # may be premium-only — treat as None (Pitfall 3)
                        kd_ratio=None,
                        match_id=None,
                        recorded_at=recorded_at,
                    )
                )

        y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
        if canonical_players:
            write_parquet_to_s3(
                records=models_to_records(canonical_players),
                schema=PLAYER_SCHEMA,
                bucket=bucket,
                key=build_s3_key("pandascore", "players", y, m, d),
                region=region,
            )

        logger.info("pandascore_players_ingested", count=len(canonical_players))
        return len(canonical_players)
