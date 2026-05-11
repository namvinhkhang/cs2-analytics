"""CS API ingestion client for modern CS2 public rankings and match stats."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import structlog

from cs2_analytics.ingestion.base import BaseAPIClient
from cs2_analytics.models.csapi import CSAPIPlayerStat, CSAPITeamRanking
from cs2_analytics.utils.parquet import (
    CSAPI_PLAYER_STATS_SCHEMA,
    CSAPI_TEAM_RANKING_SCHEMA,
)
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

logger = structlog.get_logger()


class CSAPIClient(BaseAPIClient):
    """No-auth public CS API client.

    The API serves daily-refreshed CS2 pro match, ranking, and player-stat data.
    """

    BASE_URL = "https://api.csapi.de"
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(2)

    def __init__(self) -> None:
        super().__init__(api_key="")

    async def __aenter__(self) -> CSAPIClient:
        """Return the concrete client type for static type checkers."""
        return self

    def _auth_headers(self) -> dict[str, str]:
        """CS API is public and does not require auth headers."""
        return {}

    async def get_rankings(self, *, ranking_date: date | None = None) -> list[CSAPITeamRanking]:
        """Fetch the latest or date-specific VRS-style ranking snapshot."""
        params: dict[str, Any] = {}
        if ranking_date is not None:
            params["date"] = ranking_date.isoformat()

        data = await self.get("/rankings/", **params)
        snapshot_date = str(data["date"])
        rankings = data.get("rankings", [])
        return [
            CSAPITeamRanking.model_validate({**ranking, "ranking_date": snapshot_date})
            for ranking in rankings
        ]

    async def get_matches(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch a page of recent CS API matches."""
        data = await self.get("/matches/", limit=limit, offset=offset)
        if not isinstance(data, list):
            return []
        return data

    async def get_match_stats(self, match_id: int) -> list[dict[str, Any]]:
        """Fetch aggregate player stats for one match."""
        data = await self.get(f"/matches/{match_id}/stats")
        if not isinstance(data, list):
            return []
        return data

    @staticmethod
    def _match_team_context(
        match: dict[str, Any],
        all_stats: dict[str, Any],
        team_key: str,
    ) -> tuple[int | None, str | None, list[dict[str, Any]]]:
        """Extract team metadata and player rows from one stats side."""
        stats_team = all_stats.get(team_key)
        match_team = match.get(team_key)
        stats_team_data = stats_team if isinstance(stats_team, dict) else {}
        match_team_data = match_team if isinstance(match_team, dict) else {}

        team_id_raw = stats_team_data.get("id") or match_team_data.get("id")
        team_id = int(team_id_raw) if team_id_raw is not None else None
        team_name_raw = stats_team_data.get("name") or match_team_data.get("name")
        team_name = str(team_name_raw) if team_name_raw is not None else None
        players_raw = stats_team_data.get("players", [])
        players = players_raw if isinstance(players_raw, list) else []
        return team_id, team_name, players

    def _flatten_match_player_stats(
        self,
        match: dict[str, Any],
        stats_payload: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Flatten `/matches/{id}/stats` into warehouse-ready player stat records."""
        all_stats = next(
            (
                stat_block
                for stat_block in stats_payload
                if stat_block.get("id") == 0
                or str(stat_block.get("name", "")).casefold() == "all"
            ),
            None,
        )
        if all_stats is None:
            return []

        match_id_raw = match.get("id")
        played_at_raw = match.get("date")
        if match_id_raw is None or played_at_raw is None:
            return []

        records: list[dict[str, Any]] = []
        match_id = str(match_id_raw)
        played_at = str(played_at_raw)

        for team_key in ("team1", "team2"):
            team_id, team_name, players = self._match_team_context(match, all_stats, team_key)
            for player in players:
                if not isinstance(player, dict):
                    continue
                stat = CSAPIPlayerStat.model_validate(
                    {
                        **player,
                        "team_id": team_id,
                        "team_name": team_name,
                        "N": 1,
                    }
                )
                records.append(
                    stat.to_player_stat_record(
                        recorded_at=played_at,
                        row_key=match_id,
                    )
                )

        return records

    async def ingest_team_rankings(
        self,
        bucket: str,
        ingest_date: date,
        *,
        ranking_date: date | None = None,
        region: str = "us-east-1",
    ) -> int:
        """Fetch modern team rankings and write them to S3."""
        rankings = await self.get_rankings(ranking_date=ranking_date)
        records = [ranking.to_ranking_record() for ranking in rankings]
        if records:
            y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
            write_parquet_to_s3(
                records=records,
                schema=CSAPI_TEAM_RANKING_SCHEMA,
                bucket=bucket,
                key=build_s3_key("csapi", "team_rankings", y, m, d),
                region=region,
            )

        logger.info("csapi_team_rankings_ingested", count=len(records))
        return len(records)

    async def ingest_player_stats(
        self,
        bucket: str,
        ingest_date: date,
        *,
        limit: int = 100,
        offset: int = 0,
        pages: int = 25,
        request_delay_seconds: float = 0.1,
        region: str = "us-east-1",
    ) -> int:
        """Fetch match-level modern player stats and write them to S3."""
        matches: list[dict[str, Any]] = []
        for page_index in range(pages):
            page_offset = offset + page_index * limit
            page_matches = await self.get_matches(limit=limit, offset=page_offset)
            matches.extend(page_matches)
            if len(page_matches) < limit:
                break

        records: list[dict[str, Any]] = []
        for match in matches:
            match_id_raw = match.get("id")
            if match_id_raw is None:
                continue

            stats_payload = await self.get_match_stats(int(match_id_raw))
            records.extend(self._flatten_match_player_stats(match, stats_payload))

            # Keep the public API polite when bootstrapping thousands of match details.
            if request_delay_seconds > 0:
                await asyncio.sleep(request_delay_seconds)

        if records:
            y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
            write_parquet_to_s3(
                records=records,
                schema=CSAPI_PLAYER_STATS_SCHEMA,
                bucket=bucket,
                key=build_s3_key("csapi", "player_stats", y, m, d),
                region=region,
            )

        logger.info(
            "csapi_player_stats_ingested",
            count=len(records),
            matches=len(matches),
        )
        return len(records)
