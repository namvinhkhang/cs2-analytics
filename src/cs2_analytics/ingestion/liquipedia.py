"""Liquipedia REST API v3 ingestion client for CS2 competitive data.

Fetches five CS2 entity types: teams, players, matches, tournaments, placements.
Teams/players/matches are converted to canonical models and written to S3 as
snappy-compressed Parquet. Tournaments and placements are counted only — they
have no canonical schema yet and will be persisted in a future plan.

CRITICAL: Liquipedia enforces a strict bot rate limit.
A 2-second sleep between ALL requests is MANDATORY per their API policy.
Violating this causes IP blocks. Never remove asyncio.sleep(2.0).

Auth: Apikey header (register at liquipedia.net/api).
Base URL: https://api.liquipedia.net/api/v3
Response envelope: {"result": [...]} — always use data.get("result", []).
"""

from __future__ import annotations

import asyncio
from datetime import date

import structlog

from cs2_analytics.ingestion.base import BaseAPIClient
from cs2_analytics.models.canonical import Match, Player, Team
from cs2_analytics.models.liquipedia import (
    LiquipediaMatch,
    LiquipediaPlacement,
    LiquipediaPlayer,
    LiquipediaTeam,
    LiquipediaTournament,
)
from cs2_analytics.utils.parquet import MATCH_SCHEMA, PLAYER_SCHEMA, TEAM_SCHEMA, models_to_records
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

# Module-level structured logger — emits JSON-compatible log events
logger = structlog.get_logger()


