"""PandaScore API raw Pydantic v2 models.

Source models use extra="ignore" to silently tolerate undocumented API fields.
PandaScore's CS2 game ID is "counterstrike"; free tier allows 1,000 req/hour.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class PandaScoreMatch(BaseModel):
    """Raw PandaScore match record. Maps to canonical Match via to_canonical()."""

    model_config = ConfigDict(extra="ignore")

    id: int  # PandaScore integer match ID
    name: str
    status: str  # "not_started" | "running" | "finished" | "canceled"
    begin_at: str | None = None  # ISO-8601 datetime string
    end_at: str | None = None  # ISO-8601 datetime string
    winner: dict[str, Any] | None = None  # {"id": int, "name": str, ...}
    opponents: list[dict[str, Any]] = []  # [{"opponent": {"id": int, "name": str}}, ...]
    results: list[dict[str, Any]] | None = None  # [{"score": int, ...}, ...] per-team result

    def to_canonical(self) -> Match:
        """Map PandaScore match fields to the shared canonical Match schema."""
        from cs2_analytics.models.canonical import Match

        # Extract team IDs from opponents list with safe positional fallbacks
        team_a_id: str = "unknown"
        team_b_id: str = "unknown"
        if len(self.opponents) > 0:
            team_a_id = str(self.opponents[0]["opponent"]["id"])
        if len(self.opponents) > 1:
            team_b_id = str(self.opponents[1]["opponent"]["id"])

        # Extract winner ID if match has a result
        winner_id: str | None = None
        if self.winner is not None:
            winner_id = str(self.winner["id"])

        # Extract scores from results list if both teams present
        # CS2 regulation is MR12 (24 rounds total); overtime if combined > 24
        score_a: int | None = None
        score_b: int | None = None
        is_overtime: bool | None = None
        if self.results and len(self.results) >= 2:
            s1 = self.results[0].get("score")
            s2 = self.results[1].get("score")
            if s1 is not None and s2 is not None:
                score_a = int(s1)
                score_b = int(s2)
                # Overtime when both teams exceed regulation limit (MR15: both > 15)
                is_overtime = score_a > 15 and score_b > 15

        # Extract date portion from ISO-8601 datetime string
        # (e.g. "2024-01-15T12:00:00Z" → "2024-01-15")
        played_at: str = "unknown"
        if self.begin_at is not None:
            played_at = self.begin_at[:10]

        return Match(
            match_id=str(self.id),
            source="pandascore",
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            winner_id=winner_id,
            played_at=played_at,
            score_a=score_a,
            score_b=score_b,
            is_overtime=is_overtime,
        )


class PandaScorePlayer(BaseModel):
    """Raw PandaScore player record. Maps to canonical Player via to_canonical()."""

    model_config = ConfigDict(extra="ignore")

    id: int  # PandaScore integer player ID
    name: str  # in-game handle
    nationality: str | None = None
    current_team: dict[str, Any] | None = None  # {"id": int, "name": str, ...}

    def to_canonical(
        self,
        *,
        kills: int | None = None,
        deaths: int | None = None,
        adr: float | None = None,
        kd_ratio: float | None = None,
        match_id: str | None = None,
        recorded_at: str,
    ) -> Player:
        """Map PandaScore player fields to the shared canonical Player schema.

        Per-match stats (kills, deaths, adr, kd_ratio) are injected by the
        ingestion client when building per-match player stat records.
        """
        from cs2_analytics.models.canonical import Player

        # Extract team_id from nested current_team dict if present
        team_id: str | None = None
        if self.current_team is not None:
            team_id = str(self.current_team["id"])

        return Player(
            player_id=str(self.id),
            source="pandascore",
            display_name=self.name,
            nationality=self.nationality,
            team_id=team_id,
            kills=kills,
            deaths=deaths,
            adr=adr,
            kd_ratio=kd_ratio,
            match_id=match_id,
            recorded_at=recorded_at,
        )


# Re-export canonical types used in return annotations
from cs2_analytics.models.canonical import Match, Player  # noqa: E402, F401