class LiquipediaClient(BaseAPIClient):
    """Liquipedia REST API v3 client for CS2 competitive data.

    IMPORTANT: Liquipedia enforces a strict bot rate limit.
    A 2-second sleep between ALL requests is MANDATORY.
    Violating this causes IP blocks. Never remove asyncio.sleep(2.0).

    Auth: Apikey header (register at liquipedia.net/api).
    Base URL: https://api.liquipedia.net/api/v3
    Response envelope: {"result": [...]}

    All five fetch methods (get_teams, get_players, get_matches, get_tournaments,
    get_placements) call GET /{entity} with wiki="counterstrike" to scope results
    to CS2 competitive data.
    """

    BASE_URL: str = "https://api.liquipedia.net/api/v3"
    # Liquipedia allows ~10 req/s but we cap at 5 for safety alongside the 2s sleep
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(5)
    # Wiki parameter selects CS2 competitive data across all endpoints
    _WIKI: str = "counterstrike"

    def _auth_headers(self) -> dict[str, str]:
        """Return Liquipedia API key auth header.

        Note: Liquipedia uses 'Apikey' (not 'Bearer') as the authorization scheme.
        """
        return {
            "Authorization": f"Apikey {self._api_key}",
            "Accept": "application/json",
        }

    async def get_teams(self, limit: int = 50) -> list[LiquipediaTeam]:
        """Fetch CS2 teams from Liquipedia.

        Endpoint: GET /team?wiki=counterstrike&limit={limit}
        Sleeps 2s after request per Liquipedia bot rate limit policy.
        """
        data = await self.get("/team", wiki=self._WIKI, limit=limit)
        await asyncio.sleep(2.0)  # MANDATORY: Liquipedia bot rate limit
        return [LiquipediaTeam.model_validate(r) for r in data.get("result", [])]

    async def get_players(self, limit: int = 50) -> list[LiquipediaPlayer]:
        """Fetch CS2 players from Liquipedia.

        Endpoint: GET /player?wiki=counterstrike&limit={limit}
        Sleeps 2s after request per Liquipedia bot rate limit policy.
        """
        data = await self.get("/player", wiki=self._WIKI, limit=limit)
        await asyncio.sleep(2.0)  # MANDATORY: Liquipedia bot rate limit
        return [LiquipediaPlayer.model_validate(r) for r in data.get("result", [])]

    async def get_matches(self, limit: int = 50) -> list[LiquipediaMatch]:
        """Fetch CS2 match results from Liquipedia.

        Endpoint: GET /match2 (NOT /match — Liquipedia API v3 uses match2 for CS2)
        Sleeps 2s after request per Liquipedia bot rate limit policy.
        """
        data = await self.get("/match2", wiki=self._WIKI, limit=limit)
        await asyncio.sleep(2.0)  # MANDATORY: Liquipedia bot rate limit
        return [LiquipediaMatch.model_validate(r) for r in data.get("result", [])]

    async def get_tournaments(self, limit: int = 50) -> list[LiquipediaTournament]:
        """Fetch CS2 tournaments from Liquipedia.

        Endpoint: GET /tournament?wiki=counterstrike&limit={limit}
        Sleeps 2s after request per Liquipedia bot rate limit policy.
        """
        data = await self.get("/tournament", wiki=self._WIKI, limit=limit)
        await asyncio.sleep(2.0)  # MANDATORY: Liquipedia bot rate limit
        return [LiquipediaTournament.model_validate(r) for r in data.get("result", [])]

    async def get_placements(self, limit: int = 50) -> list[LiquipediaPlacement]:
        """Fetch CS2 tournament placements from Liquipedia.

        Endpoint: GET /placement?wiki=counterstrike&limit={limit}
        Sleeps 2s after request per Liquipedia bot rate limit policy.
        """
        data = await self.get("/placement", wiki=self._WIKI, limit=limit)
        await asyncio.sleep(2.0)  # MANDATORY: Liquipedia bot rate limit
        return [LiquipediaPlacement.model_validate(r) for r in data.get("result", [])]

    async def ingest_all(
        self,
        bucket: str,
        ingest_date: date,
        *,
        region: str = "us-east-1",
        limit: int = 50,
    ) -> dict[str, int]:
        """Ingest all 5 CS2 entity types and write canonical records to S3.

        Teams, players, and matches are converted to canonical models and
        written as snappy-compressed Parquet. Tournaments and placements
        have no canonical schema yet — only their counts are tracked.

        Returns dict of entity_type -> record count written.
        """
        y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
        raw_date = ingest_date.isoformat()
        counts: dict[str, int] = {}

        # --- Teams ---
        teams = await self.get_teams(limit=limit)
        canonical_teams: list[Team] = [t.to_canonical(ingested_at=raw_date) for t in teams]
        if canonical_teams:
            write_parquet_to_s3(
                records=models_to_records(canonical_teams),
                schema=TEAM_SCHEMA,
                bucket=bucket,
                key=build_s3_key("liquipedia", "teams", y, m, d),
                region=region,
            )
        counts["teams"] = len(canonical_teams)

        # --- Players ---
        players = await self.get_players(limit=limit)
        canonical_players: list[Player] = [p.to_canonical(recorded_at=raw_date) for p in players]
        if canonical_players:
            write_parquet_to_s3(
                records=models_to_records(canonical_players),
                schema=PLAYER_SCHEMA,
                bucket=bucket,
                key=build_s3_key("liquipedia", "players", y, m, d),
                region=region,
            )
        counts["players"] = len(canonical_players)

        # --- Matches ---
        matches = await self.get_matches(limit=limit)
        canonical_matches: list[Match] = [m.to_canonical() for m in matches]
        if canonical_matches:
            write_parquet_to_s3(
                records=models_to_records(canonical_matches),
                schema=MATCH_SCHEMA,
                bucket=bucket,
                key=build_s3_key("liquipedia", "matches", y, m, d),
                region=region,
            )
        counts["matches"] = len(canonical_matches)

        # --- Tournaments (no canonical schema yet — count only) ---
        # LiquipediaTournament has no to_canonical(); raw persistence is deferred
        # to a future plan when canonical schemas for tournaments are defined.
        tournaments = await self.get_tournaments(limit=limit)
        counts["tournaments"] = len(tournaments)

        # --- Placements (no canonical schema yet — count only) ---
        # LiquipediaPlacement has no to_canonical(); raw persistence is deferred.
        placements = await self.get_placements(limit=limit)
        counts["placements"] = len(placements)

        logger.info("liquipedia_ingest_complete", date=raw_date, counts=counts)
        return counts
